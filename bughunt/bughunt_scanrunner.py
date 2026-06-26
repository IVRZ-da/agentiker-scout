"""Scan-Runner für bug_hunt_scan() — automatische Ausführung von grep + code_intel Scans.

Architektur:
- **grep-Scans** (security, code-quality pattern mit scan_type=grep) → automatisch via subprocess
- **code_intel-Scans** (code_security_scan, code_search_by_error, code_todo_finder) → via Registry Dispatch
- **code_search** / **code_diagnostics** → weiterhin Instructions (kein auto-exec)
"""
import logging
import re
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

# ASCII-freundliche Severity-Icons
SEVERITY_ICONS = {"P0": "[P0]", "P1": "[P1]", "P2": "[P2]", "P3": "[P3]", "INFO": "[INFO]"}


def run_grep_scan(scan_query: str, scan_file_glob: str,
                  project_root: str, timeout: int = 30) -> list[dict]:
    """Execute a grep scan and return structured matches.

    Args:
        scan_query: Regex pattern to search for.
        scan_file_glob: Glob pattern for files to include (e.g. '**/*.ts').
        project_root: Absolute path to the project root.
        timeout: Max seconds for grep to run.

    Returns:
        List of dicts with keys: file, line, match, context
    """
    results = []
    try:
        # Build --include flags from glob pattern
        include_flag = []
        if scan_file_glob:
            # Handle patterns like **/*.ts → *.ts für grep --include
            # or **/*.{ts,tsx} → separate includes
            pattern = scan_file_glob.replace("**/", "")
            if "{" in pattern and "}" in pattern:
                # Multiple extensions: {ts,tsx} → --include=*.ts --include=*.tsx
                parts = pattern.split("{", 1)
                prefix = parts[0]
                extensions = parts[1].split("}", 1)[0].split(",")
                for ext in extensions:
                    include_flag.extend(["--include", f"{prefix}{ext}"])
            else:
                include_flag = ["--include", pattern]

        cmd = ["grep", "-rnI"] + include_flag + [scan_query, project_root]
        logger.debug("Scan-Runner: %s", " ".join(str(c) for c in cmd))

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if proc.returncode == 0 or proc.returncode == 1:
            # 0 = matches found, 1 = no matches (not an error)
            for line in proc.stdout.splitlines():
                match = _parse_grep_line(line)
                if match:
                    results.append(match)
        else:
            logger.warning("grep exit code %d: %s", proc.returncode,
                           proc.stderr[:200] if proc.stderr else "")

    except subprocess.TimeoutExpired:
        logger.warning("grep scan timed out after %ds: %s", timeout, scan_query[:50])
    except FileNotFoundError:
        logger.warning("grep not found on system")
    except Exception as e:
        logger.warning("grep scan failed: %s", e)

    return results


# ---------------------------------------------------------------------------
# code_intel Scan Dispatch (Phase 1 — Neue Scan-Typen)
# ---------------------------------------------------------------------------
# 🔴 F2: Graceful Degradation — jeder Scan hat try/except
# Wenn code_intel Plugin nicht geladen ist, wird der Scan übersprungen
# und als "not available" vermerkt (kein Abbruch des gesamten Batches).

# Mapping: scan_type → registry tool name
_CODE_INTEL_SCAN_MAP = {
    "code_security_scan": {
        "tool": "code_security_scan",
        "kwargs": {"severity": "all"},
        "finding_extractor": lambda r: [
            {"file": f.get("file", ""), "line": f.get("line", 0),
             "evidence": f.get("evidence", f.get("description", ""))[:200],
             "severity": _map_security_severity(f.get("severity", "P3"))}
            for f in (r.get("findings", []) if isinstance(r, dict) else [])
        ],
    },
    "code_search_by_error": {
        "tool": "code_search_by_error",
        "kwargs": {},
        "finding_extractor": lambda r: [
            {"file": e.get("file", ""), "line": e.get("line", 0),
             "evidence": e.get("evidence", e.get("match", ""))[:200],
             "severity": "P2"}
            for e in (r.get("errors", r.get("data", [])) if isinstance(r, dict) else [])
        ],
    },
    "code_todo_finder": {
        "tool": "code_todo_finder",
        "kwargs": {},
        "finding_extractor": lambda r: [
            {"file": m.get("file", ""), "line": m.get("line", 0),
             "evidence": m.get("match", m.get("content", ""))[:200],
             "severity": "P3"}
            for m in (r.get("matches", r.get("data", [])) if isinstance(r, dict) else [])
        ],
    },
}


