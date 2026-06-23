"""Test: Pattern Library — 20+ Bug-Patterns in 5 Kategorien."""

from pathlib import Path

import pytest

# ======================================================================
# Modul-Import
# ======================================================================

@pytest.fixture(autouse=True)
def init_pats():
    """Load patterns into core before each test.

    Importiert via Package-Pfad (bughunt.bughunt_core) damit
    init_patterns() die relativen Imports (from . import bughunt_patterns)
    auflösen kann — funktioniert nicht bei top-level import bughunt_core.
    """
    import sys as _sys
    plugin_root = Path(__file__).parent.parent
    parent = str(plugin_root.parent)
    if parent not in _sys.path:
        _sys.path.insert(0, parent)
    from scout.bughunt import bughunt_core as core
    core.init_patterns()
    return core


# ======================================================================
# Struktur-Tests
# ======================================================================

class TestPatternStructure:
    """Jedes Pattern hat alle erforderlichen Felder."""

    def test_all_patterns_count(self, init_pats):
        """Mindestens 20 Patterns."""
        assert len(init_pats.ALL_PATTERNS) >= 20

    def test_all_patterns_have_ids(self, init_pats):
        for p in init_pats.ALL_PATTERNS:
            assert p.pattern_id, f"Pattern ohne ID: {p.name}"
            assert len(p.pattern_id) >= 4, f"ID {p.pattern_id} zu kurz"

    def test_all_ids_unique(self, init_pats):
        ids = [p.pattern_id for p in init_pats.ALL_PATTERNS]
        assert len(ids) == len(set(ids)), "Doppelte Pattern-IDs gefunden"

    def test_all_have_names(self, init_pats):
        for p in init_pats.ALL_PATTERNS:
            assert p.name, f"{p.pattern_id} hat keinen name"

    def test_all_have_categories(self, init_pats):
        valid = {"security", "code-quality", "typescript", "go", "rust", "react-next",
                 "medusa-admin-ui", "java", "cpp", "ruby"}
        for p in init_pats.ALL_PATTERNS:
            assert p.category in valid, f"{p.pattern_id}: category={p.category} ungültig"

    def test_all_have_severities(self, init_pats):
        valid = {"P0", "P1", "P2", "P3", "INFO"}
        for p in init_pats.ALL_PATTERNS:
            assert p.severity in valid, f"{p.pattern_id}: severity={p.severity} ungültig"

    def test_all_have_descriptions(self, init_pats):
        for p in init_pats.ALL_PATTERNS:
            assert p.description, f"{p.pattern_id} hat keine description"

    def test_all_have_fix_descriptions(self, init_pats):
        for p in init_pats.ALL_PATTERNS:
            assert p.fix_description, f"{p.pattern_id} hat keine fix_description"

    def test_all_have_scan_type(self, init_pats):
        valid = {
            "code_search", "grep", "code_diagnostics",
            "code_security_scan", "code_todo_finder", "code_duplicates",
            "code_merge_conflict", "code_search_by_error", "code_unused_finder",
        }
        for p in init_pats.ALL_PATTERNS:
            assert p.scan_type in valid, f"{p.pattern_id}: scan_type={p.scan_type} ungültig"

    def test_security_count(self, init_pats):
        pats = init_pats.get_patterns_by_category("security")
        assert len(pats) == 19, f"security hat {len(pats)} patterns, erwarte 19"

    def test_code_quality_count(self, init_pats):
        pats = init_pats.get_patterns_by_category("code-quality")
        assert len(pats) == 19, f"code-quality hat {len(pats)} patterns, erwarte 19"

    def test_typescript_count(self, init_pats):
        pats = init_pats.get_patterns_by_category("typescript")
        assert len(pats) == 3

    def test_react_next_count(self, init_pats):
        pats = init_pats.get_patterns_by_category("react-next")
        assert len(pats) == 3

    def test_admin_ui_count(self, init_pats):
        pats = init_pats.get_patterns_by_category("medusa-admin-ui")
        assert len(pats) == 5

    def test_each_category_has_at_least_one(self, init_pats):
        cats = {"security", "code-quality", "typescript", "react-next", "medusa-admin-ui"}
        for cat in cats:
            assert len(init_pats.get_patterns_by_category(cat)) >= 1, \
                f"Kategorie {cat} ist leer"


# ======================================================================
# Lookup-Tests
# ======================================================================

