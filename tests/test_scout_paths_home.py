"""Nutzdaten liegen pro Profil unter ``<hermes-home>/plugin-data/agentiker-scout``.

Review #157391 Punkt 4: die Wurzel war hartkodiert auf ``~/.hermes/data/scout``,
damit teilten sich alle Profile einen Store und ``HERMES_HOME`` war wirkungslos.
"""

from __future__ import annotations

from pathlib import Path

from scout.shared import paths as _paths


def test_data_root_follows_hermes_home(monkeypatch, tmp_path):
    monkeypatch.delenv(_paths.ENV_DATA_DIR, raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    expected = (tmp_path / "plugin-data" / "agentiker-scout").resolve()
    assert _paths.resolve_data_root() == expected


def test_explicit_env_still_wins(monkeypatch, tmp_path):
    monkeypatch.setenv(_paths.ENV_DATA_DIR, str(tmp_path / "custom"))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    assert _paths.resolve_data_root() == (tmp_path / "custom").resolve()


def test_default_without_env_is_plugin_data(monkeypatch):
    monkeypatch.delenv(_paths.ENV_DATA_DIR, raising=False)
    monkeypatch.delenv("HERMES_HOME", raising=False)
    root = _paths.resolve_data_root()
    assert root.name == "agentiker-scout"
    assert root.parent.name == "plugin-data"


def test_legacy_root_is_not_used_as_default(monkeypatch):
    monkeypatch.delenv(_paths.ENV_DATA_DIR, raising=False)
    monkeypatch.delenv("HERMES_HOME", raising=False)
    assert _paths.resolve_data_root() != _paths.LEGACY_ROOT


def test_migration_moves_legacy_store(monkeypatch, tmp_path):
    legacy = tmp_path / "legacy-scout"
    (legacy / "bughunt" / "sessions").mkdir(parents=True)
    (legacy / "bughunt" / "sessions" / "s1.json").write_text("{}", encoding="utf-8")
    new_root = tmp_path / "plugin-data" / "agentiker-scout"

    monkeypatch.delenv(_paths.ENV_DATA_DIR, raising=False)
    monkeypatch.setattr(_paths, "LEGACY_ROOT", legacy)
    monkeypatch.setattr(_paths, "DATA_ROOT", new_root)

    moved = _paths.migrate_legacy_root()
    assert moved == new_root
    assert (new_root / "bughunt" / "sessions" / "s1.json").exists()
    assert not legacy.exists()


def test_migration_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.delenv(_paths.ENV_DATA_DIR, raising=False)
    monkeypatch.setattr(_paths, "LEGACY_ROOT", tmp_path / "missing")
    monkeypatch.setattr(_paths, "DATA_ROOT", tmp_path / "new")
    assert _paths.migrate_legacy_root() is None


def test_migration_respects_explicit_env(monkeypatch, tmp_path):
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    monkeypatch.setenv(_paths.ENV_DATA_DIR, str(tmp_path / "explicit"))
    monkeypatch.setattr(_paths, "LEGACY_ROOT", legacy)
    monkeypatch.setattr(_paths, "DATA_ROOT", tmp_path / "new")
    assert _paths.migrate_legacy_root() is None
    assert legacy.exists()


def test_no_hardcoded_legacy_path_in_module_source():
    source = Path(_paths.__file__).read_text(encoding="utf-8")
    # Der alte Pfad darf nur noch als Migrationskonstante auftauchen.
    assert source.count('Path.home() / ".hermes" / "data" / "scout"') == 1
    assert "plugin-data" in source
