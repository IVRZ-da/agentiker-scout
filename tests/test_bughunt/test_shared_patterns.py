"""Tests für das Shared Pattern Repository (scout/shared/patterns.py).

MIGRIERT AUS: scout/tests/test_e2e/test_e2e_patterns.py
Grund: war als E2E-Test markiert (E2E_TEST=1) obwohl reine Unit-Tests.
Enthält CRUD-Tests für save_pattern, get_pattern, delete_pattern
sowie list_research_patterns (aus scout/shared/patterns_research.py).
"""

import pytest

# ---------------------------------------------------------------------------
# shared.patterns CRUD
# ---------------------------------------------------------------------------


class TestSharedPatterns:
    """Save, Get, Delete auf shared.patterns."""

    def test_pattern_save_and_retrieve(self):
        """Pattern speichern und via get_pattern/delete_pattern abrufen/löschen."""
        from scout.shared.patterns import save_pattern, get_pattern, delete_pattern

        pid = save_pattern({
            "name": "Test Pattern",
            "description": "Created during unit test",
            "category": "code-quality",
            "severity": "P2",
            "scan_type": "grep",
            "scan_query": "test.*pattern",
            "scan_file_glob": "**/*.py",
            "scan_language": "python",
        })
        assert pid is not None

        retrieved = get_pattern(pid)
        assert retrieved is not None
        assert retrieved.get("name") == "Test Pattern"

        delete_pattern(pid)
        assert get_pattern(pid) is None

    def test_get_patterns_for_analysis_returns_list(self):
        """get_patterns_for_analysis gibt Liste zurück (kann leer sein)."""
        from scout.shared.patterns import get_patterns_for_analysis
        patterns = get_patterns_for_analysis()
        assert isinstance(patterns, list)

    def test_delete_nonexistent_pattern(self):
        """Löschen eines nicht-existierenden Patterns verursacht keinen Fehler."""
        from scout.shared.patterns import delete_pattern
        # Sollte keinen Fehler werfen
        delete_pattern("nonexistent_pattern_id_xyz")


# ---------------------------------------------------------------------------
# shared.patterns_research
# ---------------------------------------------------------------------------


class TestResearchPatterns:
    """List-Operationen auf den Research-Patterns."""

    def test_list_research_patterns(self):
        """Research-Patterns auflisten."""
        from scout.shared.patterns_research import list_research_patterns
        patterns = list_research_patterns()
        assert len(patterns) >= 4
        categories = {p["category"] for p in patterns}
        assert "regulatory" in categories

    def test_research_pattern_has_required_fields(self):
        """Jedes Research-Pattern hat name, category, description."""
        from scout.shared.patterns_research import list_research_patterns
        patterns = list_research_patterns()
        required = {"name", "category", "description"}
        for p in patterns:
            assert required.issubset(p.keys()), f"Fehlende Felder in: {p.get('name', '?')}"
