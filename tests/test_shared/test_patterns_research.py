"""Tests für shared/patterns_research.py — Research-Patterns."""
from __future__ import annotations

import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def test_get_research_pattern_found():
    sys.path.insert(0, str(PLUGIN_ROOT.parent))
    from scout.shared.patterns_research import get_research_pattern

    pat = get_research_pattern("eu-cbd-regulation")
    assert pat is not None
    assert pat["name"] == "EU-Länder CBD-Regularien"


def test_get_research_pattern_not_found():
    sys.path.insert(0, str(PLUGIN_ROOT.parent))
    from scout.shared.patterns_research import get_research_pattern

    assert get_research_pattern("nonexistent") is None


def test_get_research_patterns_by_category():
    sys.path.insert(0, str(PLUGIN_ROOT.parent))
    from scout.shared.patterns_research import get_research_patterns_by_category

    result = get_research_patterns_by_category("news")
    assert len(result) >= 1
    assert result[0]["category"] == "news"


def test_get_research_patterns_by_category_not_found():
    sys.path.insert(0, str(PLUGIN_ROOT.parent))
    from scout.shared.patterns_research import get_research_patterns_by_category

    assert get_research_patterns_by_category("ghost") == []


def test_list_research_patterns():
    sys.path.insert(0, str(PLUGIN_ROOT.parent))
    from scout.shared.patterns_research import list_research_patterns

    result = list_research_patterns()
    assert len(result) >= 4  # Alle 4 Standard-Patterns
    for p in result:
        assert "id" in p and "name" in p and "category" in p


def test_list_categories():
    sys.path.insert(0, str(PLUGIN_ROOT.parent))
    from scout.shared.patterns_research import list_categories

    cats = list_categories()
    assert "regulatory" in cats
    assert "competitive" in cats
    assert "technical" in cats
    assert "news" in cats
