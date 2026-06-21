"""Bug-Hunt Hooks — pre_llm_call, post_tool_call, on_session_end.

pre_llm_call:  Injects active session context when bug-related keywords detected.
post_tool_call: Tracks code_*/bug_hunt_* tool calls for active session.
on_session_end: Auto-persists active session to Honcho + auto-deduce shared patterns.
"""

import json, re, time, unicodedata
from typing import Any, Optional, List

import logging
logger = logging.getLogger(__name__)

# ---- Cache for pre_llm_call ----
_hook_cache: dict = {}
_HOOK_CACHE_TTL = 60  # seconds

# ---- Keywords triggering context injection ----
BUGHUNT_KEYWORDS = (
    "bug", "bugsuche", "bughunt", "bug hunt", "bug-jagd",
    "sicherheit", "security", "vulnerability", "verwundbarkeit",
    "finding", "audit", "scannen", "durchchecken", "analyse",
    "untersuch", "prüf", "scan",
)


def _is_bughunt_related(text: str) -> bool:
    """Check if user message contains bug-hunt keywords."""
    if not text:
        return False
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    text_lower = text.lower()
    return any(re.search(kw, text_lower) for kw in BUGHUNT_KEYWORDS)


def _get_cached(key: str) -> Optional[str]:
    cached = _hook_cache.get(key)
    if cached:
        val, ts = cached
        if time.monotonic() - ts < _HOOK_CACHE_TTL:
            return val
        _hook_cache.pop(key, None)
    return None


def _set_cached(key: str, val: str) -> None:
    _hook_cache[key] = (val, time.monotonic())
    if len(_hook_cache) > 20:
        _hook_cache.pop(next(iter(_hook_cache)), None)


# ======================================================================
# Hook: pre_llm_call
# ======================================================================

def on_pre_llm_call(**kwargs: Any) -> Optional[str]:
    """Inject active bug-hunt context when keywords detected."""
    messages = kwargs.get("messages", [])
    if not messages:
        return None

    # Extract last user message
    last_msg = ""
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("role") == "user":
            content = m.get("content", "")
            if isinstance(content, str):
                last_msg = content
            break

    if not last_msg or not _is_bughunt_related(last_msg):
        return None

    lines = ["[BUG-HUNT PLUGIN]"]

    # 1. Active session
    try:
        from . import bughunt_core as core  # Hermes Runtime (Package)
    except ImportError:
        import bughunt_core as core          # pytest (top-level Import)
    tracker = core.get_tracker()
    if tracker.is_active():
        ts = tracker.summary()
        lines.append(f"  Aktive Session: {ts['session_id']}")
        lines.append(f"  Tools: {ts['tools_used']}, Files: {ts['files_touched']}")
        session = core.load_session(tracker.active_session_id)
        if session:
            counts = session.findings_count()
            parts = [f"{sev}={counts[sev]}" for sev in ["P0", "P1", "P2", "P3"] if counts.get(sev, 0) > 0]
            if parts:
                lines.append(f"  Findings: {len(session.findings)} ({', '.join(parts)})")
        lines.append("  Nutze bug_hunt_list() für Details oder bug_hunt_finding() für neue Funde.")
    else:
        # 2. Recent sessions (cached)
        cached = _get_cached("recent_sessions")
        if cached:
            lines.append(cached)
        else:
            sessions = core.list_sessions()
            if sessions:
                ids = ", ".join(s.get("session_id", "?") for s in sessions[:3])
                text = f"  Letzte Sessions: {ids}"
                lines.append(text)
                lines.append("  Nutze bug_hunt_history(limit=5) für Details.")
                _set_cached("recent_sessions", "\n".join(lines[-2:]))

    return "\n".join(lines) if len(lines) > 1 else "[BUG-HUNT PLUGIN]\n  (keine aktiven Sessions)"


# ======================================================================
# Hook: post_tool_call
# ======================================================================

def on_post_tool_call(**kwargs: Any) -> None:
    """Track code_* and bug_hunt_* tool calls for the active session."""
    try:
        from . import bughunt_core as core  # Hermes Runtime (Package)
    except ImportError:
        import bughunt_core as core          # pytest (top-level Import)
    tracker = core.get_tracker()
    if not tracker.is_active():
        return

    tool_name = kwargs.get("tool_name", "")
    if not tool_name.startswith(("code_", "bug_hunt_")):
        return

    args = kwargs.get("args", {})
    result = kwargs.get("result", "")
    if isinstance(result, str) and "error" in result.lower()[:200]:
        return

    tracker.track_tool(tool_name, args, kwargs.get("status", "ok"))
    if isinstance(args, dict):
        path = args.get("path", "")
        if path and isinstance(path, str):
            tracker.track_file(path)


# ======================================================================
# Auto-Deduction: Findings → Shared Patterns
# ======================================================================

