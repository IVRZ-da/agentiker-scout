"""Bug-Hunt Scan Tools — Scan, Verify, Fix + internal helpers."""

from . import base  # noqa: F401

# ======================================================================
# Phase 4: Advanced Tools
# ======================================================================

def _resolve_scan_patterns(pattern_ids: list, preset_name: str, fw_list: list, core) -> tuple[list, list, dict | None]:  # noqa: E501
    """Löst Preset + Pattern-IDs auf, inkl. Framework-Filterung."""
    scan_path = core.PLUGIN_DIR or "."

    # Preset auflösen
    if preset_name:
        try:
            from ..bughunt_patterns import resolve_preset
            pattern_ids = resolve_preset(preset_name)
        except (ImportError, ValueError) as e:
            raise ValueError(str(e))

    # Framework Auto-Detection
    fw_profile = None
    if not fw_list:
        try:
            from shared.framework_detector import FrameworkDetector
            detector = FrameworkDetector(scan_path)
            fw_profile = detector.detect_fast().to_dict()
            fw_frameworks = fw_profile.get("frameworks", {})
            fw_list = []
            for cat_list in fw_frameworks.values():
                for fw in cat_list:
                    n = fw.get("name", "")
                    if n:
                        fw_list.append(n)
        except Exception:
            fw_profile = None

    # Patterns auflösen + Framework-Filter
    resolved = []
    for p in pattern_ids:
        pat = core.get_pattern(p)
        if pat:
            if _pattern_matches_frameworks(pat, fw_list):
                resolved.append(pat)
        else:
            pats = core.get_patterns_by_category(p)
            if pats:
                for pat in pats:
                    if _pattern_matches_frameworks(pat, fw_list):
                        resolved.append(pat)

    return resolved, fw_list, fw_profile


def _pattern_matches_frameworks(pat, fw_list: list) -> bool:
    """Prüft ob ein Pattern zum Framework-Stack passt."""
    if not fw_list:
        return True
    if not hasattr(pat, 'frameworks') or not pat.frameworks:
        return True
    if pat.frameworks == ["*"]:
        return True
    return any(fw in fw_list for fw in pat.frameworks)


def _add_auto_findings(session, scan_result: dict, core) -> list:
    """Fügt automatische Findings zur Session hinzu."""
    added = []
    for f_data in scan_result.get("auto_findings", []):
        f = core.Finding(
            title=f_data["title"],
            severity=f_data["severity"],
            category=f_data.get("category", "other"),
            file=f_data.get("file", ""),
            line=f_data.get("line", 0),
            evidence=f_data.get("evidence", ""),
            pattern_id=f_data.get("pattern_id", ""),
            description=f_data.get("description", ""),
            suggested_fix=f_data.get("suggested_fix", ""),
        )
        fid = session.add_finding(f)
        added.append(fid)
    if added:
        core.save_session(session)
    return added


def _build_scan_result(session_id: str, pattern_ids: list, resolved: list,
                        added_findings: list, scan_result: dict,
                        summary: str, fw_profile: dict | None,
                        fw_list: list) -> dict:
    """Baut das Ergebnis-Dict für den Scan."""
    result = {
        "session_id": session_id,
        "patterns_requested": pattern_ids,
        "patterns_resolved": [
            p.pattern_id if hasattr(p, 'pattern_id') else p.get('pattern_id')
            for p in resolved
        ],
        "auto_findings_count": len(added_findings),
        "auto_findings": scan_result["auto_findings"][:20],
        "manual_scan_instructions": scan_result["manual_instructions"],
        "summary": summary,
        "instruction": (
            f"Automatische Scans: {len(added_findings)} Findings erfasst. "
            f"Manuelle Scans: {len(scan_result['manual_instructions'])} offen.\n"
            f"Nutze bug_hunt_list(session_id='{session_id}') für Details."
        ),
    }
    if fw_profile:
        resolved_fw = list(fw_list) if isinstance(fw_list, list) else []
        result["frameworks"] = {
            cat: [fw["name"] for fw in fws]
            for cat, fws in fw_profile.get("frameworks", {}).items()
        }
        result["framework_warning"] = (
            f"{len(result['patterns_resolved'])} Patterns aktiv für erkannten Stack"
            if resolved_fw else "Kein Framework erkannt — alle generischen Patterns geladen"
        )
    return result


