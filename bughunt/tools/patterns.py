"""Bug-Hunt Pattern Tools — List, inspect, save, and manage bug patterns."""

import re

from . import base  # noqa: F401


def _pattern_list(args: dict, core) -> str:
    """Default: Alle Patterns listen (optional gefiltert nach Kategorie)."""
    category = args.get("category", "")
    patterns = core.get_patterns_by_category(category) if category else core.list_all_patterns()
    patterns = [p.to_dict() if hasattr(p, 'to_dict') else p for p in patterns]
    return base._ok({"patterns": patterns, "count": len(patterns)})


def _pattern_detail(args: dict, core) -> str:
    """Detail eines einzelnen Patterns anzeigen."""
    pid = args.get("pattern_id", "").strip()
    if not pid:
        return base._err("pattern_id ist erforderlich")
    pat = core.get_pattern(pid)
    if not pat:
        return base._err(f"Pattern {pid} nicht gefunden")
    return base._ok({"pattern": pat.to_dict()})


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
        return base._ok({
            "pattern_id": pid, "action": "save",
            "instruction": f"Pattern {pid} gespeichert. bug_hunt_scan(patterns=['{pid}']).",
        })
    except ValueError as e:
        return base._err(str(e))


def _pattern_save_from_session(args: dict, core) -> str:
    """Custom Pattern aus einem Finding extrahieren."""
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return base._err("session_id ist erforderlich")
    finding_id = args.get("finding_id", "").strip()
    if not finding_id:
        return base._err("finding_id ist erforderlich")
    auto_deduce = args.get("auto_deduce", True)

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

    pattern_data = _deduce_pattern_from_finding(finding, session_id, session, auto_deduce)

    try:
        pid = core.save_custom_pattern(pattern_data)
        return base._ok({
            "pattern_id": pid, "action": "save_from_session",
            "source_session": session_id, "source_finding_id": finding_id,
            "deduced": pattern_data,
            "instruction": (
                f"Pattern {pid} aus Finding {finding_id} extrahiert. "
                f"Prüfe scan_query und passe ggf. via erneutem save an."
            ),
        })
    except ValueError as e:
        return base._err(str(e))


def _deduce_pattern_from_finding(finding: dict, session_id: str, session, auto_deduce: bool) -> dict:  # noqa: E501
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
    return base._ok({"patterns": patterns, "count": len(patterns), "source": "custom"})


def _pattern_delete_custom(args: dict, core) -> str:
    """Custom Pattern löschen."""
    pid = args.get("pattern_id", "").strip()
    if not pid:
        return base._err("pattern_id ist erforderlich")
    try:
        deleted = core.delete_custom_pattern(pid)
        if deleted:
            return base._ok({"pattern_id": pid, "action": "delete_custom", "deleted": True})
        else:
            return base._err(f"Pattern {pid} nicht gefunden")
    except ValueError as e:
        return base._err(str(e))


def _pattern_import_from_session(args: dict, core) -> str:
    """Bulk-Import von Findings als Custom Patterns."""
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return base._err("session_id ist erforderlich")
    session = core.load_session(session_id)
    if not session:
        return base._err(f"Session {session_id} nicht gefunden")

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

    return base._ok({
        "action": "import_from_session",
        "session_id": session_id,
        "imported_count": len(imported),
        "skipped_count": skipped,
        "imported_pattern_ids": imported,
        "instruction": f"{len(imported)} Patterns importiert, {skipped} übersprungen.",
    })


def bug_hunt_pattern(args: dict, **kwargs) -> str:
    """List, inspect, search, save, or manage bug patterns."""
    core = base._get_core()
    action = args.get("action", "list")

    action_map = {
        "list_categories": lambda a, c: base._ok({"categories": c.list_categories(), "count": len(c.list_categories())}),  # noqa: E501
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
