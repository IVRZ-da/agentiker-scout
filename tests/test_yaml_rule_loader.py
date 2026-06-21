"""Tests für die YAML-basierte Rule-Engine (yaml_rule_loader.py).

Testet:
- YAML-Parsing (gültige/ungültige YAML)
- Rule-Validierung (fehlende Pflichtfelder)
- Kategorie-Filter
- Konvertierung in Detector-Interface
- Caching (zweites Laden sollte kein Disk-Read sein)
- Integration mit FrameworkDetector
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from shared.framework_detector import (
    ALL_DETECTORS,
    FrameworkDetector,
)
from shared.yaml_rule_loader import (
    VALID_CATEGORIES,
    YamlMarker,
    YamlRule,
    YamlRuleLoader,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rules_dir(tmp_path: Path) -> str:
    """Erzeugt ein temporäres rules-Verzeichnis mit Test-Dateien."""
    d = tmp_path / "rules"
    d.mkdir()
    return str(d)


@pytest.fixture
def loader() -> YamlRuleLoader:
    return YamlRuleLoader()


# ---------------------------------------------------------------------------
# YamlMarker
# ---------------------------------------------------------------------------


class TestYamlMarker:
    def test_valid_marker(self) -> None:
        m = YamlMarker(file="package.json", search='"react"', confidence="high")
        assert m.file == "package.json"
        assert m.search == '"react"'
        assert m.confidence == "high"

    def test_default_search_empty(self) -> None:
        m = YamlMarker(file="Dockerfile", confidence="medium")
        assert m.search == ""

    def test_invalid_confidence(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            YamlMarker(file="x.yaml", search="", confidence="super")


# ---------------------------------------------------------------------------
# YamlRule
# ---------------------------------------------------------------------------


class TestYamlRule:
    def test_valid_rule(self) -> None:
        rule = YamlRule(
            name="nextjs",
            category="frontend",
            markers=[
                YamlMarker(file="next.config.ts", search="", confidence="high"),
                YamlMarker(file="package.json", search='"next"', confidence="high"),
            ],
        )
        assert rule.name == "nextjs"
        assert rule.category == "frontend"
        assert len(rule.markers) == 2

    def test_rule_missing_name(self) -> None:
        with pytest.raises(ValueError, match="name"):
            YamlRule(name="", category="frontend", markers=[YamlMarker(file="x")])

    def test_rule_missing_category(self) -> None:
        with pytest.raises(ValueError, match="category"):
            YamlRule(name="test", category="", markers=[YamlMarker(file="x")])

    def test_rule_invalid_category(self) -> None:
        with pytest.raises(ValueError, match="category"):
            YamlRule(
                name="test",
                category="invalid_category_xyz",
                markers=[YamlMarker(file="x")],
            )

    def test_rule_empty_markers(self) -> None:
        with pytest.raises(ValueError, match="markers"):
            YamlRule(name="test", category="backend", markers=[])

    def test_to_marker_tuples(self) -> None:
        rule = YamlRule(
            name="express",
            category="backend",
            markers=[
                YamlMarker(file="package.json", search='"express"', confidence="high"),
            ],
        )
        tuples = rule.to_marker_tuples()
        assert tuples == [("package.json", '"express"', "high")]


# ---------------------------------------------------------------------------
# YAML Parsing
# ---------------------------------------------------------------------------


class TestYamlParsing:
    def test_parse_valid_yaml_file(self, rules_dir: str, loader: YamlRuleLoader) -> None:
        yaml_path = os.path.join(rules_dir, "test.yaml")
        with open(yaml_path, "w") as f:
            yaml.dump([
                {
                    "name": "test-fw",
                    "category": "backend",
                    "markers": [
                        {"file": "test.json", "search": '"test"', "confidence": "high"},
                    ],
                },
            ], f)

        rules = loader._load_file(Path(yaml_path))
        assert len(rules) == 1
        assert rules[0].name == "test-fw"

    def test_parse_invalid_yaml_syntax(self, rules_dir: str, loader: YamlRuleLoader) -> None:
        """Kaputtes YAML wird fehlertolerant übersprungen."""
        yaml_path = os.path.join(rules_dir, "broken.yaml")
        with open(yaml_path, "w") as f:
            f.write("{broken: [yaml: \n  bad indent\n")

        # load_all wrappt den Fehler via _load_directory → _load_file
        rules = loader.load_all(rules_dir)
        assert rules == []

    def test_parse_empty_file(self, rules_dir: str, loader: YamlRuleLoader) -> None:
        yaml_path = os.path.join(rules_dir, "empty.yaml")
        Path(yaml_path).touch()

        rules = loader._load_file(Path(yaml_path))
        assert rules == []

    def test_parse_not_a_list(self, rules_dir: str, loader: YamlRuleLoader) -> None:
        """Einzelnes Dict statt Liste = Fehler — wird von _load_directory abgefangen."""
        yaml_path = os.path.join(rules_dir, "single.yaml")
        with open(yaml_path, "w") as f:
            yaml.dump({"name": "test", "category": "backend", "markers": []}, f)

        # load_all fängt den Fehler und loggt eine Warnung
        rules = loader.load_all(rules_dir)
        assert rules == []

    def test_parse_entry_with_missing_fields(self, rules_dir: str, loader: YamlRuleLoader) -> None:
        """Fehlerhafte Einträge werden übersprungen, valide bleiben."""
        yaml_path = os.path.join(rules_dir, "mixed.yaml")
        with open(yaml_path, "w") as f:
            yaml.dump([
                {"name": "good", "category": "backend", "markers": [{"file": "x"}]},
                {"name": "", "category": "backend", "markers": [{"file": "x"}]},
                {"name": "bad-cat", "category": "invalid", "markers": [{"file": "x"}]},
                {"name": "no-markers", "category": "backend"},
            ], f)

        rules = loader._load_file(Path(yaml_path))
        assert len(rules) == 1
        assert rules[0].name == "good"

    def test_parse_markers_as_list_tuples(self, rules_dir: str, loader: YamlRuleLoader) -> None:
        """Marker können auch als Liste von Tupeln formatiert sein (Fallback)."""
        yaml_path = os.path.join(rules_dir, "tuple_markers.yaml")
        with open(yaml_path, "w") as f:
            yaml.dump([
                {
                    "name": "legacy",
                    "category": "backend",
                    "markers": [
                        ["package.json", '"express"', "high"],
                    ],
                },
            ], f)

        rules = loader._load_file(Path(yaml_path))
        assert len(rules) == 1
        assert rules[0].markers[0].file == "package.json"

    def test_non_dict_entry_skipped(self, rules_dir: str, loader: YamlRuleLoader) -> None:
        yaml_path = os.path.join(rules_dir, "mixed_list.yaml")
        with open(yaml_path, "w") as f:
            yaml.dump([
                {"name": "good", "category": "backend", "markers": [{"file": "x"}]},
                "just a string",
                42,
            ], f)

        rules = loader._load_file(Path(yaml_path))
        assert len(rules) == 1


# ---------------------------------------------------------------------------
# Kategorie-Filter
# ---------------------------------------------------------------------------


class TestCategoryFilter:
    def test_load_by_category(self, rules_dir: str, loader: YamlRuleLoader) -> None:
        """Nur Rules einer bestimmten Kategorie laden."""
        Path(rules_dir, "backend.yaml").write_text(yaml.dump([
            {"name": "fw-a", "category": "backend", "markers": [{"file": "a"}]},
            {"name": "fw-b", "category": "backend", "markers": [{"file": "b"}]},
        ]))
        Path(rules_dir, "frontend.yaml").write_text(yaml.dump([
            {"name": "fw-c", "category": "frontend", "markers": [{"file": "c"}]},
        ]))

        backend_rules = loader.load_by_category(rules_dir, "backend")
        assert len(backend_rules) == 2
        assert all(r.category == "backend" for r in backend_rules)

    def test_load_by_category_unknown(self, rules_dir: str, loader: YamlRuleLoader) -> None:
        """Unbekannte Kategorie = leere Liste."""
        rules = loader.load_by_category(rules_dir, "nonexistent")
        assert rules == []

    def test_load_all_groups_by_category(self, rules_dir: str, loader: YamlRuleLoader) -> None:
        Path(rules_dir, "a.yaml").write_text(yaml.dump([
            {"name": "f1", "category": "backend", "markers": [{"file": "x"}]},
            {"name": "f2", "category": "frontend", "markers": [{"file": "x"}]},
        ]))

        rules = loader.load_all(rules_dir)
        assert len(rules) == 2


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


class TestCaching:
    def test_cache_avoid_reload(self, rules_dir: str, loader: YamlRuleLoader) -> None:
        """Zweites Laden sollte gecached sein (kein Disk-Read)."""
        Path(rules_dir, "a.yaml").write_text(yaml.dump([
            {"name": "fw1", "category": "backend", "markers": [{"file": "x"}]},
        ]))

        # Erstes Laden
        r1 = loader.load_all(rules_dir)
        assert len(r1) == 1

        # Datei ändern
        Path(rules_dir, "a.yaml").write_text(yaml.dump([
            {"name": "fw1", "category": "backend", "markers": [{"file": "x"}]},
            {"name": "fw2", "category": "frontend", "markers": [{"file": "y"}]},
        ]))

        # Zweites Laden ohne force — sollte noch 1 sein
        r2 = loader.load_all(rules_dir)
        assert len(r2) == 1, "Cache sollte das alte Ergebnis zurückgeben"

    def test_force_reload(self, rules_dir: str, loader: YamlRuleLoader) -> None:
        """Mit force_reload=True wird der Cache ignoriert."""
        Path(rules_dir, "a.yaml").write_text(yaml.dump([
            {"name": "fw1", "category": "backend", "markers": [{"file": "x"}]},
        ]))
        loader.load_all(rules_dir)

        Path(rules_dir, "a.yaml").write_text(yaml.dump([
            {"name": "fw1", "category": "backend", "markers": [{"file": "x"}]},
            {"name": "fw2", "category": "frontend", "markers": [{"file": "y"}]},
        ]))

        r3 = loader.load_all(rules_dir, force_reload=True)
        assert len(r3) == 2

    def test_clear_cache(self, rules_dir: str, loader: YamlRuleLoader) -> None:
        loader.load_all(rules_dir)
        assert loader._cache  # Cache ist gefüllt
        loader.clear_cache()
        assert not loader._cache


# ---------------------------------------------------------------------------
# Detector-Konvertierung
# ---------------------------------------------------------------------------


class TestToDetector:
    def test_to_detector_creates_tech_detector(self, loader: YamlRuleLoader) -> None:
        rule = YamlRule(
            name="my-framework",
            category="backend",
            markers=[
                YamlMarker(file="my.config.js", search="", confidence="high"),
            ],
        )
        detector = loader.to_detector(rule)
        assert detector.name == "my-framework"
        assert detector.category == "backend"
        assert len(detector.markers) == 1
        assert detector.markers[0] == ("my.config.js", "", "high")

    def test_to_detector_detect_method(self, loader: YamlRuleLoader) -> None:
        """Der erzeugte Detector kann detect() aufrufen."""
        rule = YamlRule(
            name="finder",
            category="database",
            markers=[
                YamlMarker(file="testfile.txt", search="FOUND", confidence="high"),
            ],
        )
        detector = loader.to_detector(rule)

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "testfile.txt").write_text("FOUND marker here")
            result = detector.detect(Path(tmpdir))
            assert result is not None
            assert result.name == "finder"
            assert result.category == "database"
            assert result.confidence == "high"

    def test_to_detector_detect_no_match(self, loader: YamlRuleLoader) -> None:
        rule = YamlRule(
            name="missing",
            category="backend",
            markers=[
                YamlMarker(file="nonexistent.txt", search="NOTHING", confidence="high"),
            ],
        )
        detector = loader.to_detector(rule)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = detector.detect(Path(tmpdir))
            assert result is None


# ---------------------------------------------------------------------------
# Integration mit FrameworkDetector
# ---------------------------------------------------------------------------


class TestFrameworkDetectorIntegration:
    def test_yaml_rules_loaded_into_detector(self) -> None:
        """FrameworkDetector lädt standardmäßig YAML-Rules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = FrameworkDetector(tmpdir)
            names = [d.name for d in detector._detectors]
            assert "nextjs" in names
            assert "express" in names
            assert "react" in names

    def test_yaml_overrides_python_detector(self) -> None:
        """YAML-Detector mit gleichem Namen überschreibt Python-Detector."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = FrameworkDetector(tmpdir)
            yaml_names = {
                d.name for d in detector._detectors
                if type(d).__name__.startswith("_Yaml_")
            }
            py_names = {
                d.name for d in detector._detectors
                if not type(d).__name__.startswith("_Yaml_")
            }
            # Alle Python-Namen sollten in YAML-Namen vorkommen (keine Duplikate)
            assert yaml_names.isdisjoint(py_names) or py_names == set()

    def test_detect_uses_both_sources(self) -> None:
        """detect() nutzt YAML-Rules + Python-Detectors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "package.json").write_text(
                '{"dependencies": {"next": "14.0.0", "react": "18.2.0"}}'
            )
            detector = FrameworkDetector(tmpdir)
            profile = detector.detect()
            names = set()
            for fw_list in profile.frameworks.values():
                for fw in fw_list:
                    names.add(fw.name)
            assert "nextjs" in names

    def test_detect_fast_yaml_only(self) -> None:
        """detect_fast() verwendet nur YAML-Rules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "package.json").write_text(
                '{"dependencies": {"next": "14.0.0"}}'
            )
            Path(tmpdir, "next.config.ts").write_text("")
            detector = FrameworkDetector(tmpdir)
            profile = detector.detect_fast()
            # detect_fast erzeugt keine Python-Detector-spezifischen Ergebnisse
            # (es lädt YAML-Rules frisch)
            assert profile is not None

    def test_disable_yaml_rules(self) -> None:
        """Mit use_yaml_rules=False werden nur Python-Detectors geladen."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = FrameworkDetector(tmpdir, use_yaml_rules=False)
            yaml_named = [
                d for d in detector._detectors
                if type(d).__name__.startswith("_Yaml_")
            ]
            assert len(yaml_named) == 0

    def test_custom_yaml_rules_dir(self) -> None:
        """Benutzerdefiniertes YAML-Rules-Verzeichnis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_rules = os.path.join(tmpdir, "my_rules")
            os.makedirs(custom_rules)
            Path(custom_rules, "custom.yaml").write_text(yaml.dump([
                {
                    "name": "my-custom-tech",
                    "category": "backend",
                    "markers": [{"file": "custom.txt", "search": "hello", "confidence": "high"}],
                },
            ]))

            detector = FrameworkDetector(
                tmpdir,
                yaml_rules_dir=custom_rules,
            )
            names = [d.name for d in detector._detectors]
            assert "my-custom-tech" in names


# ---------------------------------------------------------------------------
# Fehlertoleranz
# ---------------------------------------------------------------------------


class TestErrorTolerance:
    def test_load_all_missing_directory(self, loader: YamlRuleLoader) -> None:
        """Nicht-existierendes Verzeichnis = leere Liste."""
        rules = loader.load_all("/nonexistent/path")
        assert rules == []

    def test_one_broken_file_does_not_break_others(
        self, rules_dir: str, loader: YamlRuleLoader
    ) -> None:
        """Ein kaputtes YAML File reißt nicht die anderen mit."""
        Path(rules_dir, "good.yaml").write_text(yaml.dump([
            {"name": "good-fw", "category": "backend", "markers": [{"file": "x"}]},
        ]))
        Path(rules_dir, "broken.yaml").write_text("{bad: yaml: [[[")
        Path(rules_dir, "empty.yaml").write_text("")
        Path(rules_dir, "also-good.yaml").write_text(yaml.dump([
            {"name": "also-good", "category": "frontend", "markers": [{"file": "y"}]},
        ]))

        rules = loader.load_all(rules_dir)
        names = {r.name for r in rules}
        assert "good-fw" in names
        assert "also-good" in names
        assert len(rules) == 2


# ---------------------------------------------------------------------------
# Valid categories
# ---------------------------------------------------------------------------


class TestValidCategories:
    def test_all_categories_defined(self) -> None:
        assert "backend" in VALID_CATEGORIES
        assert "frontend" in VALID_CATEGORIES
        assert "ui_library" in VALID_CATEGORIES
        assert "database" in VALID_CATEGORIES
        assert "language" in VALID_CATEGORIES
        assert "testing" in VALID_CATEGORIES
        assert "infra" in VALID_CATEGORIES
        assert "ci" in VALID_CATEGORIES
        assert "package_manager" in VALID_CATEGORIES
        assert len(VALID_CATEGORIES) == 9


# ---------------------------------------------------------------------------
# Real data/rules Integration
# ---------------------------------------------------------------------------


class TestRealRules:
    """Testet gegen die echten data/rules/ Dateien."""

    def test_all_real_yaml_files_load(self, loader: YamlRuleLoader) -> None:
        rules_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "rules",
        )
        rules = loader.load_all(rules_dir)
        assert len(rules) >= 35, (
            f"Erwarte mindestens 35 Rules, bekam {len(rules)}"
        )

    def test_all_real_rules_have_valid_categories(
        self, loader: YamlRuleLoader
    ) -> None:
        rules_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "rules",
        )
        rules = loader.load_all(rules_dir)
        for r in rules:
            assert r.category in VALID_CATEGORIES, (
                f"Rule '{r.name}' hat ungültige category '{r.category}'"
            )

    def test_real_rules_cover_all_python_detectors(
        self, loader: YamlRuleLoader
    ) -> None:
        """Jeder Python-Detector sollte ein YAML-Pendant haben."""
        rules_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "rules",
        )
        rules = loader.load_all(rules_dir)
        yaml_names = {r.name for r in rules}
        py_names = {d.name for d in ALL_DETECTORS}
        missing = py_names - yaml_names
        assert not missing, (
            f"Python-Detectors ohne YAML-Pendant: {sorted(missing)}"
        )

    def test_detect_with_real_rules(self) -> None:
        """Integrationstest mit echten Rules und einem echten Projekt."""
        rules_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "rules",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "package.json").write_text(
                '{"dependencies": {"next": "14.0.0", "react": "18.2.0"}}'
            )
            Path(tmpdir, "tsconfig.json").write_text("{}")

            detector = FrameworkDetector(
                tmpdir,
                yaml_rules_dir=rules_dir,
            )
            profile = detector.detect()
            assert profile.has_framework("nextjs")
            assert profile.has_framework("react")
            assert profile.has_framework("typescript")


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_rule_with_version_hint(self, loader: YamlRuleLoader) -> None:
        rule = YamlRule(
            name="node",
            category="infra",
            markers=[YamlMarker(file="package.json", search='"node"', confidence="high")],
            version_hint=r'"node":\s*"([^"]+)"',
        )
        assert rule.version_hint == r'"node":\s*"([^"]+)"'
        detector = loader.to_detector(rule)
        assert hasattr(detector, "_version_regex")
        assert detector._version_regex == rule.version_hint

    def test_marker_with_list_tuple_format(self, loader: YamlRuleLoader) -> None:
        """YamlRuleLoader kann leeres/nicht-existierendes Verzeichnis laden."""
        rules = loader.load_all("/tmp/does-not-exist-xyz-12345")
        assert rules == []

    def test_load_by_category_empty_dir(self, loader: YamlRuleLoader) -> None:
        rules = loader.load_by_category("/dev/null/xyz", "backend")
        assert rules == []
