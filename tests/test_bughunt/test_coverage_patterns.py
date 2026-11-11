"""Coverage-Ergänzung für scout/bughunt/core/patterns.py.

Fokus: Validierungsfehler, ID-Vergabe mit kaputten IDs, Limit, Kategorie-Merge,
Fallback-Objektbau, Recovery bei korrupter JSON-Datei und die Import-Fallbacks
in init_patterns().

Alle Dateien liegen in tmp_path; die In-Memory-Registries werden pro Test
gepatcht, damit nichts in andere Tests leckt.
"""

from __future__ import annotations

import json
import sys
import types

import pytest

from scout.bughunt.core import patterns as pat

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_state(tmp_path, monkeypatch):
    """Isoliert JSON-Datei und In-Memory-Registries."""
    custom_file = tmp_path / "patterns" / "custom_patterns.json"
    custom_file.parent.mkdir(parents=True)

    monkeypatch.setattr(pat, "CUSTOM_PATTERNS_FILE", custom_file, raising=True)
    monkeypatch.setattr(pat, "PATTERNS_DIR", custom_file.parent, raising=True)
    monkeypatch.setattr(pat, "SESSIONS_DIR", tmp_path / "sessions", raising=True)
    monkeypatch.setattr(pat, "PATTERNS_BY_ID", {}, raising=True)
    monkeypatch.setattr(pat, "PATTERNS_BY_CATEGORY", {}, raising=True)
    monkeypatch.setattr(pat, "ALL_PATTERNS", [], raising=True)
    return custom_file


