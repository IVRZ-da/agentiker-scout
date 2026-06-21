"""Shared Pattern Repository — single source of truth for all 3 domains.

Konsolidiert:
- patterns_core.py aus ~/.hermes/patterns/ (shared_patterns.json)
- bughunt data/patterns/custom_patterns.json (lokal — ENTFÄLLT)
- analysis tools/base.py _run_shared_patterns (Pattern-Ausführung)
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("scout.patterns")

PATTERNS_DIR = Path.home() / ".hermes" / "patterns"
SHARED_PATTERNS_FILE = PATTERNS_DIR / "shared_patterns.json"
PATTERNS_CORE_MIGRATED = PATTERNS_DIR / ".scout_migrated"

# ─── Lazy init ────────────────────────────────────────────────────────────

def _ensure_dirs() -> None:
    PATTERNS_DIR.mkdir(parents=True, exist_ok=True)

def _load_patterns() -> list[dict]:
    """Load all shared patterns from disk."""
    _ensure_dirs()
    if not SHARED_PATTERNS_FILE.exists():
        return []
    try:
        data = json.loads(SHARED_PATTERNS_FILE.read_text())
        return data if isinstance(data, list) else data.get("patterns", [])
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("scout.patterns: Fehler beim Laden: %s", e)
        return []

def _save_patterns(patterns: list[dict]) -> None:
    """Save all shared patterns to disk."""
    _ensure_dirs()
    SHARED_PATTERNS_FILE.write_text(
        json.dumps(patterns, ensure_ascii=False, indent=2)
    )

# ─── Public API ──────────────────────────────────────────────────────────

def save_pattern(pattern_data: dict) -> str:
    """Save a pattern to the shared repository.

    Args:
        pattern_data: Dict with pattern_id, name, description, scan_pattern, etc.

    Returns:
        Pattern ID (existing or newly generated).
    """
    patterns = _load_patterns()
    pid = pattern_data.get("pattern_id", "")

    if pid:
        # Update existing
        for i, p in enumerate(patterns):
            if p.get("pattern_id") == pid:
                patterns[i] = pattern_data
                break
        else:
            patterns.append(pattern_data)
    else:
        # Generate new ID (P001, P002, ...)
        existing_ids = {p.get("pattern_id", "") for p in patterns}
        counter = 1
        while f"P{counter:03d}" in existing_ids:
            counter += 1
        pid = f"P{counter:03d}"
        pattern_data["pattern_id"] = pid
        pattern_data["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        patterns.append(pattern_data)

    _save_patterns(patterns)
    logger.debug("scout.patterns: Pattern %s gespeichert", pid)
    return pid


def get_pattern(pattern_id: str) -> Optional[dict]:
    """Get a single pattern by ID."""
    patterns = _load_patterns()
    for p in patterns:
        if p.get("pattern_id") == pattern_id:
            return p
    return None


def get_patterns_for_analysis(scan_language: str = "") -> list[dict]:
    """Get all patterns applicable for analysis (security, deadcode scans).

    Args:
        scan_language: Optional language filter (python, typescript, go).

    Returns:
        List of pattern dicts with scan_pattern, category, language, etc.
    """
    patterns = _load_patterns()
    if not scan_language:
        return patterns

    lang_map = {
        "python": {"py"},
        "typescript": {"ts", "tsx", "js", "jsx"},
        "go": {"go"},
        "rust": {"rs"},
    }
    valid_exts = lang_map.get(scan_language, set())

    return [
        p for p in patterns
        if p.get("scan_language") == scan_language
        or _glob_matches_language(p.get("scan_file_glob", ""), valid_exts)
    ]


def _glob_matches_language(glob: str, valid_exts: set[str]) -> bool:
    """Check if a file glob matches a language's extensions."""
    import fnmatch
    for ext in valid_exts:
        if fnmatch.fnmatch(glob, f"*{ext}") or fnmatch.fnmatch(glob, f"*.{ext}"):
            return True
        if ext in glob:  # fallback for list globs like **/*.{ts,tsx}
            return True
    return False


def increment_match_count(pattern_id: str) -> None:
    """Increment match count for a pattern (tracking stats)."""
    patterns = _load_patterns()
    for p in patterns:
        if p.get("pattern_id") == pattern_id:
            p["match_count"] = p.get("match_count", 0) + 1
            break
    _save_patterns(patterns)


def count_patterns() -> int:
    """Count total patterns in repository."""
    return len(_load_patterns())


def list_all_patterns() -> list[dict]:
    """List all patterns with metadata."""
    return _load_patterns()


def get_patterns_by_category(category: str) -> list[dict]:
    """Get patterns filtered by category."""
    return [p for p in _load_patterns() if p.get("category") == category]


def delete_pattern(pattern_id: str) -> bool:
    """Delete a pattern by ID."""
    patterns = _load_patterns()
    before = len(patterns)
    patterns = [p for p in patterns if p.get("pattern_id") != pattern_id]
    if len(patterns) < before:
        _save_patterns(patterns)
        return True
    return False


def migrate_bughunt_custom_patterns() -> int:
    """Migrate custom patterns from bughunt's local store into shared repository.

    Called once during scout activation.
    """
    bughunt_custom = (
        Path.home() / ".hermes" / "plugins" / "bughunt" / "data" / "patterns" / "custom_patterns.json"
    )
    if not bughunt_custom.exists():
        return 0

    if PATTERNS_CORE_MIGRATED.exists():
        return 0

    try:
        custom_data = json.loads(bughunt_custom.read_text())
        if not isinstance(custom_data, list):
            custom_data = custom_data.get("patterns", [])

        existing_ids = {p.get("pattern_id") for p in _load_patterns()}
        migrated = 0
        for pat in custom_data:
            pid = pat.get("pattern_id")
            if pid and pid not in existing_ids:
                save_pattern(pat)
                migrated += 1

        PATTERNS_CORE_MIGRATED.write_text(
            json.dumps({"migrated": migrated, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        )
        logger.info("scout.patterns: %d custom patterns migriert", migrated)
        return migrated
    except Exception as e:
        logger.warning("scout.patterns: Migration fehlgeschlagen: %s", e)
        return 0
