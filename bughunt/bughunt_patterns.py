"""Bug-Hunt Pattern Library — Functions (Daten in data/patterns_data.py)."""
from typing import Optional

from scout.bughunt.data.patterns_data import (
    ALL_PATTERNS,
    PATTERNS_BY_CATEGORY,
    PATTERNS_BY_ID,
    PRESETS,
    BugPattern,
)


def resolve_preset(preset_name: str) -> list[str]:
    """Löst ein Preset in Pattern-IDs auf.

    Args:
        preset_name: Name des Presets (z.B. 'medusa-full').

    Returns:
        Liste von Pattern-IDs (z.B. ['A001', 'A002', 'S001', ...]).
    """
    preset = PRESETS.get(preset_name)
    if not preset:
        raise ValueError(
            f"Unbekanntes Preset: {preset_name}. "
            f"Verfügbar: {', '.join(sorted(PRESETS.keys()))}"
        )

    pattern_ids: list[str] = []
    seen: set[str] = set()

    # 1. Kategorien auflösen
    for cat in preset.get("categories", []):
        for p in PATTERNS_BY_CATEGORY.get(cat, []):
            if p.pattern_id not in seen:
                pattern_ids.append(p.pattern_id)
                seen.add(p.pattern_id)

    return pattern_ids


def list_presets() -> list[dict]:
    """Listet alle verfügbaren Presets mit Beschreibung und Pattern-Count."""
    result = []
    for name, data in sorted(PRESETS.items()):
        ids = resolve_preset(name)
        result.append({
            "name": name,
            "description": data["description"],
            "pattern_count": len(ids),
            "categories": data.get("categories", []),
        })
    return result


def get_pattern(pattern_id: str) -> Optional[BugPattern]:
    return PATTERNS_BY_ID.get(pattern_id)


def get_patterns_by_category(category: str) -> list[BugPattern]:
    return PATTERNS_BY_CATEGORY.get(category, [])


def get_patterns_by_ids(pattern_ids: list[str]) -> list[BugPattern]:
    return [p for p in (get_pattern(pid) for pid in pattern_ids) if p]


def list_categories() -> list[dict]:
    return [
        {"category": cat, "count": len(patterns)}
        for cat, patterns in sorted(PATTERNS_BY_CATEGORY.items())
    ]


def list_all_patterns() -> list[dict]:
    return [p.to_dict() for p in ALL_PATTERNS]
