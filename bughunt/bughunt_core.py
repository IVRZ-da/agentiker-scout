"""Bug-Hunt Core — Datenmodelle, Session-Management, Persistenz, Tracker.

Finding: Ein einzelnes Bug-Finding (title, severity, file, line, ...)
BugHuntSession: Ein Scan-Durchlauf (findings, status, project)
BugHuntTracker: In-Memory Tracker für aktive Session (für Hooks)
"""

import hashlib
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from scout._fmt import fmt_err, fmt_ok

logger = logging.getLogger(__name__)

# ======================================================================
# Pfade
# ======================================================================

PLUGIN_DIR = Path(__file__).parent
DATA_DIR = PLUGIN_DIR / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
PATTERNS_DIR = DATA_DIR / "patterns"
CUSTOM_PATTERNS_FILE = PATTERNS_DIR / "custom_patterns.json"
CUSTOM_PREFIX = "CUSTOM_"
MAX_CUSTOM_PATTERNS = 500

# ======================================================================
# Konstanten
# ======================================================================

SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "INFO": 4}
SEVERITY_VALUES = list(SEVERITY_ORDER.keys())

FINDING_STATUSES = [
    "open", "triaged", "in_progress", "fixed",
    "verified", "false_positive", "wont_fix",
]

FINDING_CATEGORIES = [
    "security", "code-quality", "typescript", "react-next",
    "admin-ui", "performance", "testing", "dependency",
    "database", "other",
]


# ======================================================================
# Datenmodell: Finding
# ======================================================================

class Finding:
    """Ein einzelnes Bug-Finding."""

    def __init__(self, title: str = "", severity: str = "P2",
                 category: str = "other", file: str = "", line: int = 0,
                 description: str = "", evidence: str = "",
                 pattern_id: str = "", suggested_fix: str = "",
                 status: str = "open"):
        self.id = str(uuid.uuid4())[:8]
        self.title = title
        self.severity = severity
        self.category = category
        self.file = file
        self.line = line
        self.description = description
        self.evidence = evidence
        self.pattern_id = pattern_id
        self.suggested_fix = suggested_fix
        self.status = status
        self.notes = ""
        now = datetime.now(timezone.utc).isoformat()
        self.created_at = now
        self.updated_at = now

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "Finding":
        f = cls()
        for k, v in d.items():
            setattr(f, k, v)
        return f

    @staticmethod
    def validate_severity(v: str) -> bool:
        return v.upper() in SEVERITY_VALUES

    @staticmethod
    def validate_status(v: str) -> bool:
        return v in FINDING_STATUSES


# ======================================================================
# Datenmodell: BugHuntSession
# ======================================================================

class BugHuntSession:
    """Eine Bug-Hunt Session (entspricht einem Scan-Durchlauf)."""

    def __init__(self, project: str = "", scope: str = "quick",
                 focus_areas: Optional[list[str]] = None):
        self.session_id = str(uuid.uuid4())[:12]
        self.project = project
        self.scope = scope  # quick, comprehensive, custom
        self.focus_areas = focus_areas or []
        self.findings: list[dict] = []
        self.status = "open"
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.closed_at: Optional[str] = None
        self.summary = ""
        self.scan_count = 0

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "BugHuntSession":
        s = cls()
        for k, v in d.items():
            setattr(s, k, v)
        return s

    def add_finding(self, finding: Finding) -> str:
        """Finding hinzufügen (mit Duplikat-Prüfung).

        Duplikat = gleicher file + line + pattern_id + Status nicht fixed/verified.
        Nur wenn mindestens file oder pattern_id gesetzt ist (sonst kein eindeutiges ID-Merkmal).
        Gibt finding_id zurück (neu oder existierend).
        """
        has_id_fields = bool(finding.file or finding.pattern_id)
        if has_id_fields:
            for existing in self.findings:
                if (existing.get("file") == finding.file
                        and existing.get("line") == finding.line
                        and existing.get("pattern_id") == finding.pattern_id
                        and existing.get("status") not in ("fixed", "verified", "false_positive")):
                    return existing["id"]
        d = finding.to_dict()
        self.findings.append(d)
        return d["id"]

    def update_finding(self, finding_id: str, updates: dict) -> bool:
        """Finding aktualisieren. Returns True bei Erfolg."""
        for existing in self.findings:
            if existing["id"] == finding_id:
                allowed = {"severity", "status", "notes", "suggested_fix", "title", "description"}
                for k, v in updates.items():
                    if k in allowed:
                        existing[k] = v
                existing["updated_at"] = datetime.now(timezone.utc).isoformat()
                return True
        return False

    def get_findings(self, severity: str = None, status: str = None,
                     category: str = None, file: str = None) -> list[dict]:
        """Gefilterte Findings, sortiert nach Severity (P0 zuerst)."""
        results = self.findings
        if severity:
            results = [f for f in results if f.get("severity", "").upper() == severity.upper()]
        if status:
            results = [f for f in results if f.get("status") == status]
        if category:
            results = [f for f in results if f.get("category") == category]
        if file:
            results = [f for f in results if file.lower() in f.get("file", "").lower()]
        return sorted(results, key=lambda x: SEVERITY_ORDER.get(x.get("severity", "P3"), 5))

    def findings_count(self) -> dict[str, int]:
        """Zählung pro Severity."""
        counts = {s: 0 for s in SEVERITY_VALUES}
        for f in self.findings:
            sev = f.get("severity", "P3")
            if sev in counts:
                counts[sev] += 1
        return counts

    def close(self, summary: str = "") -> None:
        """Session als abgeschlossen markieren."""
        self.status = "closed"
        self.closed_at = datetime.now(timezone.utc).isoformat()
        self.summary = summary


