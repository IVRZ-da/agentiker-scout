"""Bug-Hunt Session Tools — Start, Finding, List, Close, Triage, Report, Export, Stats."""

import json

from . import base  # noqa: F401

# ======================================================================
# Phase 2: Basic Tools
# ======================================================================

def bug_hunt_start(args: dict, **kwargs) -> str:
    """Start a new bug-hunt session."""
    core = base._get_core()
    project = args.get("project", "").strip()
    if not project:
        return base._err("project ist erforderlich — Pfad oder Name des zu scannenden Projekts")
    scope = args.get("scope", "quick")
    valid_scopes = {"quick", "comprehensive", "custom"}
    if scope not in valid_scopes:
        return base._err(f"scope muss eine sein von: {', '.join(sorted(valid_scopes))}")
    focus_areas = args.get("focus_areas", [])
    session = core.BugHuntSession(project=project, scope=scope, focus_areas=focus_areas)
    core.save_session(session)
    tracker = core.get_tracker()
    tracker.start(session.session_id)

    # Optional: plan_follow integration (silent skip if not loaded)
    plan_result = base._try_create_bughunt_plan(project, session.session_id, scope)
    plan_info = {}
    if plan_result:
        plan_info = {
            "plan_created": True,
            "plan_goal": plan_result.get("goal", ""),
            "plan_status": "Ein Bug-Hunt Plan wurde erstellt. "
                           "Nutze plan_current() für den aktuellen Task.",
        }

    return base._ok({
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
    core = base._get_core()
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return base._err("session_id ist erforderlich")
    session = core.load_session(session_id)
    if not session:
        return base._err(f"Session {session_id} nicht gefunden")
    severity = args.get("severity", "P2").upper()
    if not core.Finding.validate_severity(severity):
        return base._err(f"Ungültige severity: {severity}. Erlaubt: P0, P1, P2, P3, INFO")
    category = args.get("category", "other")
    if category not in core.FINDING_CATEGORIES:
        return base._err(f"Ungültige category: {category}")
    title = args.get("title", "").strip()
    if not title:
        return base._err("title ist erforderlich")
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
        instruction = "P0/P1 Finding. Triage via bug_hunt_triage() oder Fix via bug_hunt_verify()."
    return base._ok({"finding_id": finding_id, "title": title, "severity": severity,
                "status": "open", "total_findings": len(session.findings),
                "instruction": instruction})


def bug_hunt_list(args: dict, **kwargs) -> str:
    """List findings for a session, filterable."""
    core = base._get_core()
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return base._err("session_id ist erforderlich")
    session = core.load_session(session_id)
    if not session:
        return base._err(f"Session {session_id} nicht gefunden")
    findings = session.get_findings(
        severity=args.get("severity"), status=args.get("status"),
        category=args.get("category"), file=args.get("file"),
    )
    return base._ok({"session_id": session_id, "findings": findings,
                "count": len(findings), "total": len(session.findings),
                "counts_by_severity": session.findings_count()})


def bug_hunt_close(args: dict, **kwargs) -> str:
    """Close a bug-hunt session."""
    core = base._get_core()
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return base._err("session_id ist erforderlich")
    session = core.load_session(session_id)
    if not session:
        return base._err(f"Session {session_id} nicht gefunden")
    session.close(summary=args.get("summary", ""))
    core.save_session(session)
    core.get_tracker().reset()
    return base._ok({
        "session_id": session_id, "status": "closed",
        "total_findings": len(session.findings),
        "counts_by_severity": session.findings_count(),
        "instruction": "Session abgeschlossen. Nutze honcho_conclude() zum Persistieren.",
    })


def bug_hunt_triage(args: dict, **kwargs) -> str:
    """Update severity/status for findings."""
    core = base._get_core()
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return base._err("session_id ist erforderlich")
    session = core.load_session(session_id)
    if not session:
        return base._err(f"Session {session_id} nicht gefunden")
    finding_ids = args.get("finding_ids", [])
    if not finding_ids:
        return base._err("finding_ids ist erforderlich")
    severity = args.get("severity", "").upper()
    status = args.get("status", "")
    if severity and not core.Finding.validate_severity(severity):
        return base._err(
            f"Ungültige severity: '{severity}'. "
            f"Gültige Werte: {', '.join(core.SEVERITY_VALUES)}"
        )
    if status and not core.Finding.validate_status(status):
        return base._err(
            f"Ungültiger status: '{status}'. "
            f"Gültige Werte: {', '.join(core.FINDING_STATUSES)}"
        )
    updates = {}
    if severity:
        updates["severity"] = severity
    if status:
        updates["status"] = status
    if args.get("notes"):
        updates["notes"] = args["notes"]
    if not updates:
        return base._err("Mindestens eines von severity/status/notes ist erforderlich")
    updated = sum(1 for fid in finding_ids if session.update_finding(fid, updates))
    core.save_session(session)
    return base._ok({"session_id": session_id, "finding_ids": finding_ids, "updated": updated, "updates": updates})  # noqa: E501


def bug_hunt_report(args: dict, **kwargs) -> str:
    """Generate a structured bug-hunt report."""
    core = base._get_core()
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return base._err("session_id ist erforderlich")
    session = core.load_session(session_id)
    if not session:
        return base._err(f"Session {session_id} nicht gefunden")
    report_format = args.get("format", "json")
    group_by = args.get("group_by", "severity")
    if report_format == "markdown":
        return base._ok({"session_id": session_id, "format": "markdown",
                    "report": core.generate_markdown_report(session, group_by)})
    return base._ok({
        "session_id": session_id, "project": session.project,
        "scope": session.scope, "status": session.status,
        "started_at": session.started_at, "closed_at": session.closed_at,
        "summary": session.summary, "total_findings": len(session.findings),
        "counts_by_severity": session.findings_count(),
        "findings": session.findings, "format": "json",
    })


def bug_hunt_export(args: dict, **kwargs) -> str:
    """Export findings as JSON or Markdown."""
    core = base._get_core()
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return base._err("session_id ist erforderlich")
    session = core.load_session(session_id)
    if not session:
        return base._err(f"Session {session_id} nicht gefunden")
    export_format = args.get("format", "json")
    output = args.get("output", "")
    if export_format == "markdown":
        content = core.generate_markdown_report(session, "severity")
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
            return base._err(f"Export fehlgeschlagen: {e}")
    return base._ok(result)


def bug_hunt_stats(args: dict, **kwargs) -> str:
    """Statistics about findings in a session + Risk-Score via analysis_risk."""
    core = base._get_core()
    session_id = args.get("session_id", "").strip()
    if not session_id:
        return base._err("session_id ist erforderlich")
    session = core.load_session(session_id)
    if not session:
        return base._err(f"Session {session_id} nicht gefunden")
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
            risk_result = base._call_tool("analysis_risk", path=project_path)
            if isinstance(risk_result, dict) and risk_result.get("risk_score") is not None:
                result["risk_score"] = risk_result["risk_score"]
                result["risk_level"] = risk_result.get("risk_level", "unknown")
        except Exception:
            pass

    return base._ok(result)
