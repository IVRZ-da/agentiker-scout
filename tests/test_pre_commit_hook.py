"""Regressionstests für scripts/pre-commit-hook.

Der Hook hat keine ``.py``-Endung (er wird per ``core.hooksPath`` aufgerufen),
also wird er über einen ``SourceFileLoader`` geladen. Beim Import läuft nichts
ausser den Modul-Konstanten — ``main()`` hängt am ``__main__``-Guard.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = REPO_ROOT / "scripts" / "pre-commit-hook"


@pytest.fixture(scope="module")
def hook():
    loader = importlib.machinery.SourceFileLoader("scout_pre_commit_hook", str(HOOK_PATH))
    spec = importlib.util.spec_from_loader("scout_pre_commit_hook", loader)
    assert spec is not None, "Hook konnte nicht als Modul geladen werden"
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class TestIsDocPath:
    """Nur echte Doku darf die Tests überspringen."""

    @pytest.mark.parametrize(
        "pfad",
        ["CHANGELOG.md", "README.md", "docs/architecture.md", "docs/x.png",
         "assets/logo.svg", "LICENSE", "NOTICE", ".gitignore", "./CHANGELOG.md"],
    )
    def test_dokumentation(self, hook, pfad):
        assert hook.is_doc_path(pfad) is True

    @pytest.mark.parametrize(
        "pfad",
        [
            "bughunt/data/patterns_data.json",  # der Regelsatz selbst
            "plugin.yaml",                      # Tool-Oberfläche
            "pyproject.toml",
            "VERSION",
            "scripts/pre-commit-hook",          # der Hook selbst
            "shared/scan_paths.py",
            "Makefile",
            "data/sessions/x.json",
        ],
    )
    def test_keine_dokumentation(self, hook, pfad):
        assert hook.is_doc_path(pfad) is False


class TestDetermineTestFiles:
    def test_nur_doku_ergibt_keine_tests(self, hook):
        assert hook.determine_test_files(["CHANGELOG.md"]) == []
        assert hook.determine_test_files(["CHANGELOG.md", "docs/x.png"]) == []

    def test_regelsatz_json_laesst_tests_laufen(self, hook):
        """Der gemeldete Bug: nur JSON geändert → 'Nur Dokumentation geändert'."""
        ergebnis = hook.determine_test_files(["bughunt/data/patterns_data.json"])
        assert ergebnis, "Änderung am Pattern-Regelsatz darf die Tests nicht überspringen"
        assert ergebnis != ["all"]
        assert "tests/test_bughunt/test_patterns.py" in ergebnis
        assert "tests/test_bughunt/test_tools_mgmt.py" in ergebnis
        assert "tests/test_bughunt/test_scan_paths_and_regex.py" in ergebnis

    def test_manifest_erzwingt_volle_suite(self, hook):
        assert hook.determine_test_files(["plugin.yaml"]) == ["all"]

    def test_hook_aenderung_erzwingt_volle_suite(self, hook):
        assert hook.determine_test_files(["scripts/pre-commit-hook"]) == ["all"]

    def test_unbekannte_nicht_doku_datei_erzwingt_volle_suite(self, hook):
        # Kein Mapping, keine Doku → fail-closed.
        assert hook.determine_test_files(["shared/gibt_es_nicht_im_map.py"]) == ["all"]
        assert hook.determine_test_files(["Makefile"]) == ["all"]

    def test_modul_aenderung_zieht_seine_suite(self, hook):
        assert hook.determine_test_files(["bughunt/bughunt_hooks.py"]) == [
            "tests/test_bughunt/test_hooks.py"
        ]

    def test_geloeschte_testdatei_erzwingt_volle_suite(self, hook):
        assert hook.determine_test_files(["tests/test_geloescht_1234.py"]) == ["all"]

    def test_nur_testdatei_laeuft_allein(self, hook):
        assert hook.determine_test_files(["tests/test_bughunt/test_patterns.py"]) == [
            "tests/test_bughunt/test_patterns.py"
        ]

    def test_testdatei_plus_modul_laeuft_beide(self, hook):
        """Früher: „Testdatei geändert → nur diese" — das Modul fiel unter den Tisch."""
        ergebnis = hook.determine_test_files(
            ["tests/test_bughunt/test_patterns.py", "bughunt/bughunt_hooks.py"]
        )
        assert "tests/test_bughunt/test_patterns.py" in ergebnis
        assert "tests/test_bughunt/test_hooks.py" in ergebnis

    def test_commit_aus_hook_und_test_und_manifest(self, hook):
        """Realfall: Hook + neue Testdatei + plugin.yaml/VERSION im selben Commit."""
        ergebnis = hook.determine_test_files([
            "CHANGELOG.md", "VERSION", "plugin.yaml", "pyproject.toml",
            "scripts/pre-commit-hook", "tests/test_pre_commit_hook.py",
        ])
        assert ergebnis == ["all"]

    def test_conftest_erzwingt_volle_suite(self, hook):
        """conftest.py wirkt auf jede Suite."""
        assert hook.determine_test_files(["tests/conftest.py"]) == ["all"]

    def test_keine_leeren_zuordnungen_im_katalog(self, hook):
        """Eine leere Liste hätte früher stillschweigend „keine Tests" ergeben."""
        leer = [mod for mod, tfs in hook.MODULE_TEST_MAP.items() if not tfs]
        assert leer == [], f"Module ohne Test-Zuordnung: {leer}"

    def test_alle_pfade_existieren(self, hook):
        """Nie eine Teilmenge aus nicht existierenden Dateien zurückgeben."""
        for changed in (
            ["bughunt/data/patterns_data.json"],
            ["bughunt/bughunt_hooks.py"],
            ["analysis/analysis_core.py"],
        ):
            for pfad in hook.determine_test_files(changed):
                if pfad == "all":
                    continue
                assert os.path.exists(REPO_ROOT / pfad), f"{pfad} existiert nicht"


class TestResolveTestFile:
    def test_kurzname_wird_aufgeloest(self, hook):
        assert hook.resolve_test_file("test_bughunt/patterns") == "tests/test_bughunt/test_patterns.py"

    def test_vollstaendiger_name_bleibt(self, hook):
        assert hook.resolve_test_file("test_bughunt/test_patterns") == "tests/test_bughunt/test_patterns.py"

    def test_mit_py_endung(self, hook):
        assert hook.resolve_test_file("test_bughunt/test_patterns.py") == "tests/test_bughunt/test_patterns.py"

    def test_unbekannt_ist_none(self, hook):
        assert hook.resolve_test_file("test_bughunt/gibt_es_nicht") is None

    def test_verzeichnis_wird_akzeptiert(self, hook):
        assert hook.resolve_test_file("test_bughunt") == "tests/test_bughunt"

    def test_alle_katalog_eintraege_aufloesbar(self, hook):
        """Früher existierten nur 6 von 59 Einträgen — der Rest fiel still weg."""
        offen = [
            (mod, tf)
            for mod, tfs in hook.MODULE_TEST_MAP.items()
            for tf in tfs
            if tf != "all" and hook.resolve_test_file(tf) is None
        ]
        assert offen == [], f"nicht auflösbare Mapping-Einträge: {offen[:10]}"