def bug_hunt_scan(args: dict, **kwargs) -> str:
    """Run automated scans using pattern library.

    Features:
    - **grep patterns**: Automatische Ausführung via Scan-Runner
    - **code_search/code_diagnostics**: Instructions (benötigt Hermes-Tools)
    - auto_add_findings: Findings automatisch zur Session hinzufügen (Default: True)
    """
    core = base._get_core()
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return base._err("session_id ist erforderlich")
    session = core.load_session(session_id)
    if not session:
        return base._err(f"Session {session_id} nicht gefunden")
    pattern_ids = args.get("patterns", [])
    preset_name = args.get("preset", "")
    scan_path = args.get("path", session.project)
    auto_add = args.get("auto_add_findings", True)
    fw_list = args.get("frameworks", [])

    # Patterns auflösen (Preset + Framework-Filter)
    try:
        resolved, fw_list, fw_profile = _resolve_scan_patterns(
            pattern_ids, preset_name, fw_list, core
        )
    except ValueError as e:
        return base._err(str(e))

    if not resolved:
        return base._err(f"Keine Patterns gefunden für: {pattern_ids}")

    # Scan-Runner für grep-basierte Patterns
    try:
        from .. import bughunt_scanrunner as runner
    except ImportError:
        import bughunt_scanrunner as runner

    pattern_dicts = [p.to_dict() if hasattr(p, 'to_dict') else p.__dict__ for p in resolved]
    scan_result = runner.batch_grep_scans(pattern_dicts, scan_path)

    # Auto-Findings
    added_findings = []
    if auto_add:
        added_findings = _add_auto_findings(session, scan_result, core)

    session.scan_count += 1
    core.save_session(session)

    summary = runner.get_scan_summary(scan_result)
    result = _build_scan_result(
        session_id, pattern_ids, resolved, added_findings,
        scan_result, summary, fw_profile, fw_list
    )
    return base._ok(result)


def bug_hunt_verify(args: dict, **kwargs) -> str:
    """Verify if a finding's bug still exists."""
    core = base._get_core()
    session_id = args.get("session_id", "").strip()
    finding_id = args.get("finding_id", "").strip()
    if not session_id:
        return base._err("session_id ist erforderlich")
    if not finding_id:
        return base._err("finding_id ist erforderlich")
    session = core.load_session(session_id)
    if not session:
        return base._err(f"Session {session_id} nicht gefunden")
    finding = None
    for f in session.findings:
        if f.get("id") == finding_id:
            finding = f
            break
    if not finding:
        return base._err(f"Finding {finding_id} nicht in Session {session_id}")
    pattern_id = finding.get("pattern_id", "")
    file_path = finding.get("file", "")
    parts = []
    if file_path:
        parts.append(f"Lies Code um Zeile {finding.get('line', 0)} in {file_path} mit read_file()")
    if pattern_id:
        pattern = core.get_pattern(pattern_id)
        if pattern:
            parts.append(f"Führe code_search(pattern={pattern.scan_query!r}) aus")
    return base._ok({
        "finding_id": finding_id, "finding": finding,
        "instruction": " | ".join(parts) if parts else "Manuelle Prüfung nötig.",
    })


# ======================================================================
# bug_hunt_fix — Auto-Fix via Subagent
# ======================================================================

def bug_hunt_fix(args: dict, **kwargs) -> str:
    """Generate an auto-fix prompt for a bug finding.

    Returns a fix_prompt that the agent can pass to delegate_task()
    for automatic bug fixing. Supports both Finding-pattern and
    manual fix instructions.
    """
    core = base._get_core()
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return base._err("session_id ist erforderlich")
    finding_id = args.get("finding_id", "").strip()
    if not finding_id:
        return base._err("finding_id ist erforderlich")
    fix_override = args.get("fix_instruction", "")

    session = core.load_session(session_id)
    if not session:
        return base._err(f"Session {session_id} nicht gefunden")

    # Finding in der Session suchen
    finding = None
    for f in session.findings:
        if f.get("id") == finding_id:
            finding = f
            break
    if not finding:
        return base._err(f"Finding {finding_id} nicht in Session {session_id}")

    # Pattern laden (falls vorhanden)
    pattern = None
    pattern_id = finding.get("pattern_id", "")
    if pattern_id:
        pattern_obj = core.get_pattern(pattern_id)
        if pattern_obj:
            pattern = pattern_obj.to_dict() if hasattr(pattern_obj, 'to_dict') else pattern_obj.__dict__  # noqa: E501

    # Fix-Instruction überschreiben falls manuell angegeben
    if fix_override:
        finding["suggested_fix"] = fix_override

    # Prompt bauen
    fix_mod = base._get_fix_mod()
    prompt = fix_mod.build_fix_prompt(finding, pattern)

    return base._ok({
        "session_id": session_id,
        "finding_id": finding_id,
        "pattern_id": pattern_id,
        "title": finding.get("title", ""),
        "severity": finding.get("severity", "P2"),
        "file": finding.get("file", ""),
        "line": finding.get("line", 0),
        "fix_prompt": prompt,
        "instruction": (
            f"Führe delegate_task(goal=fix_prompt) aus, um den Fix automatisch "
            f"anzuwenden. Nach erfolgreichem Fix: bug_hunt_finding("
            f"session_id='{session_id}', title='{finding.get('title', '')}', "
            f"status='fixed', ...) aufrufen."
        ),
    })
