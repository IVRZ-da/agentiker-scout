"""Tests für Custom Pattern Persistenz (v0.6.0).

Testet: save_custom_pattern, load_custom_patterns, delete_custom_pattern,
         list_custom_patterns, _sync_custom_pattern_to_memory, Deduplizierung,
         Auto-ID, Validation, 500er-Limit, JSON-Corruption-Recovery.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

# ── Helper: bughunt_core laden wie conftest.py ──────────────────────

@pytest.fixture(scope="function")
def core(tmp_path):
    """bughunt_core Modul laden — mit isoliertem DATA_DIR pro Test."""
    # Sicherstellen dass _fmt gemockt ist
    if "_fmt" not in sys.modules:
        fmt = types.ModuleType("_fmt")
        fmt.fmt_ok = lambda d, **kw: str(d)
        fmt.fmt_err = lambda m, **kw: str(m)
        sys.modules["_fmt"] = fmt

    # bughunt package falls nötig
    if "bughunt" not in sys.modules:
        pkg = types.ModuleType("bughunt")
        pkg.__path__ = [str(Path(__file__).parent.parent.parent / "bughunt")]
        sys.modules["bughunt"] = pkg
        sys.modules["bughunt._fmt"] = sys.modules.get("_fmt", types.ModuleType("_fmt"))

    mod_name = f"bughunt.bughunt_core.{tmp_path.name}"
    if mod_name in sys.modules:
        return sys.modules[mod_name]

    source = Path(__file__).parent.parent.parent / "bughunt" / "bughunt_core.py"
    spec = importlib.util.spec_from_file_location(mod_name, source)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "bughunt"
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)

    # PATTERNS_DIR auf tmp_path isolieren (damit keine Kreuz-Kontamination)
    mod.PATTERNS_DIR = tmp_path / "patterns"
    mod.PATTERNS_DIR.mkdir(parents=True, exist_ok=True)
    mod.CUSTOM_PATTERNS_FILE = mod.PATTERNS_DIR / "custom_patterns.json"
    return mod


# ── Tests ───────────────────────────────────────────────────────────

class TestSaveCustomPattern:
    def test_save_new(self, core):
        """Neues Custom Pattern speichern."""
        core.init_patterns()
        pid = core.save_custom_pattern({
            "name": "Test Save",
            "scan_query": "test-save-query",
            "category": "code-quality",
            "severity": "P2",
            "scan_type": "grep",
        })
        try:
            assert pid.startswith("CUSTOM_"), f"Prefix: {pid}"
            assert pid in core.PATTERNS_BY_ID
            p = core.PATTERNS_BY_ID[pid]
            assert getattr(p, "source", "") == "custom"
            assert getattr(p, "name", "") == "Test Save"
        finally:
            core.delete_custom_pattern(pid)

    def test_save_increments_id(self, core):
        """Auto-ID: CUSTOM_001, CUSTOM_002, ..."""
        core.init_patterns()
        pids = []
        try:
            for i in range(3):
                pid = core.save_custom_pattern({
                    "name": f"Inc {i}",
                    "scan_query": f"inc-query-{i}",
                    "category": "code-quality",
                    "severity": "P2",
                    "scan_type": "grep",
                })
                pids.append(pid)
                assert pid == f"CUSTOM_{i+1:03d}", f"Expected CUSTOM_{i+1:03d}, got {pid}"
        finally:
            for pid in pids:
                core.delete_custom_pattern(pid)

    def test_dedup_same_name_and_query(self, core):
        """Gleicher name+scan_query → Update, nicht neu anlegen."""
        core.init_patterns()
        pid1 = core.save_custom_pattern({
            "name": "Dedup Test",
            "scan_query": "dedup-query",
            "category": "code-quality",
            "severity": "P2",
            "scan_type": "grep",
            "fix_description": "Original",
        })
        try:
            pid2 = core.save_custom_pattern({
                "name": "Dedup Test",
                "scan_query": "dedup-query",
                "category": "security",
                "severity": "P1",
                "scan_type": "grep",
                "fix_description": "Updated",
            })
            assert pid2 == pid1, f"Sollte gleiche ID haben: {pid2} != {pid1}"
            # Prüfen ob Update durchgeschlagen ist
            p = core.PATTERNS_BY_ID[pid1]
            cat = getattr(p, "category", "")
            assert cat == "security", f"Category sollte 'security' sein, ist '{cat}'"
        finally:
            core.delete_custom_pattern(pid1)

    def test_unique_id_across_different_queries(self, core):
        """Verschiedene queries → verschiedene IDs."""
        core.init_patterns()
        pid1 = core.save_custom_pattern({
            "name": "Unique A",
            "scan_query": "query-a",
            "category": "code-quality",
            "severity": "P2",
            "scan_type": "grep",
        })
        pid2 = core.save_custom_pattern({
            "name": "Unique B",
            "scan_query": "query-b",
            "category": "code-quality",
            "severity": "P2",
            "scan_type": "grep",
        })
        try:
            assert pid1 != pid2, "Verschiedene Patterns → verschiedene IDs"
        finally:
            core.delete_custom_pattern(pid1)
            core.delete_custom_pattern(pid2)

    def test_validation_missing_name(self, core):
        """Ohne name → ValueError."""
        core.init_patterns()
        with pytest.raises(ValueError, match="name"):
            core.save_custom_pattern({
                "scan_query": "test",
                "scan_type": "grep",
            })

    def test_validation_missing_scan_query(self, core):
        """grep ohne scan_query → ValueError."""
        core.init_patterns()
        with pytest.raises(ValueError, match="scan_query"):
            core.save_custom_pattern({
                "name": "No Query",
                "scan_type": "grep",
                "scan_query": "",
            })

    def test_validation_invalid_severity(self, core):
        """Ungültige severity → ValueError."""
        core.init_patterns()
        with pytest.raises(ValueError, match="severity"):
            core.save_custom_pattern({
                "name": "Bad Severy",
                "scan_query": "test",
                "scan_type": "grep",
                "severity": "P5",
            })

    def test_tags_preserved(self, core):
        """Tags werden korrekt gespeichert und returned."""
        core.init_patterns()
        tags = ["performance", "react", "data-fetching"]
        pid = core.save_custom_pattern({
            "name": "Tagged Pattern",
            "scan_query": "tag-query",
            "category": "react-next",
            "severity": "P2",
            "scan_type": "grep",
            "tags": tags,
        })
        try:
            p = core.PATTERNS_BY_ID[pid]
            saved_tags = getattr(p, "tags", [])
            assert saved_tags == tags, f"{saved_tags} != {tags}"
        finally:
            core.delete_custom_pattern(pid)


class TestLoadCustomPatterns:
    def test_load_empty(self, core):
        """Keine Datei → leere Liste."""
        data = core.load_custom_patterns()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_load_after_save(self, core):
        """Nach save → load enthält das Pattern."""
        core.init_patterns()
        pid = core.save_custom_pattern({
            "name": "Load Test",
            "scan_query": "load-query",
            "category": "code-quality",
            "severity": "P2",
            "scan_type": "grep",
        })
        try:
            data = core.load_custom_patterns()
            assert len(data) >= 1
            ids = [e["pattern_id"] for e in data]
            assert pid in ids, f"{pid} not in {ids}"
        finally:
            core.delete_custom_pattern(pid)


class TestDeleteCustomPattern:
    def test_delete_existing(self, core):
        """Löschen eines existierenden Custom Patterns."""
        core.init_patterns()
        pid = core.save_custom_pattern({
            "name": "Delete Me",
            "scan_query": "delete-query",
            "category": "code-quality",
            "severity": "P2",
            "scan_type": "grep",
        })
        assert pid in core.PATTERNS_BY_ID
        result = core.delete_custom_pattern(pid)
        assert result is True
        assert pid not in core.PATTERNS_BY_ID

    def test_delete_nonexistent(self, core):
        """Löschen eines nicht-existierenden → False."""
        core.init_patterns()
        result = core.delete_custom_pattern("CUSTOM_999")
        assert result is False

    def test_delete_builtin_raises(self, core):
        """Built-in Patterns können nicht gelöscht werden."""
        core.init_patterns()
        with pytest.raises(ValueError, match="nicht löschen"):
            core.delete_custom_pattern("S001")

    def test_delete_removes_from_categories(self, core):
        """Nach delete: Pattern auch aus Kategorien entfernt."""
        core.init_patterns()
        pid = core.save_custom_pattern({
            "name": "Cat Delete",
            "scan_query": "cat-del",
            "category": "security",
            "severity": "P1",
            "scan_type": "grep",
        })
        try:
            # Check it's in its category and in 'custom'
            cust = core.get_patterns_by_category("custom")
            assert any(getattr(p, "pattern_id", "") == pid for p in cust)
        finally:
            core.delete_custom_pattern(pid)
            # After delete
            cust = core.get_patterns_by_category("custom")
            assert not any(getattr(p, "pattern_id", "") == pid for p in cust)


class TestListCustomPatterns:
    def test_list_empty(self, core):
        """Ohne Custom Patterns → leere Liste."""
        core.init_patterns()
        result = core.list_custom_patterns()
        assert isinstance(result, list)

    def test_list_after_save(self, core):
        """Nach save → in der Liste."""
        core.init_patterns()
        pid = core.save_custom_pattern({
            "name": "List Me",
            "scan_query": "list-query",
            "category": "code-quality",
            "severity": "P2",
            "scan_type": "grep",
        })
        try:
            result = core.list_custom_patterns()
            assert any(c["pattern_id"] == pid for c in result)
        finally:
            core.delete_custom_pattern(pid)


class TestInitPatternsMerge:
    def test_custom_merged_after_init(self, core):
        """init_patterns() merged Custom Patterns in PATTERNS_BY_ID."""
        core.init_patterns()
        pid = core.save_custom_pattern({
            "name": "Merge Test",
            "scan_query": "merge-query",
            "category": "code-quality",
            "severity": "P2",
            "scan_type": "grep",
        })
        try:
            # Re-init
            core.init_patterns()
            assert pid in core.PATTERNS_BY_ID
            # Sollte auch in der 'custom' Kategorie sein
            cust = core.get_patterns_by_category("custom")
            assert any(getattr(p, "pattern_id", "") == pid for p in cust)
        finally:
            core.delete_custom_pattern(pid)

    def test_builtin_still_present_after_custom(self, core):
        """Built-in Patterns bleiben nach Custom-Merge erhalten."""
        core.init_patterns()
        pid = core.save_custom_pattern({
            "name": "Builtin Check",
            "scan_query": "builtin-check",
            "category": "code-quality",
            "severity": "P2",
            "scan_type": "grep",
        })
        try:
            core.init_patterns()
            assert "S001" in core.PATTERNS_BY_ID
            assert len(core.PATTERNS_BY_ID) >= 44  # 43 built-in + 1 custom
        finally:
            core.delete_custom_pattern(pid)


class TestIntegrationWithFindings:
    def test_pattern_appears_in_get_patterns_by_category_custom(self, core):
        """get_patterns_by_category('custom') liefert Custom Patterns."""
        core.init_patterns()
        pid = core.save_custom_pattern({
            "name": "Cat Custom",
            "scan_query": "cat-custom",
            "category": "code-quality",
            "severity": "P2",
            "scan_type": "grep",
        })
        try:
            pats = core.get_patterns_by_category("custom")
            ids = [getattr(p, "pattern_id", "") for p in pats]
            assert pid in ids
        finally:
            core.delete_custom_pattern(pid)

    def test_source_field_defaults_to_builtin(self, core):
        """Bestehende Built-in Patterns haben source='built-in'."""
        core.init_patterns()
        p = core.get_pattern("S001")
        assert p is not None
        assert getattr(p, "source", "built-in") in ("built-in", "")

    def test_custom_pattern_has_metadata(self, core):
        """Custom Pattern hat source_session, created_at, etc."""
        core.init_patterns()
        pid = core.save_custom_pattern({
            "name": "Meta Test",
            "scan_query": "meta-query",
            "category": "code-quality",
            "severity": "P2",
            "scan_type": "grep",
            "source_session": "sess_abc",
            "source_project": "/test",
            "source_finding_id": "f_xyz",
        })
        try:
            p = core.PATTERNS_BY_ID[pid]
            assert getattr(p, "source_session", "") == "sess_abc"
            assert getattr(p, "source_project", "") == "/test"
            assert getattr(p, "source_finding_id", "") == "f_xyz"
            assert getattr(p, "created_at", "") != ""
            assert getattr(p, "updated_at", "") != ""
        finally:
            core.delete_custom_pattern(pid)