def _map_security_severity(sev: str) -> str:
    """Map security scan severity to P-Level."""
    sev_map = {"CRITICAL": "P0", "HIGH": "P1", "MEDIUM": "P2", "LOW": "P3", "INFO": "INFO"}
    return sev_map.get(sev.upper(), "P2")


def _run_code_intel_scan(scan_type: str, scan_path: str) -> dict:
    """Führt einen code-intel Scan via Registry Dispatch aus.

    🔴 F2: Bei fehlendem Plugin/Registry → graceful Fallback.
    Returns: dict mit "findings" (list) und "tool_status".
    """
    scan_config = _CODE_INTEL_SCAN_MAP.get(scan_type)
    if not scan_config:
        return {"findings": [], "tool_status": "unknown_scan_type"}

    tool_name = scan_config["tool"]
    kwargs = dict(scan_config["kwargs"])
    kwargs["path"] = scan_path

    try:
        from tools.registry import registry
        entry = registry.get_entry(tool_name)
        if entry is None:
            logger.debug("code_intel scan skipped — %s not registered", tool_name)
            return {"findings": [], "tool_status": f"{tool_name} nicht verfügbar (Plugin?)"}

        # Handle both handler signatures:
        # (args: dict, **kwargs) — standard Hermes pattern
        # (**kwargs) — some tools only accept keyword args
        try:
            result = entry.handler(kwargs)
        except TypeError:
            result = entry.handler(**kwargs)
        if isinstance(result, str):
            import json
            try:
                result = json.loads(result)
            except (json.JSONDecodeError, TypeError):
                # Rich-format output (e.g. code_intel fmt_ok Panels) —
                # cannot be parsed as JSON automatically.
                # The user can run the tool manually via the instruction.
                return {"findings": [], "tool_status": f"{tool_name}: rich output (nicht automatisch parsebar)"}

        extractor = scan_config["finding_extractor"]
        findings = extractor(result) if callable(extractor) else []
        return {"findings": findings, "tool_status": "ok", "raw_count": len(findings)}

    except Exception as e:
        # 🔴 F2: Graceful Degradation — kein Abbruch
        logger.debug("code_intel scan %s failed: %s", tool_name, e)
        return {"findings": [], "tool_status": f"{tool_name}: {e}"}


def _parse_grep_line(line: str) -> Optional[dict]:
    """Parse a single grep output line into a structured result.

    Format: filepath:line:content
    Handles edge cases like colons in filepaths and binary warnings.
    """
    line = line.strip()
    if not line or "Binary file" in line:
        return None

    # Find first colon with digits after it (format: file:line:content)
    match = re.match(r"^(.+?):(\d+):(.*)$", line)
    if not match:
        return None

    filepath = match.group(1)
    line_num = int(match.group(2))
    content = match.group(3).strip()

    return {
        "file": filepath,
        "line": line_num,
        "match": content[:200],  # Truncate long matches
    }


