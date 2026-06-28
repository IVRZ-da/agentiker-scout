"""Bug-Hunt History Tool — Search past sessions + Timeline via analysis_timeline."""

from . import base  # noqa: F401


def bug_hunt_history(args: dict, **kwargs) -> str:
    """Search past bug-hunt sessions + Timeline via analysis_timeline.

    🔴 F3/F4: Erweiterte History mit analysis_timeline + code_git_blame.
    """
    core = base._get_core()
    session_id = args.get("session_id", "").strip()
    if session_id:
        session = core.load_session(session_id)
        if not session:
            return base._err(f"Session {session_id} nicht gefunden")
        return base._ok({"session": session.to_dict(), "source": "local"})
    project = args.get("project", "").strip()
    limit = min(args.get("limit", 10), 50)
    sessions = core.list_sessions()
    if project:
        sessions = [s for s in sessions if project.lower() in s.get("project", "").lower()]

    result: dict = {
        "sessions": sessions[:limit], "count": min(len(sessions), limit),
        "instruction": (
            "Für Details: bug_hunt_history(session_id='...'). "
            "Für Honcho: honcho_search(peer='bughunt')."
        ),
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
            blame = base._call_tool("code_git_blame", path=path)
            if blame and isinstance(blame, dict):
                result["git_blame"] = {
                    "lines": len(blame.get("blame", blame.get("lines", []))),
                }
        except Exception:
            pass

    return base._ok(result)