# Mapping: Code-Kontext → scan_query (P2b Heuristik)
_CONTEXT_PATTERNS: List[tuple] = [
    # try/except silent catch
    (r"except\s+\w*\s*:\s*pass", "except.*?:\\s*pass", "Silent Catch"),
    (r"except\s*:", r"except\s*:", "Bare Except"),
    # console.log/warn/error
    (r"console\.\s*(log|warn|error)\s*\(", r"console\.(log|warn|error)\(", "Console Log"),
    # execSync / exec
    (r"execSync\s*\(", r"execSync\(", "execSync Call"),
    (r"\bexec\s*\(", r"\bexec\s*\(", "exec Call"),
    # Timer
    (r"setTimeout\s*\(", r"setTimeout\(", "setTimeout"),
    (r"setInterval\s*\(", r"setInterval\(", "setInterval"),
    # eval
    (r"\beval\s*\(", r"\beval\s*\(", "eval Call"),
    # child_process
    (r"(spawn|fork|execFile)\s*\(", r"(spawn|fork|execFile)\(", "Child Process"),
    # SQL-Injection (Template-Strings in Query)
    (r"SELECT\s+.*FROM.*\+", r"SELECT.*FROM.*\\+", "SQL Concatenation"),
    # print() debugging
    (r"print\s*\(.*['\"]debug", r"print\\(.*['\\\"]debug", "Debug Print"),
    (r"print\s*\(.*[a-z]", r"print\\(.*[a-z]", "print() Debug"),
]

# Datei-Extension → scan_language Mapping
_EXTENSION_LANGUAGE: dict = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
}

# Datei-Extension → scan_file_glob Mapping
_EXTENSION_GLOB: dict = {
    ".py": "**/*.py",
    ".ts": "**/*.{ts,tsx}",
    ".tsx": "**/*.{ts,tsx}",
    ".js": "**/*.{js,jsx}",
    ".jsx": "**/*.{js,jsx}",
    ".go": "**/*.go",
    ".rs": "**/*.rs",
    ".java": "**/*.java",
    ".rb": "**/*.rb",
    ".php": "**/*.php",
}


def _deduce_scan_query(evidence: str) -> tuple[str, str]:
    """Extrahiert scan_query und Pattern-Name aus Evidence-Text.

    Nutzt Code-Kontext-Heuristiken statt Regex auf evidence:
    - try/except → except.*?:
    - console.log → console\\.(log|warn|error)\\(
    - execSync → execSync\\(

    Args:
        evidence: Evidence-Text aus Finding

    Returns:
        Tuple (scan_query, pattern_name)
    """
    if not evidence:
        return ("", "")

    ev = evidence.strip()

    # Pattern-Matching gegen Code-Kontext
    for ctx_regex, scan_query, name in _CONTEXT_PATTERNS:
        if re.search(ctx_regex, ev, re.IGNORECASE):
            return (scan_query, name)

    # Fallback: ersten Function-Call oder Keyword extrahieren
    m = re.search(r'([a-zA-Z_]\w*(?:\s*\([\'\"])?)', ev)
    if m:
        word = m.group(1).rstrip("('\"")
        if word:
            # Escape für grep: Function-Call
            escaped = re.escape(word)
            return (f"{escaped}\\(", word)

    # Letzter Fallback: erste 50 Zeichen der evidence
    return (re.escape(ev[:50].strip()), ev[:30])


def _deduce_language(file_path: str) -> tuple[str, str]:
    """Leitet scan_language und scan_file_glob aus Datei-Extension ab.

    Args:
        file_path: Dateipfad aus Finding

    Returns:
        Tuple (scan_language, scan_file_glob)
    """
    if not file_path:
        return ("", "")

    ext = None
    for known_ext in sorted(_EXTENSION_LANGUAGE.keys(), key=len, reverse=True):
        if file_path.endswith(known_ext):
            ext = known_ext
            break

    if ext:
        return (
            _EXTENSION_LANGUAGE.get(ext, ""),
            _EXTENSION_GLOB.get(ext, f"**/*{ext}"),
        )
    return ("", "")


def _deduce_category_from_severity(severity: str) -> str:
    """Leitet eine sinnvolle Kategorie aus der Severity ab."""
    if severity == "P0":
        return "security"
    elif severity == "P1":
        return "code-quality"
    elif severity == "P2":
        return "code-quality"
    elif severity == "P3":
        return "code-quality"
    return "other"