# ======================================================================
# Session Persistenz
# ======================================================================

def _ensure_dirs():
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    PATTERNS_DIR.mkdir(parents=True, exist_ok=True)


# ======================================================================
# Custom Pattern Persistenz (v0.6.0)
# ======================================================================

def _pattern_hash(name: str, scan_query: str) -> str:
    """Deterministischer Hash für Deduplizierung via name + scan_query."""
    return hashlib.md5(f"{name}::{scan_query}".encode()).hexdigest()


def _next_custom_id() -> str:
    """Auto-ID: höchste existierende CUSTOM_XXX + 1."""
    highest = 0
    for pid in PATTERNS_BY_ID:
        if pid.startswith(CUSTOM_PREFIX):
            try:
                num = int(pid[len(CUSTOM_PREFIX):])
                if num > highest:
                    highest = num
            except ValueError:
                continue
    return f"{CUSTOM_PREFIX}{highest + 1:03d}"


def _validate_custom_pattern(data: dict) -> Optional[str]:
    """Validierung eines Custom Pattern. Returns error string or None."""
    if not data.get("name", "").strip():
        return "name ist erforderlich"
    scan_type = data.get("scan_type", "")
    if scan_type not in ("grep", "code_search", "code_diagnostics"):
        return "scan_type muss eine sein von: grep, code_search, code_diagnostics"
    if scan_type in ("grep", "code_search") and not data.get("scan_query", "").strip():
        return "scan_query ist erforderlich für grep/code_search"
    sev = data.get("severity", "P2").upper()
    if sev not in SEVERITY_VALUES:
        return f"Ungültige severity: {sev}"
    cat = data.get("category", "")
    if cat and cat not in FINDING_CATEGORIES and cat not in ("custom",):
        return f"Ungültige category: {cat}"
    return None


def save_custom_pattern(pattern_data: dict) -> str:
    """Neues Custom Pattern speichern oder existierendes updaten.

    Deduplizierung: name + scan_query (via Hash).
    Auto-ID: CUSTOM_001, CUSTOM_002, ...
    Max 500 Custom Patterns.
    Atomischer Write via tempfile + rename.

    Returns:
        pattern_id (neu oder existierend)
    """
    _ensure_dirs()

    # Validierung
    err = _validate_custom_pattern(pattern_data)
    if err:
        raise ValueError(err)

    name = pattern_data["name"].strip()
    scan_query = pattern_data.get("scan_query", "").strip()
    new_hash = _pattern_hash(name, scan_query)

    # Bestehende Patterns laden
    existing = _load_custom_patterns_raw()

    # Deduplizierung: Prüfen ob name+scan_query bereits existiert
    for i, ep in enumerate(existing):
        ep_hash = _pattern_hash(
            ep.get("name", ""),
            ep.get("scan_query", ""),
        )
        if ep_hash == new_hash:
            # Update existierendes Pattern
            pid = ep["pattern_id"]
            for k, v in pattern_data.items():
                if k not in ("pattern_id", "created_at", "source"):
                    ep[k] = v
            ep["updated_at"] = datetime.now(timezone.utc).isoformat()
            _atomic_write_json(CUSTOM_PATTERNS_FILE, existing)

            # In-Memory-Patterns updaten
            if pid in PATTERNS_BY_ID:
                old_p = PATTERNS_BY_ID[pid]
                for k, v in ep.items():
                    setattr(old_p, k, v) if hasattr(old_p, k) else None
            return pid

    # Neues Pattern
    if len(existing) >= MAX_CUSTOM_PATTERNS:
        raise ValueError(f"Maximum von {MAX_CUSTOM_PATTERNS} Custom Patterns erreicht")

    pid = _next_custom_id()
    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "pattern_id": pid,
        "name": name,
        "category": pattern_data.get("category", "other"),
        "severity": pattern_data.get("severity", "P2").upper(),
        "description": pattern_data.get("description", ""),
        "scan_type": pattern_data.get("scan_type", ""),
        "scan_query": scan_query,
        "scan_file_glob": pattern_data.get("scan_file_glob", ""),
        "scan_language": pattern_data.get("scan_language", ""),
        "fix_description": pattern_data.get("fix_description", ""),
        "false_positive_notes": pattern_data.get("false_positive_notes", ""),
        "source": "custom",
        "source_session": pattern_data.get("source_session", ""),
        "source_project": pattern_data.get("source_project", ""),
        "source_finding_id": pattern_data.get("source_finding_id", ""),
        "match_count": pattern_data.get("match_count", 0),
        "tags": pattern_data.get("tags", []),
        "created_at": now,
        "updated_at": now,
    }
    existing.append(entry)
    _atomic_write_json(CUSTOM_PATTERNS_FILE, existing)

    # In init_patterns-merged Version synchron halten
    _sync_custom_pattern_to_memory(entry)
    return pid


