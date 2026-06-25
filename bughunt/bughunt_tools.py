"""Bug-Hunt Tool Handler — 12 Tools für Bug-Jagd, Triage, Reporting.

Jeder Handler folgt dem Hermes Dispatch Contract:
    (args: dict, **kwargs) -> str
"""

import importlib.util
import json
import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("scout.bughunt")

# Import shared tool dispatch (analysis/tools/base.py)
try:
    from scout.analysis.tools.base import _call_tool
except ImportError:
    # Fallback: _call_tool definieren (falls analysis nicht verfügbar)
    def _call_tool(name: str, **kwargs):
        """Fallback wenn analysis tools nicht geladen."""
        logger.debug("_call_tool: %s nicht verfügbar (analysis tools fehlen)", name)
        return {"error": f"{name} nicht verfügbar"}

# Lazy-load bughunt_core via importlib (avoid relative import issues in tool dispatch)
_CORE_MODULE = None
_PLUGIN_DIR = Path(__file__).parent

def _get_core():
    """Lazy-load bughunt_core, ensuring init_patterns() is called.

    Tries normal relative import first (uses Python module cache — same
    instance that __init__.py already initialized). Falls back to importlib
    for contexts where relative imports fail (subagent dispatch, etc)."""
    global _CORE_MODULE
    if _CORE_MODULE is not None:
        return _CORE_MODULE

    # 1) Normal relative import — uses sys.modules cache → Singleton
    try:
        from scout.bughunt import bughunt_core as core_mod
        core_mod.init_patterns()  # idempotent — befüllt PATTERNS_BY_ID
        _CORE_MODULE = core_mod
        return _CORE_MODULE
    except (ImportError, AttributeError, ValueError) as e:
        logger.debug("bughunt_core lazy-import fallback: %s", e)
        pass

    # 2) Fallback: importlib mit korrektem Package-Namen
    #    ('scout.bughunt.bughunt_core' statt 'bughunt_core_loader' damit
    #     __package__='scout.bughunt' gesetzt wird → relative imports in
    #     init_patterns() funktionieren)
    core_path = _PLUGIN_DIR / 'bughunt_core.py'

    # Wenn bereits ein sys.modules['bughunt_core'] existiert (z.B. von Tests
    # die 'bughunt_core' direkt importieren und via monkeypatch patchen),
    # dieses verwenden statt eine neue importlib-Instanz zu erzeugen.
    if 'bughunt_core' in sys.modules:
        _CORE_MODULE = sys.modules['bughunt_core']
        _CORE_MODULE.init_patterns()
        return _CORE_MODULE

    spec = importlib.util.spec_from_file_location('scout.bughunt.bughunt_core', core_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load bughunt_core from {core_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules['scout.bughunt.bughunt_core'] = mod
    spec.loader.exec_module(mod)
    mod.init_patterns()  # jetzt sicher: __package__='scout.bughunt'
    # Auch unter bare-name registrieren — für monkeypatch.setattr("bughunt_core.xxx", mock)
    # in Tests. Sonst patchen Tests eine andere Instanz als die Handler verwenden.
    if 'bughunt_core' not in sys.modules:
        sys.modules['bughunt_core'] = mod
    _CORE_MODULE = mod
    return _CORE_MODULE


# Lazy-import bughunt_fix (keine zirkulären Abhängigkeiten)
_FIX_MODULE = None


def _get_fix_mod():
    """Lazy-import bughunt_fix — kein Core-Zugriff nötig."""
    global _FIX_MODULE
    if _FIX_MODULE is not None:
        return _FIX_MODULE
    try:
        from scout.bughunt import bughunt_fix as fix_mod
        _FIX_MODULE = fix_mod
        return _FIX_MODULE
    except (ImportError, AttributeError, ValueError) as e:
        logger.debug("bughunt_fix lazy-import fallback: %s", e)
        pass
    if "bughunt_fix" in sys.modules:
        _FIX_MODULE = sys.modules["bughunt_fix"]
        return _FIX_MODULE
    fix_path = _PLUGIN_DIR / "bughunt_fix.py"
    spec = importlib.util.spec_from_file_location("bughunt_fix", fix_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load bughunt_fix from {fix_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["bughunt_fix"] = mod
    spec.loader.exec_module(mod)
    _FIX_MODULE = mod
    return _FIX_MODULE


# ─── plan_follow Integration via Registry-Dispatch ─────────────────────
# Lose Kopplung: Wenn plan_follow Plugin geladen ist, können wir
# automatisch Bug-Hunt Pläne erstellen. Wenn nicht → Silent Skip.


def _try_create_bughunt_plan(project: str, session_id: str,
                              scope: str = "quick",
                              findings_count: int = 0) -> dict | None:
    """Create a plan_follow plan for the current bug hunt.

    Uses Registry-Dispatch for lose coupling — if plan_follow is not
    loaded, returns None silently.

    Returns:
        dict with plan status, or None if plan_follow unavailable.
    """
    try:
        from tools.registry import registry
        entry = registry.get_entry("plan_create")
        if entry is None:
            return None
        handler = getattr(entry, "handler", None)
        if not callable(handler):
            return None

        # Build plan with 3 phases: Scan → Fix → Verify
        plan_result = handler({
            "goal": f"Bug-Hunt: {project} ({scope})",
            "template": "research",
            "params": {
                "project": project,
                "session_id": session_id,
                "scope": scope,
            },
        })
        return json.loads(plan_result) if isinstance(plan_result, str) else plan_result
    except Exception:
        return None


def _ok(data: dict) -> str:
    """Success response — preserves existing status keys."""
    data.setdefault("status", "ok")
    return json.dumps(data, ensure_ascii=False)


def _err(msg: str) -> str:
    """Error response."""
    return json.dumps({"error": msg, "status": "error"}, ensure_ascii=False)


# ======================================================================
# Phase 2: Basic Tools
# ======================================================================

def bug_hunt_start(args: dict, **kwargs) -> str:
    """Start a new bug-hunt session."""
    core = _get_core()
    project = args.get("project", "").strip()
    if not project:
        return _err("project ist erforderlich — Pfad oder Name des zu scannenden Projekts")
    scope = args.get("scope", "quick")
    valid_scopes = {"quick", "comprehensive", "custom"}
    if scope not in valid_scopes:
        return _err(f"scope muss eine sein von: {', '.join(sorted(valid_scopes))}")
    focus_areas = args.get("focus_areas", [])
    session = core.BugHuntSession(project=project, scope=scope, focus_areas=focus_areas)
    core.save_session(session)
    tracker = core.get_tracker()
    tracker.start(session.session_id)

    # Optional: plan_follow integration (silent skip if not loaded)
    plan_result = _try_create_bughunt_plan(project, session.session_id, scope)
    plan_info = {}
    if plan_result:
        plan_info = {
            "plan_created": True,
            "plan_goal": plan_result.get("goal", ""),
            "plan_status": "Ein Bug-Hunt Plan wurde erstellt. "
                           "Nutze plan_current() für den aktuellen Task.",
        }

    return _ok({
        "session_id": session.session_id, "project": project, "scope": scope,
        "focus_areas": focus_areas, "status": "open", "findings_count": 0,
        **plan_info,
        "instruction": (
            "Möchtest du automatische Scans ausführen? Rufe bug_hunt_scan() auf mit "
            "Pattern-IDs wie ['security'] oder ['S001', 'C001']. Oder füge manuell "
            "Findings via bug_hunt_finding() hinzu."
        ),
    })


def bug_hunt_finding(args: dict, **kwargs) -> str:
    """Add a finding to a session."""
    core = _get_core()
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return _err("session_id ist erforderlich")
    session = core.load_session(session_id)
    if not session:
        return _err(f"Session {session_id} nicht gefunden")
    severity = args.get("severity", "P2").upper()
    if not core.Finding.validate_severity(severity):
        return _err(f"Ungültige severity: {severity}. Erlaubt: P0, P1, P2, P3, INFO")
    category = args.get("category", "other")
    if category not in core.FINDING_CATEGORIES:
        return _err(f"Ungültige category: {category}")
    title = args.get("title", "").strip()
    if not title:
        return _err("title ist erforderlich")
    finding = core.Finding(
        title=title, severity=severity, category=category,
        file=args.get("file", ""), line=args.get("line", 0),
        description=args.get("description", ""), evidence=args.get("evidence", ""),
        pattern_id=args.get("pattern_id", ""), suggested_fix=args.get("suggested_fix", ""),
        status=args.get("status", "open"),
    )
    finding_id = session.add_finding(finding)
    core.save_session(session)
    tracker = core.get_tracker()
    if finding.file:
        tracker.track_file(finding.file)
    instruction = ""
    if finding.severity in ("P0", "P1"):
        instruction = "P0/P1 Finding erfasst. Erwäge Triage via bug_hunt_triage() oder Fix mit Verifikation via bug_hunt_verify()."
    return _ok({"finding_id": finding_id, "title": title, "severity": severity,
                "status": "open", "total_findings": len(session.findings),
                "instruction": instruction})


def bug_hunt_list(args: dict, **kwargs) -> str:
    """List findings for a session, filterable."""
    core = _get_core()
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return _err("session_id ist erforderlich")
    session = core.load_session(session_id)
    if not session:
        return _err(f"Session {session_id} nicht gefunden")
    findings = session.get_findings(
        severity=args.get("severity"), status=args.get("status"),
        category=args.get("category"), file=args.get("file"),
    )
    return _ok({"session_id": session_id, "findings": findings,
                "count": len(findings), "total": len(session.findings),
                "counts_by_severity": session.findings_count()})


def bug_hunt_close(args: dict, **kwargs) -> str:
    """Close a bug-hunt session."""
    core = _get_core()
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return _err("session_id ist erforderlich")
    session = core.load_session(session_id)
    if not session:
        return _err(f"Session {session_id} nicht gefunden")
    session.close(summary=args.get("summary", ""))
    core.save_session(session)
    core.get_tracker().reset()
    return _ok({
        "session_id": session_id, "status": "closed",
        "total_findings": len(session.findings),
        "counts_by_severity": session.findings_count(),
        "instruction": "Session abgeschlossen. Rufe honcho_conclude() auf um die Session zu persistieren.",
    })


# ======================================================================
# Phase 4: Advanced Tools
# ======================================================================

def _resolve_scan_patterns(pattern_ids: list, preset_name: str, fw_list: list, core) -> tuple[list, list, Optional[dict]]:
    """Löst Preset + Pattern-IDs auf, inkl. Framework-Filterung."""
    scan_path = core.PLUGIN_DIR or "."

    # Preset auflösen
    if preset_name:
        try:
            from .bughunt_patterns import resolve_preset
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
                        summary: str, fw_profile: Optional[dict],
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
    core = _get_core()
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return _err("session_id ist erforderlich")
    session = core.load_session(session_id)
    if not session:
        return _err(f"Session {session_id} nicht gefunden")
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
        return _err(str(e))

    if not resolved:
        return _err(f"Keine Patterns gefunden für: {pattern_ids}")

    # Scan-Runner für grep-basierte Patterns
    try:
        from . import bughunt_scanrunner as runner
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
    return _ok(result)


def bug_hunt_triage(args: dict, **kwargs) -> str:
    """Update severity/status for findings."""
    core = _get_core()
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return _err("session_id ist erforderlich")
    session = core.load_session(session_id)
    if not session:
        return _err(f"Session {session_id} nicht gefunden")
    finding_ids = args.get("finding_ids", [])
    if not finding_ids:
        return _err("finding_ids ist erforderlich")
    severity = args.get("severity", "").upper()
    status = args.get("status", "")
    if severity and not core.Finding.validate_severity(severity):
        return _err(f"Ungültige severity: {severity}")
    if status and not core.Finding.validate_status(status):
        return _err(f"Ungültiger status: {status}")
    updates = {}
    if severity:
        updates["severity"] = severity
    if status:
        updates["status"] = status
    if args.get("notes"):
        updates["notes"] = args["notes"]
    if not updates:
        return _err("Mindestens eines von severity/status/notes ist erforderlich")
    updated = sum(1 for fid in finding_ids if session.update_finding(fid, updates))
    core.save_session(session)
    return _ok({"session_id": session_id, "finding_ids": finding_ids, "updated": updated, "updates": updates})


def bug_hunt_verify(args: dict, **kwargs) -> str:
    """Verify if a finding's bug still exists."""
    core = _get_core()
    session_id = args.get("session_id", "").strip()
    finding_id = args.get("finding_id", "").strip()
    if not session_id:
        return _err("session_id ist erforderlich")
    if not finding_id:
        return _err("finding_id ist erforderlich")
    session = core.load_session(session_id)
    if not session:
        return _err(f"Session {session_id} nicht gefunden")
    finding = None
    for f in session.findings:
        if f.get("id") == finding_id:
            finding = f
            break
    if not finding:
        return _err(f"Finding {finding_id} nicht in Session {session_id}")
    pattern_id = finding.get("pattern_id", "")
    file_path = finding.get("file", "")
    parts = []
    if file_path:
        parts.append(f"Lies Code um Zeile {finding.get('line', 0)} in {file_path} mit read_file()")
    if pattern_id:
        pattern = core.get_pattern(pattern_id)
        if pattern:
            parts.append(f"Führe code_search(pattern={pattern.scan_query!r}) aus")
    return _ok({
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
    core = _get_core()
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return _err("session_id ist erforderlich")
    finding_id = args.get("finding_id", "").strip()
    if not finding_id:
        return _err("finding_id ist erforderlich")
    fix_override = args.get("fix_instruction", "")

    session = core.load_session(session_id)
    if not session:
        return _err(f"Session {session_id} nicht gefunden")

    # Finding in der Session suchen
    finding = None
    for f in session.findings:
        if f.get("id") == finding_id:
            finding = f
            break
    if not finding:
        return _err(f"Finding {finding_id} nicht in Session {session_id}")

    # Pattern laden (falls vorhanden)
    pattern = None
    pattern_id = finding.get("pattern_id", "")
    if pattern_id:
        pattern_obj = core.get_pattern(pattern_id)
        if pattern_obj:
            pattern = pattern_obj.to_dict() if hasattr(pattern_obj, 'to_dict') else pattern_obj.__dict__

    # Fix-Instruction überschreiben falls manuell angegeben
    if fix_override:
        finding["suggested_fix"] = fix_override

    # Prompt bauen
    fix_mod = _get_fix_mod()
    prompt = fix_mod.build_fix_prompt(finding, pattern)

    return _ok({
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


def bug_hunt_report(args: dict, **kwargs) -> str:
    """Generate a structured bug-hunt report."""
    core = _get_core()
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return _err("session_id ist erforderlich")
    session = core.load_session(session_id)
    if not session:
        return _err(f"Session {session_id} nicht gefunden")
    report_format = args.get("format", "json")
    group_by = args.get("group_by", "severity")
    if report_format == "markdown":
        return _ok({"session_id": session_id, "format": "markdown",
                    "report": core._generate_markdown_report(session, group_by)})
    return _ok({
        "session_id": session_id, "project": session.project,
        "scope": session.scope, "status": session.status,
        "started_at": session.started_at, "closed_at": session.closed_at,
        "summary": session.summary, "total_findings": len(session.findings),
        "counts_by_severity": session.findings_count(),
        "findings": session.findings, "format": "json",
    })


# ======================================================================
# Phase 5: Management Tools
# ======================================================================

def bug_hunt_export(args: dict, **kwargs) -> str:
    """Export findings as JSON or Markdown."""
    core = _get_core()
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return _err("session_id ist erforderlich")
    session = core.load_session(session_id)
    if not session:
        return _err(f"Session {session_id} nicht gefunden")
    export_format = args.get("format", "json")
    output = args.get("output", "")
    if export_format == "markdown":
        content = core._generate_markdown_report(session, "severity")
    else:
        content = json.dumps(session.to_dict(), ensure_ascii=False, indent=2)
    result = {"session_id": session_id, "format": export_format, "content": content}
    if output:
        from pathlib import Path
        try:
            p = Path(output)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            result["output_path"] = str(p.resolve())
        except Exception as e:
            return _err(f"Export fehlgeschlagen: {e}")
    return _ok(result)


def bug_hunt_history(args: dict, **kwargs) -> str:
    """Search past bug-hunt sessions + Timeline via analysis_timeline.

    🔴 F3/F4: Erweiterte History mit analysis_timeline + code_git_blame.
    """
    core = _get_core()
    session_id = args.get("session_id", "").strip()
    if session_id:
        session = core.load_session(session_id)
        if not session:
            return _err(f"Session {session_id} nicht gefunden")
        return _ok({"session": session.to_dict(), "source": "local"})
    project = args.get("project", "").strip()
    limit = min(args.get("limit", 10), 50)
    sessions = core.list_sessions()
    if project:
        sessions = [s for s in sessions if project.lower() in s.get("project", "").lower()]

    result: dict = {
        "sessions": sessions[:limit], "count": min(len(sessions), limit),
        "instruction": "Für Details: bug_hunt_history(session_id='...'). Für Honcho: honcho_search(peer='bughunt').",
    }

    # Timeline/Blame Integration (wenn path angegeben)
    path = args.get("path", "").strip()
    symbol = args.get("symbol", "").strip()
    if path:
        try:
            timeline_kwargs = {"path": path}
            if symbol:
                timeline_kwargs["symbol"] = symbol
                timeline_kwargs["max_commits"] = 5
            from tools.registry import registry
            entry = registry.get_entry("analysis_timeline")
            if entry:
                tl_result = entry.handler(timeline_kwargs)
                if tl_result:
                    result["timeline"] = str(tl_result)[:500]
        except Exception:
            pass
        try:
            blame = _call_tool("code_git_blame", path=path)
            if blame and isinstance(blame, dict):
                result["git_blame"] = {
                    "lines": len(blame.get("blame", blame.get("lines", []))),
                }
        except Exception:
            pass

    return _ok(result)


def _pattern_list(args: dict, core) -> str:
    """Default: Alle Patterns listen (optional gefiltert nach Kategorie)."""
    category = args.get("category", "")
    patterns = core.get_patterns_by_category(category) if category else core.list_all_patterns()
    patterns = [p.to_dict() if hasattr(p, 'to_dict') else p for p in patterns]
    return _ok({"patterns": patterns, "count": len(patterns)})


def _pattern_detail(args: dict, core) -> str:
    """Detail eines einzelnen Patterns anzeigen."""
    pid = args.get("pattern_id", "").strip()
    if not pid:
        return _err("pattern_id ist erforderlich")
    pat = core.get_pattern(pid)
    if not pat:
        return _err(f"Pattern {pid} nicht gefunden")
    return _ok({"pattern": pat.to_dict()})


def _pattern_save(args: dict, core) -> str:
    """Neues Custom Pattern speichern."""
    try:
        pid = core.save_custom_pattern({
            "name": args.get("name", "").strip(),
            "category": args.get("category", "other"),
            "severity": args.get("severity", "P2").upper(),
            "description": args.get("description", ""),
            "scan_type": args.get("scan_type", ""),
            "scan_query": args.get("scan_query", "").strip(),
            "scan_file_glob": args.get("scan_file_glob", ""),
            "scan_language": args.get("scan_language", ""),
            "fix_description": args.get("fix_description", ""),
            "false_positive_notes": args.get("false_positive_notes", ""),
            "source_session": args.get("source_session", ""),
            "source_project": args.get("source_project", ""),
            "tags": args.get("tags", []),
        })
        return _ok({
            "pattern_id": pid, "action": "save",
            "instruction": f"Pattern {pid} gespeichert. Nutze bug_hunt_scan(patterns=['{pid}']) zum Scannen.",
        })
    except ValueError as e:
        return _err(str(e))


def _pattern_save_from_session(args: dict, core) -> str:
    """Custom Pattern aus einem Finding extrahieren."""
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return _err("session_id ist erforderlich")
    finding_id = args.get("finding_id", "").strip()
    if not finding_id:
        return _err("finding_id ist erforderlich")
    auto_deduce = args.get("auto_deduce", True)

    session = core.load_session(session_id)
    if not session:
        return _err(f"Session {session_id} nicht gefunden")
    finding = None
    for f in session.findings:
        if f.get("id") == finding_id:
            finding = f
            break
    if not finding:
        return _err(f"Finding {finding_id} nicht in Session {session_id}")

    pattern_data = _deduce_pattern_from_finding(finding, session_id, session, auto_deduce)

    try:
        pid = core.save_custom_pattern(pattern_data)
        return _ok({
            "pattern_id": pid, "action": "save_from_session",
            "source_session": session_id, "source_finding_id": finding_id,
            "deduced": pattern_data,
            "instruction": (
                f"Pattern {pid} aus Finding {finding_id} extrahiert. "
                f"Prüfe scan_query und passe ggf. via erneutem save an."
            ),
        })
    except ValueError as e:
        return _err(str(e))


def _deduce_pattern_from_finding(finding: dict, session_id: str, session, auto_deduce: bool) -> dict:
    """Leitet Pattern-Daten aus einem Finding ab."""
    pattern_data = {
        "name": finding.get("title", ""),
        "category": finding.get("category", "other"),
        "severity": finding.get("severity", "P2"),
        "description": finding.get("description", ""),
        "fix_description": finding.get("suggested_fix", ""),
        "source_session": session_id,
        "source_project": session.project,
        "source_finding_id": finding.get("id", ""),
    }

    if auto_deduce and finding.get("evidence"):
        file_path = finding.get("file", "")
        if file_path.endswith((".py", ".ts", ".tsx", ".js", ".go", ".rs")):
            pattern_data["scan_type"] = "grep"
            ev = finding.get("evidence", "")
            if ev:
                import re
                m = re.search(r'(\w+(?:\.\w+)*\s*\()', ev)
                if m:
                    pattern_data["scan_query"] = m.group(1).strip()
                else:
                    words = ev.split()
                    pattern_data["scan_query"] = words[0] if words else ev[:50]
            if file_path:
                ext = file_path.rsplit(".", 1)[-1]
                pattern_data["scan_file_glob"] = f"**/*.{ext}"
        else:
            pattern_data["scan_type"] = "grep"
    return pattern_data


def _pattern_list_custom(args: dict, core) -> str:
    """Nur Custom Patterns anzeigen."""
    patterns = core.list_custom_patterns()
    return _ok({"patterns": patterns, "count": len(patterns), "source": "custom"})


def _pattern_delete_custom(args: dict, core) -> str:
    """Custom Pattern löschen."""
    pid = args.get("pattern_id", "").strip()
    if not pid:
        return _err("pattern_id ist erforderlich")
    try:
        deleted = core.delete_custom_pattern(pid)
        if deleted:
            return _ok({"pattern_id": pid, "action": "delete_custom", "deleted": True})
        else:
            return _err(f"Pattern {pid} nicht gefunden")
    except ValueError as e:
        return _err(str(e))


def _pattern_import_from_session(args: dict, core) -> str:
    """Bulk-Import von Findings als Custom Patterns."""
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return _err("session_id ist erforderlich")
    session = core.load_session(session_id)
    if not session:
        return _err(f"Session {session_id} nicht gefunden")

    findings = session.findings
    imported = []
    skipped = 0
    for f in findings:
        if args.get("filter_pattern_id"):
            if f.get("pattern_id") != args["filter_pattern_id"]:
                continue
        try:
            pid = core.save_custom_pattern({
                "name": f.get("title", "Untitled"),
                "category": f.get("category", "other"),
                "severity": f.get("severity", "P2"),
                "description": f.get("description", ""),
                "scan_type": "grep",
                "scan_query": (f.get("pattern_id") or f.get("title", ""))[:100],
                "fix_description": f.get("suggested_fix", ""),
                "source_session": session_id,
                "source_project": session.project,
                "source_finding_id": f.get("id", ""),
            })
            imported.append(pid)
        except ValueError:
            skipped += 1

    return _ok({
        "action": "import_from_session",
        "session_id": session_id,
        "imported_count": len(imported),
        "skipped_count": skipped,
        "imported_pattern_ids": imported,
        "instruction": f"{len(imported)} Patterns importiert, {skipped} übersprungen (Duplikate/Fehler).",
    })


def bug_hunt_pattern(args: dict, **kwargs) -> str:
    """List, inspect, search, save, or manage bug patterns."""
    core = _get_core()
    action = args.get("action", "list")

    action_map = {
        "list_categories": lambda a, c: _ok({"categories": c.list_categories(), "count": len(c.list_categories())}),
        "detail": _pattern_detail,
        "save": _pattern_save,
        "save_from_session": _pattern_save_from_session,
        "list_custom": _pattern_list_custom,
        "delete_custom": _pattern_delete_custom,
        "import_from_session": _pattern_import_from_session,
    }

    handler = action_map.get(action)
    if handler:
        return handler(args, core)
    return _pattern_list(args, core)


def bug_hunt_stats(args: dict, **kwargs) -> str:
    """Statistics about findings in a session + Risk-Score via analysis_risk."""
    core = _get_core()
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return _err("session_id ist erforderlich")
    session = core.load_session(session_id)
    if not session:
        return _err(f"Session {session_id} nicht gefunden")
    findings = session.findings
    by_severity = session.findings_count()
    by_category = {}
    by_status = {}
    file_counts = {}
    for f in findings:
        by_category[f.get("category", "other")] = by_category.get(f.get("category", "other"), 0) + 1
        by_status[f.get("status", "open")] = by_status.get(f.get("status", "open"), 0) + 1
        fp = f.get("file", "unknown")
        file_counts[fp] = file_counts.get(fp, 0) + 1
    top_files = sorted(file_counts.items(), key=lambda x: -x[1])[:10]

    result: dict = {
        "session_id": session_id, "total": len(findings),
        "by_severity": by_severity, "by_category": by_category,
        "by_status": by_status,
        "top_files": [{"file": f, "count": c} for f, c in top_files],
        "scope": session.scope, "project": session.project, "status": session.status,
    }

    # Risk-Score via analysis_risk (falls verfügbar)
    project_path = session.project
    if project_path and project_path != "/test":
        try:
            risk_result = _call_tool("analysis_risk", path=project_path)
            if isinstance(risk_result, dict) and risk_result.get("risk_score") is not None:
                result["risk_score"] = risk_result["risk_score"]
                result["risk_level"] = risk_result.get("risk_level", "unknown")
        except Exception:
            pass

    return _ok(result)
