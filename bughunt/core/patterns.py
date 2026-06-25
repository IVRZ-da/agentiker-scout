"""Pattern CRUD — custom pattern persistence and built-in pattern library."""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from scout.bughunt import bughunt_patterns as bp
from scout.bughunt.core.model import (
    CUSTOM_PATTERNS_FILE,
    CUSTOM_PREFIX,
    MAX_CUSTOM_PATTERNS,
    PATTERNS_DIR,
    PLUGIN_DIR,
)

logger = logging.getLogger(__name__)

# ======================================================================
# Konstanten
# ======================================================================

SEVERITY_VALUES = ["P0", "P1", "P2", "P3", "INFO"]
FINDING_CATEGORIES = [
    "security",
    "code-quality",
    "typescript",
    "react-next",
    "admin-ui",
    "performance",
    "testing",
    "dependency",
    "database",
    "other",
]

DATA_DIR = PLUGIN_DIR / "data"
SESSIONS_DIR = DATA_DIR / "sessions"

# ======================================================================
# In-Memory Pattern Registry — wird via init_patterns() befüllt
# ======================================================================

PATTERNS_BY_ID: dict = {}
PATTERNS_BY_CATEGORY: dict = {}
ALL_PATTERNS: list = []

# ======================================================================
# Hilfsfunktionen (Persistenz)
# ======================================================================


def _ensure_dirs() -> None:
    """Ensure required directories exist."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    PATTERNS_DIR.mkdir(parents=True, exist_ok=True)


def _atomic_write_json(path: Path, data: list) -> None:
    """Atomischer JSON-Write via tempfile + rename."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)


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
                num = int(pid[len(CUSTOM_PREFIX) :])
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
    p = (
        bp.BugPattern.from_dict(entry)
        if hasattr(bp, "BugPattern")
        else _dict_to_pattern(entry)
    )
    # In ALL_PATTERNS (nur wenn noch nicht vorhanden)
    if not any(getattr(x, "pattern_id", "") == p.pattern_id for x in ALL_PATTERNS):
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
        raise ValueError(
            f"Kann Built-in Pattern {pattern_id} nicht löschen. "
            f"Nur {CUSTOM_PREFIX}XXX Patterns sind löschbar."
        )

    existing = _load_custom_patterns_raw()
    before = len(existing)
    existing = [e for e in existing if e.get("pattern_id") != pattern_id]
    if len(existing) == before:
        return False  # Nicht gefunden

    _atomic_write_json(CUSTOM_PATTERNS_FILE, existing)

    # Aus In-Memory entfernen
    PATTERNS_BY_ID.pop(pattern_id, None)
    ALL_PATTERNS[:] = [
        p for p in ALL_PATTERNS if getattr(p, "pattern_id", "") != pattern_id
    ]
    for cat in list(PATTERNS_BY_CATEGORY.keys()):
        PATTERNS_BY_CATEGORY[cat] = [
            p
            for p in PATTERNS_BY_CATEGORY[cat]
            if getattr(p, "pattern_id", "") != pattern_id
        ]
    return True


def list_custom_patterns() -> list[dict]:
    """Alle Custom Patterns als Dicts zurückgeben."""
    return [
        p.to_dict() if hasattr(p, "to_dict") else p
        for p in ALL_PATTERNS
        if getattr(p, "source", "built-in") == "custom"
    ]


# ======================================================================
# Pattern Library — geladen von bughunt_patterns
# ======================================================================


def init_patterns() -> None:
    """Load all patterns from bughunt_patterns module plus custom patterns.

    Called once at plugin registration time. Populates the forward
    declarations so all core.* pattern functions work.
    After loading built-in patterns, merges any custom patterns
    from data/patterns/custom_patterns.json.
    """
    try:
        from scout.bughunt import bughunt_patterns as bp2
    except ImportError:
        import bughunt_patterns as bp2  # pytest (top-level Import)

    PATTERNS_BY_ID.clear()
    PATTERNS_BY_ID.update(bp2.PATTERNS_BY_ID)
    PATTERNS_BY_CATEGORY.clear()
    PATTERNS_BY_CATEGORY.update(bp2.PATTERNS_BY_CATEGORY)
    ALL_PATTERNS.clear()
    ALL_PATTERNS.extend(bp2.ALL_PATTERNS)

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