def _sync_custom_pattern_to_memory(entry: dict) -> None:
    """Custom Pattern in die In-Memory PATTERNS_* Dictionaries mergen.
    Wird von save_custom_pattern() und init_patterns() aufgerufen.
    """
    from . import bughunt_patterns as bp
    p = bp.BugPattern.from_dict(entry) if hasattr(bp, 'BugPattern') else _dict_to_pattern(entry)
    # In ALL_PATTERNS (nur wenn noch nicht vorhanden)
    if not any(getattr(x, 'pattern_id', '') == p.pattern_id for x in ALL_PATTERNS):
        ALL_PATTERNS.append(p)
    PATTERNS_BY_ID[p.pattern_id] = p
    cat = p.category or "other"
    if cat not in PATTERNS_BY_CATEGORY:
        PATTERNS_BY_CATEGORY[cat] = []
    if not any(x.pattern_id == p.pattern_id for x in PATTERNS_BY_CATEGORY[cat]):
        PATTERNS_BY_CATEGORY[cat].append(p)
    # Auch in 'custom' Kategorie
    if "custom" not in PATTERNS_BY_CATEGORY:
        PATTERNS_BY_CATEGORY["custom"] = []
    if not any(x.pattern_id == p.pattern_id for x in PATTERNS_BY_CATEGORY["custom"]):
        PATTERNS_BY_CATEGORY["custom"].append(p)


def _dict_to_pattern(d: dict) -> object:
    """Fallback: dict zu pattern-ähnlichem Objekt wenn BugPattern nicht importierbar."""
    class _P:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)
    return _P(**d)


