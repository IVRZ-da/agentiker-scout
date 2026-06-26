"""Tests für scout.bughunt.bughunt_patterns — Pattern-Library Funktionen.

Nutzt patch.object auf dem bughunt_patterns-Modul, weil
from ... import die Referenz beim Import kopiert.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from scout.bughunt import bughunt_patterns as bp

# ─── Mock BugPattern ───────────────────────────────────────────────────


class MockBugPattern:
    """Minimaler BugPattern-Ersatz für Tests."""
    def __init__(self, pattern_id="", name="", category="", severity="P2",
                 description="", tags=None, frameworks=None):
        self.pattern_id = pattern_id
        self.name = name
        self.category = category
        self.severity = severity
        self.description = description
        self.tags = tags or []
        self.frameworks = frameworks or []

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "category": self.category,
            "severity": self.severity,
            "description": self.description,
            "tags": self.tags,
            "frameworks": self.frameworks,
        }


# ─── Mock Data ─────────────────────────────────────────────────────────

_P1 = MockBugPattern(pattern_id="S001", name="execSync",
                      category="security", severity="P0",
                      description="Test pattern 1")
_P2 = MockBugPattern(pattern_id="C001", name="Silent Catch",
                      category="code-quality", severity="P1",
                      description="Test pattern 2")
_P3 = MockBugPattern(pattern_id="R001", name="useEffect Cleanup",
                      category="react-next", severity="P1",
                      description="Test pattern 3")
_P4 = MockBugPattern(pattern_id="A001", name="Delete-Stub",
                      category="medusa-admin-ui", severity="P1",
                      description="Test pattern 4")

_MOCK_PRESETS = {
    "medusa-full": {
        "description": "Kompletter Medusa-Stack",
        "categories": ["security", "code-quality", "medusa-admin-ui"],
    },
    "medusa-admin": {
        "description": "Nur Admin UI",
        "categories": ["medusa-admin-ui"],
    },
    "security-only": {
        "description": "Nur Security",
        "categories": ["security"],
    },
    "empty-preset": {
        "description": "Ohne Kategorien",
        "categories": [],
    },
}

_MOCK_BY_ID = {"S001": _P1, "C001": _P2, "R001": _P3, "A001": _P4}
_MOCK_BY_CAT = {
    "security": [_P1],
    "code-quality": [_P2],
    "react-next": [_P3],
    "medusa-admin-ui": [_P4],
}
_MOCK_ALL = [_P1, _P2, _P3, _P4]


# ─── Fixture ───────────────────────────────────────────────────────────


@pytest.fixture
def with_mocks():
    """Patched Module-Level Referenzen: PRESETS, PATTERNS_BY_ID, etc."""
    with (
        patch.object(bp, "PRESETS", _MOCK_PRESETS),
        patch.object(bp, "PATTERNS_BY_ID", _MOCK_BY_ID),
        patch.object(bp, "PATTERNS_BY_CATEGORY", _MOCK_BY_CAT),
        patch.object(bp, "ALL_PATTERNS", _MOCK_ALL),
        patch.object(bp, "BugPattern", MockBugPattern),
    ):
        yield


# ======================================================================
# resolve_preset
# ======================================================================


class TestResolvePreset:
    """resolve_preset(): Löst Preset in Pattern-IDs auf."""

    def test_valid_preset_returns_ids(self, with_mocks):
        ids = bp.resolve_preset("medusa-full")
        assert ids == ["S001", "C001", "A001"]

    def test_deduplicates(self, with_mocks):
        ids = bp.resolve_preset("medusa-full")
        assert len(ids) == len(set(ids))

    def test_unknown_preset_raises_valueerror(self, with_mocks):
        with pytest.raises(ValueError) as exc:
            bp.resolve_preset("does-not-exist")
        msg = str(exc.value)
        assert "Unbekanntes Preset" in msg
        assert "does-not-exist" in msg
        for name in ("medusa-full", "medusa-admin", "security-only", "empty-preset"):
            assert name in msg

    def test_empty_preset_returns_empty_list(self, with_mocks):
        ids = bp.resolve_preset("empty-preset")
        assert ids == []

    def test_preset_single_category(self, with_mocks):
        ids = bp.resolve_preset("medusa-admin")
        assert ids == ["A001"]

    def test_preset_security_only(self, with_mocks):
        ids = bp.resolve_preset("security-only")
        assert ids == ["S001"]


# ======================================================================
# list_presets
# ======================================================================


class TestListPresets:
    """list_presets(): Listet alle verfügbaren Presets."""

    def test_returns_sorted(self, with_mocks):
        presets = bp.list_presets()
        names = [p["name"] for p in presets]
        assert names == ["empty-preset", "medusa-admin", "medusa-full", "security-only"]

    def test_has_all_fields(self, with_mocks):
        presets = bp.list_presets()
        p = next(x for x in presets if x["name"] == "medusa-full")
        assert p["description"] == "Kompletter Medusa-Stack"
        assert p["pattern_count"] == 3
        assert p["categories"] == ["security", "code-quality", "medusa-admin-ui"]

    def test_empty_preset_count(self, with_mocks):
        presets = bp.list_presets()
        p = next(x for x in presets if x["name"] == "empty-preset")
        assert p["pattern_count"] == 0


# ======================================================================
# get_pattern
# ======================================================================


class TestGetPattern:
    """get_pattern(): Holt ein Pattern per ID."""

    def test_found(self, with_mocks):
        p = bp.get_pattern("S001")
        assert p is not None
        assert p.pattern_id == "S001"
        assert p.name == "execSync"

    def test_not_found(self, with_mocks):
        assert bp.get_pattern("X999") is None

    def test_empty_string(self, with_mocks):
        assert bp.get_pattern("") is None


# ======================================================================
# get_patterns_by_category
# ======================================================================


class TestGetPatternsByCategory:
    """get_patterns_by_category(): Patterns einer Kategorie."""

    def test_existing(self, with_mocks):
        pats = bp.get_patterns_by_category("security")
        assert len(pats) == 1
        assert pats[0].pattern_id == "S001"

    def test_nonexistent_returns_empty(self, with_mocks):
        assert bp.get_patterns_by_category("nonexistent") == []

    def test_empty_string(self, with_mocks):
        assert bp.get_patterns_by_category("") == []


# ======================================================================
# get_patterns_by_ids
# ======================================================================


class TestGetPatternsByIds:
    """get_patterns_by_ids(): Holt mehrere Patterns per ID-Liste."""

    def test_all_existing(self, with_mocks):
        pats = bp.get_patterns_by_ids(["S001", "C001"])
        assert len(pats) == 2
        assert pats[0].pattern_id == "S001"

    def test_mixed_list(self, with_mocks):
        pats = bp.get_patterns_by_ids(["S001", "X999", "C001"])
        assert len(pats) == 2
        assert {p.pattern_id for p in pats} == {"S001", "C001"}

    def test_all_nonexistent_returns_empty(self, with_mocks):
        assert bp.get_patterns_by_ids(["X999", "Y888"]) == []

    def test_empty_list(self, with_mocks):
        assert bp.get_patterns_by_ids([]) == []

    def test_duplicate_ids(self, with_mocks):
        pats = bp.get_patterns_by_ids(["S001", "S001"])
        assert len(pats) == 2
        assert pats[0].pattern_id == "S001"
        assert pats[1].pattern_id == "S001"


# ======================================================================
# list_categories
# ======================================================================


class TestListCategories:
    """list_categories(): Listet alle Kategorien mit Count."""

    def test_sorted(self, with_mocks):
        cats = bp.list_categories()
        names = [c["category"] for c in cats]
        assert names == sorted(names)
        assert names == ["code-quality", "medusa-admin-ui", "react-next", "security"]

    def test_has_counts(self, with_mocks):
        cats = {c["category"]: c["count"] for c in bp.list_categories()}
        assert cats["security"] == 1

    def test_structure(self, with_mocks):
        for cat in bp.list_categories():
            assert "category" in cat
            assert "count" in cat


# ======================================================================
# list_all_patterns
# ======================================================================


class TestListAllPatterns:
    """list_all_patterns(): Alle Patterns als dict-Liste."""

    def test_returns_dicts(self, with_mocks):
        pats = bp.list_all_patterns()
        assert len(pats) == 4
        for p in pats:
            assert isinstance(p, dict)

    def test_has_ids(self, with_mocks):
        ids = {p["pattern_id"] for p in bp.list_all_patterns()}
        assert ids == {"S001", "C001", "R001", "A001"}

    def test_content(self, with_mocks):
        pats = bp.list_all_patterns()
        p = next(x for x in pats if x["pattern_id"] == "S001")
        assert p["name"] == "execSync"
        assert p["category"] == "security"
        assert p["severity"] == "P0"