def _valid_pattern(**overrides) -> dict:
    data = {
        "name": "Unsafe innerHTML",
        "scan_type": "grep",
        "scan_query": "dangerouslySetInnerHTML",
        "severity": "P1",
        "category": "security",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# ID-Vergabe
# ---------------------------------------------------------------------------


def test_next_custom_id_skips_unparseable_ids(clean_state):
    pat.PATTERNS_BY_ID.update({
        "CUSTOM_007": object(),
        "CUSTOM_kaputt": object(),
        "CUSTOM_": object(),
        "BUILTIN_1": object(),
    })

    assert pat._next_custom_id() == "CUSTOM_008"


def test_next_custom_id_starts_at_one(clean_state):
    assert pat._next_custom_id() == "CUSTOM_001"


# ---------------------------------------------------------------------------
# Validierung
# ---------------------------------------------------------------------------


class TestValidation:
    def test_missing_name(self):
        assert pat._validate_custom_pattern({"scan_type": "grep", "scan_query": "x"}) == \
            "name ist erforderlich"

    def test_unknown_scan_type(self):
        err = pat._validate_custom_pattern(_valid_pattern(scan_type="semgrep"))

        assert err is not None
        assert "scan_type" in err

    def test_grep_requires_scan_query(self):
        err = pat._validate_custom_pattern(_valid_pattern(scan_query="   "))

        assert err is not None
        assert "scan_query" in err

    def test_code_diagnostics_needs_no_query(self):
        assert pat._validate_custom_pattern(
            _valid_pattern(scan_type="code_diagnostics", scan_query="")
        ) is None

    def test_invalid_severity(self):
        err = pat._validate_custom_pattern(_valid_pattern(severity="critical"))

        assert err is not None
        assert "severity" in err

    def test_invalid_category(self):
        err = pat._validate_custom_pattern(_valid_pattern(category="unfug"))

        assert err is not None
        assert "category" in err

    def test_custom_category_is_accepted(self):
        assert pat._validate_custom_pattern(_valid_pattern(category="custom")) is None


# ---------------------------------------------------------------------------
# Speichern
# ---------------------------------------------------------------------------


class TestSave:
    def test_invalid_pattern_raises_and_writes_nothing(self, clean_state):
        with pytest.raises(ValueError, match="scan_type"):
            pat.save_custom_pattern(_valid_pattern(scan_type="nope"))

        assert not clean_state.exists()

    def test_limit_raises_value_error(self, clean_state, monkeypatch):
        monkeypatch.setattr(pat, "MAX_CUSTOM_PATTERNS", 1, raising=True)
        clean_state.write_text(json.dumps([
            {
                "pattern_id": "CUSTOM_001",
                "name": "Anderes Pattern",
                "scan_query": "foo",
                "category": "other",
            },
        ]), encoding="utf-8")

        with pytest.raises(ValueError, match="Maximum"):
            pat.save_custom_pattern(_valid_pattern())

    def test_new_pattern_is_persisted_and_indexed(self, clean_state):
        pid = pat.save_custom_pattern(_valid_pattern())

        assert pid == "CUSTOM_001"
        stored = json.loads(clean_state.read_text(encoding="utf-8"))
        assert stored[0]["pattern_id"] == pid
        assert stored[0]["source"] == "custom"
        assert stored[0]["severity"] == "P1"
        assert pid in pat.PATTERNS_BY_ID
        assert "custom" in pat.PATTERNS_BY_CATEGORY

    def test_ids_increment_and_duplicates_update(self, clean_state):
        first = pat.save_custom_pattern(_valid_pattern())
        second = pat.save_custom_pattern(_valid_pattern(name="Anderes"))

        assert (first, second) == ("CUSTOM_001", "CUSTOM_002")

        # gleicher name+scan_query → Update auf derselben ID
        again = pat.save_custom_pattern(_valid_pattern(description="neu beschrieben"))
        assert again == first

        stored = json.loads(clean_state.read_text(encoding="utf-8"))
        assert len(stored) == 2
        assert stored[0]["description"] == "neu beschrieben"
        assert stored[0]["updated_at"] >= stored[0]["created_at"]


# ---------------------------------------------------------------------------
# In-Memory-Sync
# ---------------------------------------------------------------------------


class TestSync:
    def test_new_category_bucket_is_created(self, clean_state):
        entry = {
            "pattern_id": "CUSTOM_042",
            "name": "Eigenes",
            "category": "database",
            "severity": "P2",
            "scan_type": "grep",
            "scan_query": "select *",
        }

        pat._sync_custom_pattern_to_memory(entry)

        assert [p.pattern_id for p in pat.PATTERNS_BY_CATEGORY["database"]] == ["CUSTOM_042"]
        assert [p.pattern_id for p in pat.PATTERNS_BY_CATEGORY["custom"]] == ["CUSTOM_042"]
        assert [p.pattern_id for p in pat.ALL_PATTERNS] == ["CUSTOM_042"]

    def test_sync_is_idempotent(self, clean_state):
        entry = {
            "pattern_id": "CUSTOM_043",
            "name": "Doppelt",
            "category": "other",
            "severity": "P3",
            "scan_type": "grep",
            "scan_query": "x",
        }

        pat._sync_custom_pattern_to_memory(entry)
        pat._sync_custom_pattern_to_memory(entry)

        assert len(pat.ALL_PATTERNS) == 1
        assert len(pat.PATTERNS_BY_CATEGORY["other"]) == 1
        assert len(pat.PATTERNS_BY_CATEGORY["custom"]) == 1


def test_dict_to_pattern_fallback_object(monkeypatch):
    # bp ohne BugPattern-Attribut erzwingt den Fallback-Builder
    monkeypatch.setattr(pat, "bp", types.SimpleNamespace(), raising=True)

    obj = pat._dict_to_pattern({"pattern_id": "X1", "category": "other"})

    assert obj.pattern_id == "X1"
    assert obj.category == "other"


# ---------------------------------------------------------------------------
# Persistenz-Fehlerpfade
# ---------------------------------------------------------------------------


class TestCorruptFile:
    def test_corrupt_json_is_backed_up_and_reset(self, clean_state):
        clean_state.write_text("{ kein json", encoding="utf-8")

        assert pat._load_custom_patterns_raw() == []
        assert not clean_state.exists()
        assert clean_state.with_suffix(".json.bak").exists()

    def test_failing_backup_rename_still_returns_empty(self, clean_state):
        clean_state.write_text("{ kein json", encoding="utf-8")
        # Backup-Ziel als Verzeichnis → rename scheitert mit OSError
        clean_state.with_suffix(".json.bak").mkdir()

        assert pat._load_custom_patterns_raw() == []

    def test_json_object_instead_of_list_is_rejected(self, clean_state):
        clean_state.write_text('{"pattern_id": "CUSTOM_001"}', encoding="utf-8")

        assert pat._load_custom_patterns_raw() == []

    def test_missing_file_returns_empty(self, clean_state):
        assert pat._load_custom_patterns_raw() == []


def test_delete_builtin_pattern_is_refused():
    with pytest.raises(ValueError, match="Built-in"):
        pat.delete_custom_pattern("SEC_001")


# ---------------------------------------------------------------------------
# init_patterns — Import-Fallbacks
# ---------------------------------------------------------------------------


def _fake_patterns_module(pid: str) -> types.ModuleType:
    mod = types.ModuleType("fake_patterns")
    pattern = types.SimpleNamespace(pattern_id=pid, category="security", source="built-in")
    mod.PATTERNS_BY_ID = {pid: pattern}
    mod.PATTERNS_BY_CATEGORY = {"security": [pattern]}
    mod.ALL_PATTERNS = [pattern]
    return mod


def test_init_patterns_falls_back_to_top_level_patterns_data(clean_state, monkeypatch):
    # Paket-qualifizierter Import scheitert, der top-level Import funktioniert
    import bughunt.data.patterns_data  # noqa: F401  (im sys.path der Tests)

    monkeypatch.setitem(sys.modules, "scout.bughunt.data.patterns_data", None)

    pat.init_patterns()

    assert pat.PATTERNS_BY_ID == pat.bp.PATTERNS_BY_ID


def test_init_patterns_survives_missing_patterns_data(clean_state, monkeypatch):
    monkeypatch.setitem(sys.modules, "scout.bughunt.data.patterns_data", None)
    monkeypatch.setitem(sys.modules, "bughunt.data.patterns_data", None)

    pat.init_patterns()

    assert pat.PATTERNS_BY_ID == pat.bp.PATTERNS_BY_ID


def test_init_patterns_uses_top_level_fallback_module(clean_state, monkeypatch):
    fake = _fake_patterns_module("FALLBACK_001")
    monkeypatch.setitem(sys.modules, "bughunt_patterns", fake)
    # Erzwingt ImportError für den paket-qualifizierten Import: sowohl das
    # Paket-Attribut als auch der sys.modules-Eintrag müssen weg sein
    import scout.bughunt as scout_bughunt

    monkeypatch.delattr(scout_bughunt, "bughunt_patterns", raising=False)
    monkeypatch.setitem(sys.modules, "scout.bughunt.bughunt_patterns", None)

    pat.init_patterns()

    assert list(pat.PATTERNS_BY_ID) == ["FALLBACK_001"]
    assert pat.ALL_PATTERNS[0].pattern_id == "FALLBACK_001"


def test_init_patterns_ignores_broken_custom_loader(clean_state, monkeypatch):
    def _boom():
        raise RuntimeError("JSON kaputt")

    monkeypatch.setattr(pat, "load_custom_patterns", _boom, raising=True)

    # Darf nicht werfen — Built-ins werden trotzdem geladen
    pat.init_patterns()

    assert pat.PATTERNS_BY_ID


def test_init_patterns_merges_custom_patterns(clean_state):
    clean_state.write_text(json.dumps([{
        "pattern_id": "CUSTOM_900",
        "name": "Aus Datei",
        "category": "testing",
        "severity": "P2",
        "scan_type": "grep",
        "scan_query": "skip(",
        "source": "custom",
    }]), encoding="utf-8")

    pat.init_patterns()

    assert "CUSTOM_900" in pat.PATTERNS_BY_ID
    custom_dicts = pat.list_custom_patterns()
    assert [p["pattern_id"] for p in custom_dicts] == ["CUSTOM_900"]


def test_get_patterns_by_ids_skips_unknown(clean_state):
    entry = {
        "pattern_id": "CUSTOM_777",
        "name": "Bekannt",
        "category": "other",
        "severity": "P2",
        "scan_type": "grep",
        "scan_query": "y",
    }
    pat._sync_custom_pattern_to_memory(entry)

    found = pat.get_patterns_by_ids(["CUSTOM_777", "GIBTS_NICHT"])

    assert [p.pattern_id for p in found] == ["CUSTOM_777"]
    assert pat.list_categories() == [{"category": "custom", "count": 1},
                                     {"category": "other", "count": 1}]