def _load_custom_patterns_raw() -> list[dict]:
    """Raw aus JSON-Datei laden (als list[dict])."""
    if not CUSTOM_PATTERNS_FILE.exists():
        return []
    try:
        data = json.loads(CUSTOM_PATTERNS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Custom patterns file corrupted, starting fresh: %s", e)
        # Backup der korrupten Datei
        try:
            backup = CUSTOM_PATTERNS_FILE.with_suffix(".json.bak")
            CUSTOM_PATTERNS_FILE.rename(backup)
        except OSError:
            pass
        return []


def load_custom_patterns() -> list[dict]:
    """Custom Patterns laden und BugPattern-Objekte mergen.

    Returns:
        List of pattern dicts (für BugPattern.from_dict).
    """
    raw = _load_custom_patterns_raw()
    return raw


def delete_custom_pattern(pattern_id: str) -> bool:
    """Custom Pattern löschen.

    Nur Patterns mit CUSTOM_-Prefix sind löschbar.
    Entfernt auch aus In-Memory PATTERNS_BY_ID / PATTERNS_BY_CATEGORY / ALL_PATTERNS.
    """
    if not pattern_id.startswith(CUSTOM_PREFIX):
        raise ValueError(f"Kann Built-in Pattern {pattern_id} nicht löschen. "
                         f"Nur {CUSTOM_PREFIX}XXX Patterns sind löschbar.")

    existing = _load_custom_patterns_raw()
    before = len(existing)
    existing = [e for e in existing if e.get("pattern_id") != pattern_id]
    if len(existing) == before:
        return False  # Nicht gefunden

    _atomic_write_json(CUSTOM_PATTERNS_FILE, existing)

    # Aus In-Memory entfernen
    PATTERNS_BY_ID.pop(pattern_id, None)
    ALL_PATTERNS[:] = [p for p in ALL_PATTERNS if getattr(p, 'pattern_id', '') != pattern_id]
    for cat in list(PATTERNS_BY_CATEGORY.keys()):
        PATTERNS_BY_CATEGORY[cat] = [
            p for p in PATTERNS_BY_CATEGORY[cat]
            if getattr(p, 'pattern_id', '') != pattern_id
        ]
    return True


def list_custom_patterns() -> list[dict]:
    """Alle Custom Patterns als Dicts zurückgeben."""
    return [
        p.to_dict() if hasattr(p, 'to_dict') else p
        for p in ALL_PATTERNS
        if getattr(p, 'source', 'built-in') == 'custom'
    ]


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
# In-Memory Session Tracker (für Hook-Integration)
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
    return _tracker


# ======================================================================
# Response Helpers
# ======================================================================

def _ok(data: dict) -> str:
    """Success response — delegiert an fmt_ok."""
    data.setdefault("status", "ok")
    return fmt_ok(data)


def _err(msg: str) -> str:
    """Error response — delegiert an fmt_err."""
    return fmt_err(msg)


# ======================================================================
# Path Validation
# ======================================================================

_TRAVERSAL = re.compile(r"(?:^|/|\\\\)\.{2,}(?:/|\\\\)|%2e%2e", re.I)
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
# Markdown Report Generator (für bug_hunt_report)
# ======================================================================

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

    # Findings gruppieren
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
    """Ein Finding als Markdown-Zeilen."""
    return [
        f"### [{f.get('severity', 'P2')}] {f.get('title', 'Untitled')}",
        "",
        f"- **ID:** `{f.get('id', '?')}`",
        f"- **File:** {f.get('file', '?')}:{f.get('line', 0)}",
        f"- **Status:** {f.get('status', 'open')}",
        f"- **Pattern:** {f.get('pattern_id', '-')}",
        "",
        f"{f.get('description', '')}",
        "",
        "```",
        f"{f.get('evidence', '')}",
        "```",
        "",
        f"**Fix:** {f.get('suggested_fix', '-')}",
        "",
        "---",
        "",
    ]


# ======================================================================
# Pattern Library — geladen von bughunt_patterns
# ======================================================================

# Forward declarations — werden via init_patterns() befüllt
PATTERNS_BY_ID: dict = {}
PATTERNS_BY_CATEGORY: dict = {}
ALL_PATTERNS: list = []


def init_patterns() -> None:
    """Load all patterns from bughunt_patterns module plus custom patterns.

    Called once at plugin registration time. Populates the forward
    declarations so all core.* pattern functions work.
    After loading built-in patterns, merges any custom patterns
    from data/patterns/custom_patterns.json.
    """
    try:
        from . import bughunt_patterns as bp  # Hermes Runtime (Package)
    except ImportError:
        import bughunt_patterns as bp  # pytest (top-level Import)
    PATTERNS_BY_ID.clear()
    PATTERNS_BY_ID.update(bp.PATTERNS_BY_ID)
    PATTERNS_BY_CATEGORY.clear()
    PATTERNS_BY_CATEGORY.update(bp.PATTERNS_BY_CATEGORY)
    ALL_PATTERNS.clear()
    ALL_PATTERNS.extend(bp.ALL_PATTERNS)

    # Merge Custom Patterns aus JSON-Datei (v0.6.0)
    try:
        custom_data = load_custom_patterns()
        for entry in custom_data:
            _sync_custom_pattern_to_memory(entry)
    except Exception as e:
        logger.debug("init_patterns: custom patterns skipped (%s)", e)


def get_pattern(pattern_id: str):
    return PATTERNS_BY_ID.get(pattern_id)


def get_patterns_by_category(category: str) -> list:
    return PATTERNS_BY_CATEGORY.get(category, [])


def get_patterns_by_ids(pattern_ids: list[str]) -> list:
    return [p for p in (get_pattern(pid) for pid in pattern_ids) if p]


def list_categories() -> list[dict]:
    return [
        {"category": cat, "count": len(patterns)}
        for cat, patterns in sorted(PATTERNS_BY_CATEGORY.items())
    ]


def list_all_patterns() -> list[dict]:
    return [p.to_dict() for p in ALL_PATTERNS]


# ======================================================================
# Auto-Init — Patterns laden beim ersten Import (Fallback)
# ======================================================================
# Wird von __init__.py via core.init_patterns() aufgerufen.
# Zusätzlich hier als Modul-Level-Aufruf, damit Patterns auch dann
# geladen werden, wenn bughunt_core ausserhalb des Package-Kontexts
# importiert wird (z.B. via importlib).
# try/except: sicher ausserhalb des Packages (relativer Import scheitert).
# ======================================================================
try:
    init_patterns()
except (ImportError, AttributeError, ValueError) as e:
    logger.debug("init_patterns failed: %s", e)
