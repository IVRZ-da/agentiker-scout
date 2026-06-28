"""graph_patterns.py — analysis_graph/pattern_discover Tool-Handler.

Extracted from analysis_tools.py (Phase C) for modularity.
Enthält Mermaid-Diagramm-Generierung und Pattern-Discovery-Tools.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from scout._fmt import fmt_err, fmt_ok

from .base import _validate_and_resolve_path, _validate_path

logger = logging.getLogger("analysis")


# ---------------------------------------------------------------------------
# Mermaid-Helper
# ---------------------------------------------------------------------------


def _mermaid_from_dependency(data: Any) -> str:
    """Generiert einen Mermaid-Flowchart aus Dependency-Daten."""
    lines = ["```mermaid", "flowchart LR"]

    if isinstance(data, dict):
        # Versuche Graph-Einträge zu extrahieren
        for key, value in data.items():
            if isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, (list, tuple)):
                        a, b = item[0], item[-1]
                        lines.append(f"  {a} --> {b}")
                    elif isinstance(item, str):
                        lines.append(f"  {item}")
    elif isinstance(data, str):
        # Plain text — Graph-of-Things format
        for line in data.strip().split("\n"):
            line = line.strip()
            if "->" in line:
                parts = line.split("->")
                a = parts[0].strip().replace(" ", "_")
                b = parts[-1].strip().replace(" ", "_")
                lines.append(f"  {a} --> {b}")

    lines.append("```")
    return "\n".join(lines) if len(lines) > 3 else "```mermaid\nflowchart LR\n  no_data[No dependency data to graph]\n```"


def _mermaid_from_cycles(data: Any) -> str:
    """Generiert Mermaid-Diagramm aus Cycle-Daten."""
    lines = ["```mermaid", "flowchart LR"]

    if isinstance(data, dict):
        cycles = data.get("cycles", data.get("data", []))
        if isinstance(cycles, list):
            for i, cycle in enumerate(cycles[:5]):
                if isinstance(cycle, (list, tuple)) and len(cycle) >= 2:
                    style = f"style C{i} fill:#ffcccc,stroke:#ff0000"
                    cycle_label = f"subgraph C{i} [Cycle {i+1}]"
                    lines.append(cycle_label)
                    for j in range(len(cycle) - 1):
                        lines.append(f"  {cycle[j]}_{i} --> {cycle[j+1]}_{i}")
                    lines.append(f"  {cycle[-1]}_{i} --> {cycle[0]}_{i}")
                    lines.append("end")
                    lines.append(style)

    lines.append("```")
    return "\n".join(lines) if len(lines) > 3 else "```mermaid\nflowchart LR\n  no_cycles[No cycles detected]\n```"


# ---------------------------------------------------------------------------
# analysis_graph Tool
# ---------------------------------------------------------------------------


def analysis_graph_tool(args: dict, **kwargs) -> str:
    """Generiert ein Mermaid-Diagramm aus Analyse-Ergebnissen."""
    report = args.get("report", {})
    graph_type = args.get("type", "dependency")

    if not report:
        return fmt_err("report is required")

    result: Dict[str, Any] = {
        "tool": "analysis_graph",
        "type": graph_type,
        "report_tool": report.get("tool", "unknown"),
        "graph": "",
    }

    # Beste Daten aus dem Report extrahieren
    sections = report.get("sections", report.get("layers", report.get("findings", report)))

    if graph_type == "dependency":
        dep_data = (
            sections.get("dependency_graph") or
            sections.get("4_graphs", {}).get("dependency_graph") or
            report.get("dependency_graph") or
            {}
        )
        result["graph"] = _mermaid_from_dependency(dep_data)
        result["note"] = "Mermaid flowchart of module dependencies."

    elif graph_type == "cycles":
        cycle_data = (
            sections.get("cycles") or
            sections.get("4_graphs", {}).get("cycles") or
            report.get("cycles") or
            {}
        )
        result["graph"] = _mermaid_from_cycles(cycle_data)
        result["note"] = "Mermaid diagram showing circular dependencies."

    elif graph_type == "summary":
        summary = report.get("summary", {})
        lines = ["```mermaid", "flowchart LR"]
        for key, value in summary.items():
            if isinstance(value, (int, float, str)):
                lines.append(f"  {key}({key}: {value})")
        lines.append("```")
        result["graph"] = "\n".join(lines)
        result["note"] = "Mermaid overview of analysis summary."

    return fmt_ok(result)


# ---------------------------------------------------------------------------
# analysis_pattern_discover Tool (P4)
# ---------------------------------------------------------------------------


def analysis_pattern_discover_tool(args: dict, **kwargs) -> str:
    """Discover unregistered code patterns that look like bugs."""
    from scout._fmt import fmt_err, fmt_ok

    path = args.get("path", "")
    scan_language = args.get("scan_language", "")
    min_frequency = args.get("min_frequency", 3)
    frameworks_opt = args.get("frameworks", [])

    error = _validate_path(path)
    if error:
        return fmt_err(error)

    path_error, resolved_path = _validate_and_resolve_path(path)
    if path_error:  # pragma: no cover — dead code, _validate_path already catches above
        return fmt_err(f"{path_error} (path: {path})")
    path = resolved_path

    report: Dict[str, Any] = {
        "path": path,
        "candidates": [],
        "summary": {"patterns_scanned": 0, "patterns_found": 0, "gaps_found": 0},
    }

    # ── Framework Auto-Detection ───────────────────────────────────
    fw_names: list[str] = []
    if not frameworks_opt:
        try:
            from shared.framework_detector import FrameworkDetector
            detector = FrameworkDetector(path)
            fw_profile = detector.detect_fast()
            fw_names = []
            for fw_list in fw_profile.frameworks.values():
                for fw in fw_list:
                    fw_names.append(fw.name)
            report["frameworks"] = {
                cat: [fw.name for fw in fws]
                for cat, fws in fw_profile.frameworks.items()
            }
        except Exception as e:
            logger.debug("framework detection failed: %s", e)
    else:
        fw_names = list(frameworks_opt)
        # frameworks als Liste übergeben
        report["frameworks"] = {"specified": fw_names}

    # scan_language aus Framework ableiten wenn nicht explizit
    if not scan_language and fw_names:
        lang_map = {
            "typescript": ["typescript"],
            "javascript": ["javascript"],
            "go": ["go", "go-chi", "go-fiber"],
            "rust": ["rust"],
            "python": ["python", "fastapi", "django"],
        }
        for lang, fw_group in lang_map.items():
            if any(fw in fw_names for fw in fw_group):
                scan_language = lang
                break

    try:
        # 1. Vorhandene Shared Patterns laden (optional Framework-gefiltert)
        from scout.shared.patterns import get_patterns_for_analysis, get_patterns_for_frameworks

        if fw_names and report.get("frameworks"):
            # Framework-gefilterte Patterns laden
            existing = get_patterns_for_frameworks(
                report["frameworks"], scan_language
            )
            report["frameworks_used_for_filter"] = True
        else:
            existing = get_patterns_for_analysis(scan_language)
        existing_queries = set()
        for p in existing:
            query = p.get("scan_query", "")
            if query:
                existing_queries.add(query.lower())

        report["summary"]["patterns_scanned"] = len(existing)

        # 2. Statistische Analyse: Häufige Code-Muster erkennen
        candidates = []

        # 2a. Python: try/except Blöcke ohne passende Patterns
        if not scan_language or scan_language == "python":
            _discover_python_patterns(path, candidates, existing_queries, min_frequency)

        # 2b. TypeScript/JavaScript: Häufige Debug/Logging Muster
        if not scan_language or scan_language in ("typescript", "javascript"):
            _discover_ts_patterns(path, candidates, existing_queries, min_frequency)

        # 2c. Go: Häufige Fehlerbehandlungs-Muster
        if not scan_language or scan_language == "go":
            _discover_go_patterns(path, candidates, existing_queries, min_frequency)

        # 3. Confidence-Scores berechnen und sortieren
        for c in candidates:
            score = 0.5
            # Höhere Frequenz = höhere Confidence
            if c.get("frequency", 0) > 10:
                score += 0.3
            elif c.get("frequency", 0) > 5:
                score += 0.15
            # Mit Beschreibung = höhere Confidence
            if c.get("description"):
                score += 0.1
            # Fix-Vorschlag = höhere Confidence
            if c.get("suggested_fix"):
                score += 0.1
            c["confidence"] = round(min(score, 1.0), 2)

        candidates.sort(key=lambda c: c.get("confidence", 0), reverse=True)

        # 4. Limit auf Top-10
        report["candidates"] = candidates[:10]
        report["summary"]["gaps_found"] = len(candidates)
        report["summary"]["patterns_found"] = len(
            [c for c in candidates if c.get("confidence", 0) > 0.6]
        )

    except Exception as e:
        logger.warning("pattern discovery error: %s", e)
        report["summary"]["error"] = str(e)

    return fmt_ok(report)


# ---------------------------------------------------------------------------
# Pattern Discovery Helfer
# ---------------------------------------------------------------------------


def _discover_python_patterns(
    path: str,
    candidates: list,
    existing_queries: set,
    min_frequency: int,
) -> None:
    """Findet ungedeckte Python-spezifische Patterns."""
    import subprocess

    # Silent catch (except: pass) — prüfen ob schon gedeckt
    q1 = "except.*?:\\s*pass"
    if q1 not in existing_queries:
        try:
            r = subprocess.run(
                ["grep", "-rn", "-e", q1, path, "--include=*.py"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                count = len(r.stdout.strip().split("\n"))
                if count >= min_frequency:
                    candidates.append({
                        "suggested_name": "Silent Catch (Python)",
                        "category": "code-quality",
                        "severity": "P2",
                        "scan_type": "grep",
                        "scan_query": q1,
                        "scan_file_glob": "**/*.py",
                        "scan_language": "python",
                        "frequency": count,
                        "description": "Leeres except: pass ohne Logging. Fehler werden verschluckt.",
                        "suggested_fix": "Im except-Block mindestens logger.warning() verwenden.",
                    })
        except Exception as e:
                    logger.debug("silent catch (except: pass) pattern discovery failed: %s", e)

    # Mutable Default Args
        q2 = r"def \\w+\\([^)]*=\\{\\s*\\}|def \\w+\\([^)]*=\\[\\s*\\]"
    if q2 not in existing_queries:
        try:
            r = subprocess.run(
                ["grep", "-rn", "-E", "-e", q2, path, "--include=*.py"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                count = len(r.stdout.strip().split("\n"))
                if count >= min_frequency:
                    candidates.append({
                        "suggested_name": "Mutable Default Arguments",
                        "category": "code-quality",
                        "severity": "P2",
                        "scan_type": "grep",
                        "scan_query": q2,
                        "scan_file_glob": "**/*.py",
                        "scan_language": "python",
                        "frequency": count,
                        "description": "Mutable Default Args (list/dict) werden zwischen Aufrufen geteilt.",
                        "suggested_fix": "Default auf None setzen und im Body initialisieren.",
                    })
        except Exception as e:
            logger.debug("mutable default args pattern discovery failed: %s", e)


def _discover_ts_patterns(
    path: str,
    candidates: list,
    existing_queries: set,
    min_frequency: int,
) -> None:
    """Findet ungedeckte TypeScript/JavaScript Patterns."""
    import subprocess
    ts_glob = "--include=*.ts"
    tsx_glob = "--include=*.tsx"

    # console.log ohne passende Patterns prüfen
    q1 = r"console\.(log|warn|error)\("
    if q1 not in existing_queries:
        try:
            r = subprocess.run(
                ["grep", "-rn", "-E", "-e", q1, path, ts_glob, tsx_glob, "--include=*.js", "--include=*.jsx"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                count = len(r.stdout.strip().split("\n"))
                if count >= min_frequency:
                    candidates.append({
                        "suggested_name": "Console Log",
                        "category": "code-quality",
                        "severity": "P3",
                        "scan_type": "grep",
                        "scan_query": q1,
                        "scan_file_glob": "**/*.{ts,tsx,js,jsx}",
                        "scan_language": "typescript",
                        "frequency": count,
                        "description": "console.log/warn/error in Produktionscode — Debug-Überreste.",
                        "suggested_fix": "Durch logger.debug() ersetzen oder entfernen.",
                    })
        except Exception as e:
            logger.debug("console.log pattern discovery failed: %s", e)

    # any statt unknown
    q2 = r":\s*any\b"
    if q2 not in existing_queries:
        try:
            r = subprocess.run(
                ["grep", "-rn", "-E", "-e", q2, path, ts_glob, tsx_glob],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                count = len(r.stdout.strip().split("\n"))
                if count >= min_frequency:
                    candidates.append({
                        "suggested_name": "TypeScript 'any' statt 'unknown'",
                        "category": "typescript",
                        "severity": "P3",
                        "scan_type": "grep",
                        "scan_query": q2,
                        "scan_file_glob": "**/*.{ts,tsx}",
                        "scan_language": "typescript",
                        "frequency": count,
                        "description": ": any deaktiviert Type Checking. unknown ist type-safe.",
                        "suggested_fix": ": any durch : unknown ersetzen und Typ-Guards nutzen.",
                    })
        except Exception as e:
            logger.debug("any-vs-unknown pattern discovery failed: %s", e)

    # force-dynamic in Next.js
    q3 = r"export\s+(const\s+)?dynamic\s*=\s*['\"]force"
    if q3 not in existing_queries:
        try:
            r = subprocess.run(
                ["grep", "-rn", "-E", "-e", q3, path, ts_glob, tsx_glob],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                count = len(r.stdout.strip().split("\n"))
                if count >= min_frequency:
                    candidates.append({
                        "suggested_name": "force-dynamic Export",
                        "category": "code-quality",
                        "severity": "P3",
                        "scan_type": "grep",
                        "scan_query": q3,
                        "scan_file_glob": "**/*.{ts,tsx}",
                        "scan_language": "typescript",
                        "frequency": count,
                        "description": "force-dynamic deaktiviert Caching. Nur nutzen wenn nötig.",
                        "suggested_fix": "Auf 'auto' setzen oder Route Segment Config prüfen.",
                    })
        except Exception as e:
            logger.debug("force-dynamic pattern discovery failed: %s", e)


def _discover_go_patterns(
    path: str,
    candidates: list,
    existing_queries: set,
    min_frequency: int,
) -> None:
    """Findet ungedeckte Go Patterns."""
    import subprocess

    q1 = r"if err\s*!=\s*nil\s*\{\s*$"
    if q1 not in existing_queries:
        try:
            r = subprocess.run(
                ["grep", "-rn", "-E", "-e", q1, path, "--include=*.go"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                count = len(r.stdout.strip().split("\n"))
                if count >= min_frequency:
                    candidates.append({
                        "suggested_name": "Error ohne Handling",
                        "category": "code-quality",
                        "severity": "P2",
                        "scan_type": "grep",
                        "scan_query": q1,
                        "scan_file_glob": "**/*.go",
                        "scan_language": "go",
                        "frequency": count,
                        "description": "if err != nil { } — Error wird ignoriert (leerer Block).",
                        "suggested_fix": "Error immer loggen oder returned werden.",
                    })
        except Exception as e:
            logger.debug("go error handling pattern discovery failed: %s", e)