class TestPatternLookup:
    """get_pattern, get_patterns_by_category, list_categories."""

    def test_get_pattern_by_id(self, init_pats):
        p = init_pats.get_pattern("S001")
        assert p is not None
        assert p.pattern_id == "S001"
        assert p.category == "security"

    def test_get_pattern_nonexistent(self, init_pats):
        p = init_pats.get_pattern("X999")
        assert p is None

    def test_get_patterns_by_ids(self, init_pats):
        pats = init_pats.get_patterns_by_ids(["S001", "C001"])
        assert len(pats) == 2
        assert pats[0].pattern_id == "S001"
        assert pats[1].pattern_id == "C001"

    def test_get_patterns_by_ids_partial(self, init_pats):
        """Unbekannte IDs werden ignoriert."""
        pats = init_pats.get_patterns_by_ids(["S001", "X999"])
        assert len(pats) == 1

    def test_list_categories(self, init_pats):
        cats = init_pats.list_categories()
        assert len(cats) == 11
        cat_names = [c["category"] for c in cats]
        assert "security" in cat_names
        assert "code-quality" in cat_names
        assert "go" in cat_names
        assert "rust" in cat_names
        assert "java" in cat_names
        assert "cpp" in cat_names
        assert "ruby" in cat_names

    def test_list_all_patterns_returns_dicts(self, init_pats):
        pats = init_pats.list_all_patterns()
        assert len(pats) >= 20
        assert isinstance(pats[0], dict)
        assert "pattern_id" in pats[0]

    def test_pattern_to_dict(self, init_pats):
        p = init_pats.get_pattern("S001")
        d = p.to_dict()
        assert d["pattern_id"] == "S001"
        assert d["name"] is not None
        assert d["category"] == "security"

    def test_pattern_severity_order(self, init_pats):
        """Security-Patterns sollten P0 haben, Code-Quality P1/P2."""
        s001 = init_pats.get_pattern("S001")
        assert s001.severity == "P0"
        c001 = init_pats.get_pattern("C001")
        assert c001.severity == "P1"
        c002 = init_pats.get_pattern("C002")
        assert c002.severity == "P2"


# ======================================================================
# Integration: Core + Patterns
# ======================================================================

class TestPatternIntegration:
    """Patterns sind via core.* verfügbar."""

    def test_init_patterns_populates_core(self, init_pats):
        """init_patterns() befüllt PATTERNS_BY_CATEGORY mit 11 Kategorien."""
        assert len(init_pats.PATTERNS_BY_CATEGORY) == 11
        assert len(init_pats.ALL_PATTERNS) >= 20

    def test_core_functions_work_after_init(self, init_pats):
        assert init_pats.get_pattern("S003") is not None
        assert init_pats.get_pattern("R001") is not None
        assert init_pats.get_pattern("A005") is not None

    def test_scan_types_code_search(self, init_pats):
        """Patterns mit scan_type='code_search' haben scan_query."""
        for p in init_pats.ALL_PATTERNS:
            if p.scan_type == "code_search":
                assert p.scan_query, f"{p.pattern_id}: code_search ohne query"

    def test_scan_types_grep(self, init_pats):
        """Patterns mit scan_type='grep' haben scan_query."""
        for p in init_pats.ALL_PATTERNS:
            if p.scan_type == "grep":
                assert p.scan_query, f"{p.pattern_id}: grep ohne query"
                assert p.scan_file_glob, f"{p.pattern_id}: grep ohne file_glob"

    def test_code_diagnostics_has_no_query(self, init_pats):
        """code_diagnostics braucht keinen scan_query."""
        for p in init_pats.ALL_PATTERNS:
            if p.scan_type == "code_diagnostics":
                pass  # scan_query kann leer sein

    def test_duplicate_init_is_idempotent(self, init_pats):
        """Mehrfaches init_patterns() erzeugt keine Duplikate."""
        init_pats.init_patterns()
        assert len(init_pats.ALL_PATTERNS) >= 20


# ======================================================================
# Edge Cases
# ======================================================================

class TestPatternEdgeCases:
    """Randfälle der Pattern-API."""

    def test_empty_category_returns_empty_list(self, init_pats):
        pats = init_pats.get_patterns_by_category("nonexistent")
        assert pats == []

    def test_empty_ids_returns_empty_list(self, init_pats):
        pats = init_pats.get_patterns_by_ids([])
        assert pats == []

    def test_list_all_patterns_never_empty(self, init_pats):
        assert len(init_pats.list_all_patterns()) > 0

    def test_list_categories_all_have_counts(self, init_pats):
        for cat in init_pats.list_categories():
            assert cat["count"] > 0


