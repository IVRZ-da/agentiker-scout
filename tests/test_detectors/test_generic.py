"""Tests für shared/detectors/generic.py — GenericDependencyDetector."""

from __future__ import annotations

import json
from pathlib import Path

from scout.shared.detectors.generic import GenericDependencyDetector


class TestGenericDependencyDetector:
    def test_empty_project(self, tmp_path: Path):
        detector = GenericDependencyDetector()
        results = detector.detect(tmp_path)
        assert results == []

    def test_package_json_react(self, tmp_path: Path):
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"dependencies": {"react": "^19.0.0", "next": "15.0.0"}}))
        detector = GenericDependencyDetector()
        results = detector.detect(tmp_path)
        names = [r.name for r in results]
        assert "react" in names
        assert "next" in names

    def test_package_json_dev_and_peer(self, tmp_path: Path):
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({
            "devDependencies": {"vitest": "^2.0.0"},
            "peerDependencies": {"react-dom": "^19.0.0"},
        }))
        detector = GenericDependencyDetector()
        results = detector.detect(tmp_path)
        names = [r.name for r in results]
        assert "vitest" in names
        assert "react-dom" in names

    def test_package_json_broken_json(self, tmp_path: Path):
        pkg = tmp_path / "package.json"
        pkg.write_text("{broken json")
        detector = GenericDependencyDetector()
        results = detector.detect(tmp_path)
        assert results == []

    def test_go_mod(self, tmp_path: Path):
        mod = tmp_path / "go.mod"
        mod.write_text("module example\n\ngo 1.22\n\nrequire (\n\tgithub.com/gin-gonic/gin v1.9\n\tgithub.com/labstack/echo v4.0\n)\n")
        detector = GenericDependencyDetector()
        results = detector.detect(tmp_path)
        names = [r.name for r in results]
        assert len(names) >= 2

    def test_go_mod_single_require(self, tmp_path: Path):
        mod = tmp_path / "go.mod"
        mod.write_text("module example\n\ngo 1.22\n\nrequire github.com/gin-gonic/gin v1.9\n")
        detector = GenericDependencyDetector()
        results = detector.detect(tmp_path)
        assert any("gin" in r.name for r in results)

    def test_requirements_txt(self, tmp_path: Path):
        req = tmp_path / "requirements.txt"
        req.write_text("flask==3.0.0\ndjango>=5.0.0\nfastapi\n")
        detector = GenericDependencyDetector()
        results = detector.detect(tmp_path)
        names = [r.name for r in results]
        assert "flask" in names
        assert "django" in names
        assert "fastapi" in names

    def test_requirements_txt_with_comments_and_blanks(self, tmp_path: Path):
        req = tmp_path / "requirements.txt"
        req.write_text("# Kommentar\nflask==3.0\n\npydantic>=2.0\n")
        detector = GenericDependencyDetector()
        results = detector.detect(tmp_path)
        names = [r.name for r in results]
        assert "flask" in names
        assert "pydantic" in names

    def test_requirements_txt_version_parse(self, tmp_path: Path):
        req = tmp_path / "requirements.txt"
        req.write_text("flask>=2.3,<3.0\n")
        detector = GenericDependencyDetector()
        results = detector.detect(tmp_path)
        if results:
            r = results[0]
            assert r.name == "flask"
            assert r.evidence[0].version is not None

    def test_cargo_toml(self, tmp_path: Path):
        cargo = tmp_path / "Cargo.toml"
        cargo.write_text("[dependencies]\nserde = \"1.0\"\ntokio = { version = \"1\", features = [\"full\"] }\n")
        detector = GenericDependencyDetector()
        results = detector.detect(tmp_path)
        names = [r.name for r in results]
        assert "serde" in names or "tokio" in names

    def test_cargo_toml_broken(self, tmp_path: Path):
        cargo = tmp_path / "Cargo.toml"
        cargo.write_text("[dependencies\nbroken")
        detector = GenericDependencyDetector()
        results = detector.detect(tmp_path)
        assert results == []

    def test_all_sources(self, tmp_path: Path):
        """Gleichzeitiges Vorhandensein aller Package-Dateien."""
        (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"vue": "^3.0.0"}}))
        (tmp_path / "go.mod").write_text("module x\n\nrequire github.com/gin-gonic/gin v1.0\n")
        (tmp_path / "requirements.txt").write_text("django==5.0\n")
        detector = GenericDependencyDetector()
        results = detector.detect(tmp_path)
        names = [r.name for r in results]
        assert "vue" in names
        assert "django" in names

    def test_category_assignment(self, tmp_path: Path):
        """Bekannte Packages bekommen die richtige Kategorie."""
        (tmp_path / "package.json").write_text(json.dumps({
            "dependencies": {"react": "^19.0.0", "postgresql": "^1.0.0", "unknown-lib-xyz": "^1.0.0"}
        }))
        detector = GenericDependencyDetector()
        results = detector.detect(tmp_path)
        cat_map = {r.name: r.category for r in results}
        expected_frontend = {"react"}
        for name in expected_frontend:
            assert cat_map.get(name) in ("frontend", "ui_library"), f"{name}: falsche Kategorie"
