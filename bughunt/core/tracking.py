"""Bug-Hunt Tracking — In-Memory Tracker + Reporting für aktive Sessions.

BugHuntTracker: Zustand der aktuellen Bug-Hunt Session (für Hooks).
_get_tracker: Singleton-Zugriff.
_ok/_err: Formatierungshelfer für Tool-Responses.
_generate_markdown_report / _finding_md: Report-Generierung.
"""

import logging
import re
import time
from typing import Optional

from scout._fmt import fmt_err, fmt_ok
from scout.bughunt.core.model import BugHuntSession

logger = logging.getLogger(__name__)


# ======================================================================
# Tracking — BugHuntTracker
# ======================================================================


class BugHuntTracker:
    """In-Memory Tracker für die aktive Session. Nur für Hooks."""

    def __init__(self):
        self.active_session_id: Optional[str] = None
        self.tools_used: list[dict] = []
        self.files_touched: set[str] = set()
        self.last_scan_at: float = 0.0

    def start(self, session_id: str) -> None:
        self.reset()
        self.active_session_id = session_id
        self.last_scan_at = time.time()

    def track_tool(self, tool_name: str, args: dict, status: str = "ok") -> None:
        self.tools_used.append({
            "tool_name": tool_name,
            "args": args,
            "timestamp": time.time(),
            "status": status,
        })

    def track_file(self, filepath: str) -> None:
        self.files_touched.add(filepath)

    def reset(self) -> None:
        self.active_session_id = None
        self.tools_used = []
        self.files_touched = set()
        self.last_scan_at = 0.0

    def is_active(self) -> bool:
        return self.active_session_id is not None

    def summary(self) -> dict:
        return {
            "session_id": self.active_session_id,
            "tools_used": len(self.tools_used),
            "files_touched": len(self.files_touched),
            "last_scan_ago_sec": int(time.time() - self.last_scan_at) if self.last_scan_at else None,
        }


_tracker = BugHuntTracker()


def get_tracker() -> BugHuntTracker:
    """Singleton-Zugriff auf den BugHuntTracker."""
    return _tracker


# ======================================================================
# Helper: _ok / _err
# ======================================================================


def _ok(data: dict) -> str:
    """Success response — delegiert an fmt_ok."""
    return fmt_ok(data)


def _err(msg: str) -> str:
    """Error response — delegiert an fmt_err."""
    return fmt_err(msg)


# ======================================================================
# Reporting — Markdown-Report
# ======================================================================

TRAVERSAL = re.compile(r"(?:^|/|\\\\)\.{2,}(?:/|\\\\)|%2e%2e", re.I)
INVALID_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def validate_path(path: str, allowed_base=None) -> Optional[str]:
    """Returns error string or None if valid.

    Args:
        path: The path string to validate.
        allowed_base: Optional base directory. If set, the resolved path
                      must be within this directory (catches symlink bypasses).
    """
    from pathlib import Path

    if not path or not isinstance(path, str):
        return "Path is empty or not a string"
    if len(path) > 4096:
        return f"Path too long ({len(path)} chars, max 4096)"
    if INVALID_CHARS.search(path):
        return "Path contains control characters or null bytes"
    if TRAVERSAL.search(path):
        return "Path traversal detected"
    try:
        resolved = Path(path).resolve()
    except (OSError, ValueError):
        return "Path cannot be resolved"
    if allowed_base is not None:
        try:
            resolved.relative_to(Path(allowed_base).resolve())
        except ValueError:
            return "Path traversal detected (outside allowed directory)"
    return None  # path is valid


def _generate_markdown_report(session: BugHuntSession,
                               group_by: str = "severity") -> str:
    """Generiert einen Markdown-Report für eine Session."""
    lines = [
        f"# Bug-Hunt Report: {session.project}",
        "",
        f"- **Session:** `{session.session_id}`",
        f"- **Scope:** {session.scope}",
        f"- **Status:** {session.status}",
        f"- **Started:** {session.started_at}",
        f"- **Findings:** {len(session.findings)}",
        "",
    ]
    if session.summary:
        lines += ["## Summary", "", session.summary, ""]
    counts = session.findings_count()
    lines += ["## Severity Breakdown", ""]
    icons = {"P0": "🔴", "P1": "🟠", "P2": "🟡", "P3": "🔵", "INFO": "⚪"}
    for sev in ["P0", "P1", "P2", "P3", "INFO"]:
        if counts.get(sev, 0):
            lines.append(f"- {icons.get(sev, '⚪')} **{sev}:** {counts[sev]}")
    lines.append("")

    from scout.bughunt.core.model import FINDING_CATEGORIES

    if group_by == "severity":
        for sev in ["P0", "P1", "P2", "P3", "INFO"]:
            findings = [f for f in session.findings if f.get("severity") == sev]
            if findings:
                lines += [f"## {sev} Findings ({len(findings)})", ""]
                for f in findings:
                    lines += _finding_md(f)
    elif group_by == "category":
        for cat in FINDING_CATEGORIES:
            findings = [f for f in session.findings if f.get("category") == cat]
            if findings:
                lines += [f"## {cat.title()} ({len(findings)})", ""]
                for f in findings:
                    lines += _finding_md(f)
    elif group_by == "file":
        files: dict[str, list] = {}
        for f in session.findings:
            files.setdefault(f.get("file", "unknown"), []).append(f)
        for filepath in sorted(files):
            findings = files[filepath]
            lines += [f"## {filepath} ({len(findings)})", ""]
            for f in findings:
                lines += _finding_md(f)
    return "\n".join(lines)


def _finding_md(f: dict) -> list[str]:
    """Ein Finding als Markdown-Liste formatieren."""
    sev = f.get("severity", "P3")
    icons = {"P0": "🔴", "P1": "🟠", "P2": "🟡", "P3": "🟢", "INFO": "ℹ️"}
    icon = icons.get(sev, "•")
    title = f.get("title", "Unbekannt")
    lines = [f"### {icon} `[{sev}]` {title}"]
    if f.get("pattern_id"):
        lines.append(f"- **Pattern:** `{f['pattern_id']}`")
    if f.get("file"):
        loc = f"`{f['file']}"
        if f.get("line"):
            loc += f":{f['line']}"
        loc += "`"
        lines.append(f"- **Fundort:** {loc}")
    if f.get("description"):
        lines.append(f"- **Beschreibung:** {f['description']}")
    if f.get("evidence"):
        ev = f["evidence"]
        if len(ev) > 200:
            ev = ev[:200] + "..."
        lines.append(f"- **Evidenz:** `{ev}`")
    if f.get("suggested_fix"):
        lines.append(f"- **Fix:** {f['suggested_fix']}")
    return lines
