"""Tests für shared/patterns.py — Shared Pattern Repository.

Alle Tests verwenden tmp_path für Isolation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _setup():
    """PYTHONPATH + Home-Verzeichnis für .hermes/patterns."""
    plugins_root = str(PLUGIN_ROOT.parent)
    if plugins_root not in sys.path:
        sys.path.insert(0, plugins_root)
    yield


@pytest.fixture
def patterns_mod(monkeypatch, tmp_path):
    """shared.patterns mit tmp_path als .hermes Verzeichnis."""
    hermes_dir = tmp_path / ".hermes"
    hermes_dir.mkdir()
    patterns_dir = hermes_dir / "patterns"
    patterns_dir.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    # Modul neu laden
    import importlib

    from scout.shared import patterns as pm
    importlib.reload(pm)
    return pm


def _r(patterns_mod, func_name, *args, **kwargs):
    """Helper: ruft Funktion aus patterns_mod auf."""
    return getattr(patterns_mod, func_name)(*args, **kwargs)


class TestSharedPatterns:
    """Systematische Tests aller Funktionen in shared/patterns.py."""

    def test_save_pattern_new(self, patterns_mod):
        """Neues Pattern ohne ID → bekommt P001."""
        pid = _r(patterns_mod, "save_pattern", {"name": "test"})
        assert pid == "P001"
        assert len(_r(patterns_mod, "list_all_patterns")) == 1

    def test_save_pattern_update(self, patterns_mod):
        """Bestehendes Pattern mit ID → wird geupdated."""
        _r(patterns_mod, "save_pattern", {"pattern_id": "P001", "name": "original"})
        _r(patterns_mod, "save_pattern", {"pattern_id": "P001", "name": "updated"})
        pat = _r(patterns_mod, "get_pattern", "P001")
        assert pat["name"] == "updated"

    def test_save_pattern_generates_unique_id(self, patterns_mod):
        """Mehrere Patterns ohne ID → P001, P002, P003."""
        for i in range(3):
            pid = _r(patterns_mod, "save_pattern", {"name": f"pat{i}"})
            assert pid == f"P00{i+1}"

    def test_get_pattern_found(self, patterns_mod):
        _r(patterns_mod, "save_pattern", {"pattern_id": "P001", "name": "findme"})
        pat = _r(patterns_mod, "get_pattern", "P001")
        assert pat is not None and pat["name"] == "findme"

    def test_get_pattern_not_found(self, patterns_mod):
        assert _r(patterns_mod, "get_pattern", "GHOST") is None

    def test_get_patterns_for_analysis_all(self, patterns_mod):
        """Ohne language-Filter: alle Patterns zurück."""
        _r(patterns_mod, "save_pattern", {"pattern_id": "P001"})
        _r(patterns_mod, "save_pattern", {"pattern_id": "P002"})
        result = _r(patterns_mod, "get_patterns_for_analysis")
        assert len(result) == 2

    def test_get_patterns_for_analysis_filtered(self, patterns_mod):
        """Mit language-Filter: nur passende Patterns."""
        _r(patterns_mod, "save_pattern", {"pattern_id": "P001", "scan_language": "python"})
        _r(patterns_mod, "save_pattern", {"pattern_id": "P002", "scan_language": "go"})
        result = _r(patterns_mod, "get_patterns_for_analysis", "python")
        assert len(result) == 1
        assert result[0]["pattern_id"] == "P001"

    def test_get_patterns_for_frameworks_generic(self, patterns_mod):
        """Framework-Filter mit standard * → alle Patterns."""
        _r(patterns_mod, "save_pattern", {"pattern_id": "P001"})
        result = _r(patterns_mod, "get_patterns_for_frameworks", {"backend": [{"name": "medusa-v2"}]})
        assert len(result) == 1

    def test_get_patterns_for_frameworks_filtered(self, patterns_mod):
        """Nur Patterns die zum Framework passen."""
        _r(patterns_mod, "save_pattern", {"pattern_id": "P001", "frameworks": ["medusa-v2"]})
        _r(patterns_mod, "save_pattern", {"pattern_id": "P002", "frameworks": ["react"]})
        result = _r(patterns_mod, "get_patterns_for_frameworks", {"backend": [{"name": "medusa-v2"}]})
        assert [p["pattern_id"] for p in result] == ["P001"]

    def test_get_patterns_for_frameworks_empty(self, patterns_mod):
        """Keine Patterns → leere Liste."""
        result = _r(patterns_mod, "get_patterns_for_frameworks", {})
        assert result == []

    def test_glob_matches_language_ext(self, patterns_mod):
        assert _r(patterns_mod, "_glob_matches_language", "*.py", {"py"})
        assert not _r(patterns_mod, "_glob_matches_language", "*.go", {"py"})
        assert _r(patterns_mod, "_glob_matches_language", "**/*.{ts,tsx}", {"ts"})

    def test_increment_match_count(self, patterns_mod):
        _r(patterns_mod, "save_pattern", {"pattern_id": "P001"})
        _r(patterns_mod, "increment_match_count", "P001")
        _r(patterns_mod, "increment_match_count", "P001")
        pat = _r(patterns_mod, "get_pattern", "P001")
        assert pat["match_count"] == 2

    def test_increment_match_count_unknown(self, patterns_mod):
        """Unbekanntes Pattern → kein Crash."""
        _r(patterns_mod, "increment_match_count", "GHOST")

    def test_count_patterns(self, patterns_mod):
        _r(patterns_mod, "save_pattern", {"pattern_id": "P001"})
        _r(patterns_mod, "save_pattern", {"pattern_id": "P002"})
        assert _r(patterns_mod, "count_patterns") == 2

    def test_list_all_patterns(self, patterns_mod):
        _r(patterns_mod, "save_pattern", {"pattern_id": "P001"})
        all_pats = _r(patterns_mod, "list_all_patterns")
        assert len(all_pats) == 1

    def test_get_patterns_by_category(self, patterns_mod):
        _r(patterns_mod, "save_pattern", {"pattern_id": "P001", "category": "security"})
        _r(patterns_mod, "save_pattern", {"pattern_id": "P002", "category": "code-quality"})
        result = _r(patterns_mod, "get_patterns_by_category", "security")
        assert len(result) == 1

    def test_delete_pattern_exists(self, patterns_mod):
        _r(patterns_mod, "save_pattern", {"pattern_id": "P001"})
        assert _r(patterns_mod, "delete_pattern", "P001") is True
        assert _r(patterns_mod, "count_patterns") == 0

    def test_delete_pattern_not_exists(self, patterns_mod):
        assert _r(patterns_mod, "delete_pattern", "GHOST") is False

    def test_migrate_bughunt_custom_patterns_no_file(self, patterns_mod):
        """Keine alte bughunt-Datei → 0 migriert."""
        count = _r(patterns_mod, "migrate_bughunt_custom_patterns")
        assert count == 0

    def test_migrate_bughunt_custom_patterns_already_migrated(self, patterns_mod):
        """Migration schon durchgeführt (Marker-Datei existiert) → 0."""
        patterns_mod.PATTERNS_CORE_MIGRATED.write_text("{}")
        count = _r(patterns_mod, "migrate_bughunt_custom_patterns")
        assert count == 0

    def test_migrate_bughunt_custom_patterns_success(self, patterns_mod, tmp_path):
        """Erfolgreiche Migration von bughunt custom patterns."""
        # Bughunt custom patterns Datei anlegen
        bughunt_dir = tmp_path / ".hermes" / "plugins" / "bughunt" / "data" / "patterns"
        bughunt_dir.mkdir(parents=True)
        custom_file = bughunt_dir / "custom_patterns.json"
        custom_file.write_text(json.dumps([
            {"pattern_id": "CUSTOM001", "name": "custom1", "category": "security"},
            {"pattern_id": "CUSTOM002", "name": "custom2", "category": "code-quality"},
        ]))

        count = _r(patterns_mod, "migrate_bughunt_custom_patterns")
        assert count == 2
        # Marker sollte existieren
        assert patterns_mod.PATTERNS_CORE_MIGRATED.exists()
        # Patterns sollten importiert sein
        pat1 = _r(patterns_mod, "get_pattern", "CUSTOM001")
        assert pat1 is not None
        assert pat1["name"] == "custom1"

    def test_migrate_bughunt_custom_patterns_skips_duplicates(self, patterns_mod, tmp_path):
        """Duplikate werden bei Migration übersprungen."""
        # Vorher ein Pattern speichern
        _r(patterns_mod, "save_pattern", {"pattern_id": "EXISTING", "name": "existing"})

        bughunt_dir = tmp_path / ".hermes" / "plugins" / "bughunt" / "data" / "patterns"
        bughunt_dir.mkdir(parents=True)
        custom_file = bughunt_dir / "custom_patterns.json"
        custom_file.write_text(json.dumps([
            {"pattern_id": "EXISTING", "name": "existing"},  # Duplikat
            {"pattern_id": "NEW001", "name": "new"},         # Neu
        ]))

        count = _r(patterns_mod, "migrate_bughunt_custom_patterns")
        assert count == 1  # Nur NEW001 ist neu
        assert _r(patterns_mod, "get_pattern", "NEW001") is not None

    def test_migrate_bughunt_custom_patterns_corrupt_json(self, patterns_mod, tmp_path):
        """Kaputte JSON → Exception → 0 zurück (kein Crash)."""
        bughunt_dir = tmp_path / ".hermes" / "plugins" / "bughunt" / "data" / "patterns"
        bughunt_dir.mkdir(parents=True)
        custom_file = bughunt_dir / "custom_patterns.json"
        custom_file.write_text("{broken json}")

        count = _r(patterns_mod, "migrate_bughunt_custom_patterns")
        assert count == 0  # Exception → return 0

    def test_migrate_bughunt_custom_patterns_dict_format(self, patterns_mod, tmp_path):
        """custom_patterns.json als Dict mit 'patterns' Key."""
        bughunt_dir = tmp_path / ".hermes" / "plugins" / "bughunt" / "data" / "patterns"
        bughunt_dir.mkdir(parents=True)
        custom_file = bughunt_dir / "custom_patterns.json"
        custom_file.write_text(json.dumps({
            "patterns": [{"pattern_id": "DICT001", "name": "from_dict"}]
        }))

        count = _r(patterns_mod, "migrate_bughunt_custom_patterns")
        assert count == 1
        assert _r(patterns_mod, "get_pattern", "DICT001") is not None

    def test_empty_patterns_file(self, patterns_mod):
        """Leere Patterns-Datei → leere Liste."""
        patterns_mod.SHARED_PATTERNS_FILE.write_text("[]")
        assert _r(patterns_mod, "count_patterns") == 0

    def test_corrupted_patterns_file(self, patterns_mod):
        """Kaputte JSON-Datei → leere Liste (kein Crash)."""
        patterns_mod.SHARED_PATTERNS_FILE.write_text("{broken json}")
        assert _r(patterns_mod, "count_patterns") == 0
