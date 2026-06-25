"""Bug-Hunt Persistenz — Session Speichern/Laden/Cleanup."""

import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

from scout.bughunt.core.model import (
    MAX_SESSIONS,
    SESSION_TTL_DAYS,
    SESSIONS_DIR,
    BugHuntSession,
)

logger = logging.getLogger(__name__)

# ======================================================================
# Session Persistenz
# ======================================================================


def _ensure_dirs():
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _atomic_write_json(path: Path, data: list) -> None:
    """Atomischer JSON-Write via tempfile + rename."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)


def save_session(session: BugHuntSession) -> str:
    """Session als JSON speichern. Returns session_id."""
    _ensure_dirs()
    path = SESSIONS_DIR / f"{session.session_id}.json"
    path.write_text(json.dumps(session.to_dict(), ensure_ascii=False, indent=2))
    return session.session_id


def load_session(session_id: str) -> Optional[BugHuntSession]:
    """Session von Disk laden."""
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return BugHuntSession.from_dict(data)
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to load session %s: %s", session_id, e)
        return None


def delete_session(session_id: str) -> bool:
    """Session von Disk löschen."""
    path = SESSIONS_DIR / f"{session_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def list_sessions() -> list[dict]:
    """Alle Sessions auflisten (neueste zuerst)."""
    _ensure_dirs()
    sessions = []
    for f in sorted(SESSIONS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            sessions.append({
                "session_id": data.get("session_id", ""),
                "project": data.get("project", ""),
                "scope": data.get("scope", ""),
                "status": data.get("status", ""),
                "findings_count": len(data.get("findings", [])),
                "started_at": data.get("started_at", ""),
                "closed_at": data.get("closed_at", ""),
            })
        except Exception as e:
            logger.warning("Failed to load session %s: %s", f.name, e)
            continue
    return sessions


# ======================================================================
# Path Validation
# ======================================================================

_TRAVERSAL = re.compile(r"(?:^|/|\\)\.{2,}(?:/|\\)|%2e%2e", re.I)
_INVALID_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def validate_path(path: str, allowed_base: Optional[Path] = None) -> Optional[str]:
    """Returns error string or None if valid.

    Args:
        path: The path string to validate.
        allowed_base: Optional base directory. If set, the resolved path
                      must be within this directory (catches symlink bypasses).
    """
    if not path or not isinstance(path, str):
        return "Path is empty or not a string"
    if len(path) > 4096:
        return f"Path too long ({len(path)} chars, max 4096)"
    if _INVALID_CHARS.search(path):
        return "Path contains control characters or null bytes"
    if _TRAVERSAL.search(path):
        return "Path traversal detected"
    # Resolve to catch symlink-based and encoding-based traversal bypasses
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


# ======================================================================
# Session Cleanup — verhindert Datenmüll
# ======================================================================


def cleanup_old_sessions(max_sessions: int = MAX_SESSIONS,
                         max_age_days: int = SESSION_TTL_DAYS) -> int:
    """Remove old session files beyond limits.

    Args:
        max_sessions: Maximum session files to keep (newest first).
        max_age_days: Maximum age in days for any session file.

    Returns:
        Number of deleted files.
    """
    before = len(list(SESSIONS_DIR.glob("*.json")))
    now = time.time()
    cutoff = now - (max_age_days * 86400)
    deleted = 0

    sessions = sorted(SESSIONS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)

    # Remove by age
    for f in sessions:
        if f.stat().st_mtime < cutoff:
            try:
                f.unlink()
                deleted += 1
            except OSError:
                pass

    # Remove by count (keep newest max_sessions)
    remaining = sorted(SESSIONS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    for f in remaining[max_sessions:]:
        try:
            f.unlink()
            deleted += 1
        except OSError:
            pass

    after = len(list(SESSIONS_DIR.glob("*.json")))
    if deleted:
        logger.debug("cleanup_old_sessions: %d removed (%d \u2192 %d)", deleted, before, after)
    return deleted