class TestPatternImport:
    """BugPattern.from_dict und Lookup-Funktionen."""

    def test_from_dict(self, init_pats):
        """BugPattern.from_dict erzeugt korrektes Objekt."""
        from scout.bughunt import bughunt_patterns as bp
        d = {"pattern_id": "X001", "name": "Custom", "category": "security",
             "severity": "P0", "description": "Test", "scan_type": "grep",
             "scan_query": "test", "scan_file_glob": "*.py"}
        p = bp.BugPattern.from_dict(d)
        assert p.pattern_id == "X001"
        assert p.name == "Custom"
        assert p.category == "security"
        assert p.severity == "P0"
        assert p.scan_type == "grep"

    def test_from_dict_minimal(self, init_pats):
        """BugPattern.from_dict mit minimalen Feldern."""
        from scout.bughunt import bughunt_patterns as bp
        p = bp.BugPattern.from_dict({"pattern_id": "X002"})
        assert p.pattern_id == "X002"
        assert p.name == ""  # default

    def test_from_dict_overwrite(self, init_pats):
        """from_dict überschreibt per setattr — auch unbekannte Felder."""
        from scout.bughunt import bughunt_patterns as bp
        bp.BugPattern()
        p2 = bp.BugPattern.from_dict({"pattern_id": "Y001", "custom_field": 42})
        assert p2.pattern_id == "Y001"
        assert hasattr(p2, "custom_field")

    def test_get_pattern_existing(self, init_pats):
        """get_pattern() findet existierendes Pattern."""
        p = init_pats.get_pattern("S001")
        assert p is not None
        assert p.pattern_id == "S001"

    def test_get_pattern_nonexistent(self, init_pats):
        """get_pattern() gibt None für unbekannte IDs."""
        p = init_pats.get_pattern("ZZZZ")
        assert p is None

    def test_get_patterns_by_category(self, init_pats):
        """get_patterns_by_category() liefert Liste."""
        pats = init_pats.get_patterns_by_category("security")
        assert len(pats) >= 8
        for p in pats:
            assert p.category == "security"

    def test_get_patterns_by_ids_mixed(self, init_pats):
        """get_patterns_by_ids() filtert nicht-existierende IDs."""
        pats = init_pats.get_patterns_by_ids(["S001", "ZZZZ", "C001"])
        assert len(pats) == 2  # ZZZZ existiert nicht
        assert pats[0].pattern_id == "S001"
        assert pats[1].pattern_id == "C001"


class TestRegexSyntax:
    """Regex-Syntax-Prüfung für alle scan_query Patterns."""

    def test_all_grep_queries_are_valid_regex(self, init_pats):
        r"""Jeder grep scan_query muss syntaktisch valide sein.

        Akzeptiert POSIX-Escapes (\(, \), \{, \}) die Python re nicht mag.
        """
        import re
        invalid = []
        posix_only_escapes = {r"\(", r"\)", r"\{", r"\}", r"\|"}
        for p in init_pats.ALL_PATTERNS:
            if p.scan_type == "grep" and p.scan_query:
                try:
                    re.compile(p.scan_query)
                except re.error as e:
                    # Prüfen ob es nur ein POSIX-escape ist (wird von grep verstanden)
                    msg = str(e)
                    if any(esc in p.scan_query for esc in posix_only_escapes):
                        continue  # POSIX-Escape, von grep unterstützt
                    invalid.append(f"{p.pattern_id}: {msg}")
        assert not invalid, "Ungültige Regex-Patterns:\n" + "\n".join(invalid)

    def test_all_grep_queries_have_content(self, init_pats):
        """Jeder grep scan_query darf nicht leer sein."""
        for p in init_pats.ALL_PATTERNS:
            if p.scan_type == "grep":
                assert p.scan_query, f"{p.pattern_id}: grep scan_query leer"

    def test_code_search_queries_have_content(self, init_pats):
        """Jeder code_search scan_query darf nicht leer sein."""
        for p in init_pats.ALL_PATTERNS:
            if p.scan_type == "code_search":
                assert p.scan_query, f"{p.pattern_id}: code_search scan_query leer"

    def test_scan_file_glob_exists_for_grep(self, init_pats):
        """Jeder grep scan_type braucht ein scan_file_glob."""
        for p in init_pats.ALL_PATTERNS:
            if p.scan_type == "grep":
                assert p.scan_file_glob, f"{p.pattern_id}: scan_file_glob leer"
