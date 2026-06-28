"""Bug-Hunt Pattern Library — geladen aus patterns_data.json.

Bietet dieselbe API wie vorher (ALL_PATTERNS, PATTERNS_BY_ID, PRESETS, ...)
aber die Pattern-Daten werden lazy aus patterns_data.json geladen.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CUSTOM_PREFIX = "CUSTOM_"

# Pfad zur JSON-Datendatei
_DATA_PATH = Path(__file__).resolve().parent / "patterns_data.json"


class BugPattern:
    """Ein Bug-Such-Pattern mit strukturierten Metadaten."""

    def __init__(self, pattern_id: str = "", name: str = "",
                 category: str = "", severity: str = "P2",
                 description: str = "", scan_type: str = "",
                 scan_query: str = "", scan_file_glob: str = "",
                 scan_language: str = "", fix_description: str = "",
                 false_positive_notes: str = "",
                 source: str = "built-in",
                 source_session: str = "", source_project: str = "",
                 source_finding_id: str = "",
                 match_count: int = 0, tags: Optional[list[str]] = None,
                 created_at: str = "", updated_at: str = "",
                 frameworks: Optional[list[str]] = None,
                 frameworks_required: bool = False):
        self.pattern_id = pattern_id
        self.name = name
        self.category = category
        self.severity = severity
        self.description = description
        self.scan_type = scan_type
        self.scan_query = scan_query
        self.scan_file_glob = scan_file_glob
        self.scan_language = scan_language
        self.fix_description = fix_description
        self.false_positive_notes = false_positive_notes
        self.source = source
        self.source_session = source_session
        self.source_project = source_project
        self.source_finding_id = source_finding_id
        self.match_count = match_count
        self.tags = tags or []
        now = datetime.now(timezone.utc).isoformat()
        self.created_at = created_at or now
        self.updated_at = updated_at or now
        self.frameworks = frameworks or []
        self.frameworks_required = frameworks_required

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "BugPattern":
        p = cls()
        for k, v in d.items():
            setattr(p, k, v)
        return p


# ─── Lazy Loader ────────────────────────────────────────────────────

def _load_patterns_json() -> dict:
    """Lade Pattern-Daten aus patterns_data.json (lazy)."""
    if not _DATA_PATH.exists():
        logger.warning("patterns_data.json nicht gefunden: %s", _DATA_PATH)
        return {}
    try:
        return json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("patterns_data.json konnte nicht geladen werden: %s", e)
        return {}


# ─── Globale Pattern-Listen (lazy initialisiert) ────────────────────

_SOURCE_DATA: dict | None = None


def _ensure_loaded() -> None:
    """Stelle sicher dass Pattern-Daten initialisiert sind."""
    global _SOURCE_DATA, ALL_PATTERNS, PATTERNS_BY_ID, PATTERNS_BY_CATEGORY, PRESETS, FRAMEWORK_MAP
    if _SOURCE_DATA is not None:
        return

    raw = _load_patterns_json()
    _SOURCE_DATA = raw

    # Globale Konstanten
    FRAMEWORK_MAP.update(raw.get("FRAMEWORK_MAP", {}))
    PRESETS.update(raw.get("PRESETS", {}))

    # Pattern-Listen aus JSON erzeugen
    all_patterns: list[BugPattern] = []
    for category_list_name, pattern_dicts in raw.get("patterns", {}).items():
        for pd in pattern_dicts:
            bp = BugPattern.from_dict(pd)
            all_patterns.append(bp)

    ALL_PATTERNS.clear()
    ALL_PATTERNS.extend(all_patterns)

    PATTERNS_BY_ID.clear()
    for p in ALL_PATTERNS:
        PATTERNS_BY_ID[p.pattern_id] = p

    PATTERNS_BY_CATEGORY.clear()
    for p in ALL_PATTERNS:
        PATTERNS_BY_CATEGORY.setdefault(p.category, []).append(p)


# ─── Globale Collections (Module-Level für Rückwärtskompatibilität) ──

ALL_PATTERNS: list[BugPattern] = []
PATTERNS_BY_ID: dict[str, BugPattern] = {}
PATTERNS_BY_CATEGORY: dict[str, list[BugPattern]] = {}
FRAMEWORK_MAP: dict[str, list[str]] = {}
PRESETS: dict[str, dict] = {}