def batch_grep_scans(patterns: list[dict], project_root: str) -> dict:
    """Execute multiple grep scans and collect results.

    Args:
        patterns: List of pattern dicts (from pattern library).
        project_root: Project root to scan.

    Returns:
        dict with auto_findings (list of finding dicts) and manual_instructions.
    """
    auto_findings = []
    manual_instructions = []

    for pattern in patterns:
        scan_type = pattern.get("scan_type", "")
        scan_query = pattern.get("scan_query", "")
        scan_file_glob = pattern.get("scan_file_glob", "")
        pattern_id = pattern.get("pattern_id", "")
        name = pattern.get("name", "")
        severity = pattern.get("severity", "P2")

        if scan_type == "grep" and scan_query:
            matches = run_grep_scan(scan_query, scan_file_glob, project_root)
            if matches:
                for m in matches:
                    auto_findings.append({
                        "pattern_id": pattern_id,
                        "severity": severity,
                        "title": name,
                        "file": m["file"],
                        "line": m["line"],
                        "evidence": m["match"],
                        "category": pattern.get("category", "other"),
                        "description": pattern.get("description", ""),
                        "suggested_fix": pattern.get("fix_description", ""),
                    })
                manual_instructions.append(
                    f"✅ {pattern_id} ({name}): {len(matches)} Treffer automatisch erfasst"
                )
            else:
                manual_instructions.append(
                    f"ℹ️ {pattern_id} ({name}): Keine Treffer (grep)"
                )

        elif scan_type in _CODE_INTEL_SCAN_MAP:
            # 🔴 F2: Graceful Degradation — bei Fehler kein Abbruch
            scan_result = _run_code_intel_scan(scan_type, project_root)
            findings = scan_result.get("findings", [])
            tool_status = scan_result.get("tool_status", "unknown")

            if tool_status == "ok" and findings:
                for f_data in findings:
                    auto_findings.append({
                        "pattern_id": pattern_id,
                        "severity": f_data.get("severity", severity),
                        "title": name,
                        "file": f_data.get("file", ""),
                        "line": f_data.get("line", 0),
                        "evidence": f_data.get("evidence", ""),
                        "category": pattern.get("category", "other"),
                        "description": pattern.get("description", ""),
                        "suggested_fix": pattern.get("fix_description", ""),
                    })
                manual_instructions.append(
                    f"✅ {pattern_id} ({name}): {len(findings)} Treffer via {scan_type}"
                )
            elif tool_status == "ok" and not findings:
                manual_instructions.append(
                    f"ℹ️ {pattern_id} ({name}): Keine Treffer ({scan_type})"
                )
            else:
                # 🔴 F2: Tool nicht verfügbar — kein Abbruch, nur Hinweis
                manual_instructions.append(
                    f"⚠️ {pattern_id} ({name}): {tool_status} — Scan übersprungen"
                )

        elif scan_type in ("code_search", "code_diagnostics"):
            manual_instructions.append(
                f"🔧 {pattern_id} ({name}): Bitte führe `{scan_type}` aus: "
                f"{scan_query} (Dateien: {scan_file_glob or 'alle'})"
            )

        else:
            manual_instructions.append(
                f"❓ {pattern_id} ({name}): Unbekannter Scan-Typ '{scan_type}'"
            )

    return {
        "auto_findings": auto_findings,
        "manual_instructions": manual_instructions,
        "auto_count": len(auto_findings),
        "manual_count": len(manual_instructions),
    }


def get_scan_summary(scan_result: dict) -> str:
    """Generate a human-readable summary of scan results."""
    auto_findings = scan_result.get("auto_findings", [])
    manual = scan_result.get("manual_instructions", [])

    lines = []
    if auto_findings:
        # Group by severity
        by_sev: dict[str, list] = {}
        for f in auto_findings:
            sev = f.get("severity", "P2")
            by_sev.setdefault(sev, []).append(f)

        lines.append(f"🔍 {len(auto_findings)} automatische Treffer:")
        for sev in ["P0", "P1", "P2", "P3", "INFO"]:
            if sev in by_sev:
                icon = SEVERITY_ICONS.get(sev, "•")
                lines.append(f"  {icon} {sev}: {len(by_sev[sev])} Treffer")
    else:
        lines.append("🔍 Keine automatischen Treffer")

    if manual:
        lines.append(f"\n📋 {len(manual)} manuelle Scans nötig:")
        for instr in manual:
            lines.append(f"  {instr}")

    return "\n".join(lines)