def _auto_deduce_patterns(session) -> List[str]:
    """Analysiert alle Findings einer Session und deduziert Shared Patterns.

    Für jedes Finding das genug Kontext hat (file, evidence, pattern_id):
    1. scan_query aus Evidence extrahieren
    2. scan_language + scan_file_glob aus file path ableiten
    3. Kategorie, Severity und Beschreibung aus Finding übernehmen
    4. Pattern via save_pattern() im Shared Repository registrieren

    Args:
        session: BugHuntSession-Objekt mit findings

    Returns:
        Liste der gespeicherten Pattern-IDs
    """
    from scout.shared.patterns import save_pattern, get_pattern

    created_patterns = []

    for f in session.findings:
        if not isinstance(f, dict):
            # Finding-Objekt → Dict konvertieren
            if hasattr(f, 'to_dict'):
                f = f.to_dict()
            elif hasattr(f, '__dict__'):
                f = f.__dict__
            else:
                continue

        title = f.get("title") or f.get("name", "")
        evidence = f.get("evidence") or f.get("match", "")
        file_path = f.get("file") or f.get("file_path", "")
        pattern_id = f.get("pattern_id", "")
        severity = f.get("severity", "P2")
        category = f.get("category", "")
        description = f.get("description", "")
        suggested_fix = f.get("suggested_fix") or f.get("fix_description", "")
        source_session = f.get("session_id") or (session.session_id if hasattr(session, 'session_id') else "")
        source_project = getattr(session, 'project', '')

        # Brauchen mindestens Titel und entweder evidence oder file_path
        if not title and not evidence:
            continue

        # scan_query aus Evidence ableiten
        scan_query, deduced_name = _deduce_scan_query(evidence)
        if not scan_query:
            continue

        # scan_language + scan_file_glob aus Datei-Extension
        scan_language, scan_file_glob = _deduce_language(file_path)

        # Kategorie: Finding oder deduced
        bh_categories = [category] if category else ["other"]
        if category:
            analysis_categories = [category]
        else:
            analysis_categories = [_deduce_category_from_severity(severity)]

        # Severity: max P1 für auto-deduced (zu riskant für automatische P0)
        final_severity = severity
        if severity == "P0":
            final_severity = "P1"

        try:
            # Prüfen ob Pattern bereits existiert (gleicher name + scan_query)
            pattern_data = {
                "name": title or deduced_name,
                "category": category or deduced_name[:30],
                "severity": final_severity,
                "description": description or f"Auto-deduced from finding: {title}",
                "scan_type": "grep",
                "scan_query": scan_query,
                "scan_file_glob": scan_file_glob,
                "scan_language": scan_language,
                "fix_description": suggested_fix,
                "analysis_depth": 2,
                "analysis_kinds": analysis_categories,
                "auto_analysis": True,
                "bughunt_categories": bh_categories,
                "source_plugin": "bughunt",
                "source_session": source_session,
                "source_project": source_project,
                "source_finding_id": f.get("id", "") if isinstance(f, dict) else "",
            }
            pid = save_pattern(pattern_data)
            created_patterns.append(pid)
        except ValueError as e:
            import logging
            logging.getLogger(__name__).debug(
                "bughunt: pattern deduction skipped for %s: %s", title, e
            )

    return created_patterns


# ======================================================================
# Hook: on_session_end (erweitert)
# ======================================================================

def on_session_end(**kwargs: Any) -> None:
    """Auto-save active session if not yet closed."""
    try:
        from . import bughunt_core as core  # Hermes Runtime (Package)
    except ImportError:
        import bughunt_core as core          # pytest (top-level Import)
    tracker = core.get_tracker()
    if not tracker.is_active():
        return

    session_id = tracker.active_session_id
    session = core.load_session(session_id)
    if not session:
        tracker.reset()
        return

    counts = session.findings_count()
    sev_parts = [f"{sev}={counts[sev]}" for sev in ["P0", "P1", "P2", "P3"] if counts.get(sev, 0) > 0]
    summary = f"Bug-Hunt {session_id}: {', '.join(sev_parts) if sev_parts else 'no findings'}"
    session.close(summary=summary)
    core.save_session(session)

    # Auto-Deduction: Findings → Shared Patterns (P2a)
    try:
        from scout.shared.patterns import count_patterns
        created = _auto_deduce_patterns(session)
        if created:
            stats = count_patterns()
            logger.info(
                "bughunt: %d Patterns auto-deduced (%d total in shared repo)",
                len(created), stats.get("total", 0)
            )
    except Exception as e:
        logger.debug("bughunt: auto-deduction skipped: %s", e)

    # Honcho persist via registry.dispatch (not invoke_hook!)
    try:
        from tools.registry import registry
        registry.dispatch("honcho_conclude", {
            "conclusion": json.dumps({
                "type": "bug_hunt_session",
                "session_id": session_id,
                "project": session.project,
                "scope": session.scope,
                "summary": summary,
                "findings_count": len(session.findings),
                "counts_by_severity": counts,
                "timestamp": session.closed_at,
            }),
            "peer": "bughunt",
        })
    except Exception as e:
        logger.warning("bughunt: Honcho persist failed: %s", e)

    tracker.reset()
