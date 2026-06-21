"""Tests für den GenericDependencyDetector (Auto-Discovery aus package.json etc.)."""

from __future__ import annotations

import json
import tempfile
import textwrap
from pathlib import Path

import pytest

from shared.framework_detector import (
    _KNOWN_PREFIXES,
    _TOP_NPM,
    DetectedFramework,
    FrameworkDetector,
    GenericDependencyDetector,
    _lookup_category,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_project():
    """Erstellt ein temporäres Projekt."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        yield root


def _write(root: Path, rel_path: str, content: str = "") -> Path:
    """Schreibt eine Datei im temporären Projekt."""
    fpath = root / rel_path
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text(content)
    return fpath


# ---------------------------------------------------------------------------
# GenericDependencyDetector: package.json
# ---------------------------------------------------------------------------


class TestPackageJsonDetection:
    def test_known_dependencies(self, tmp_project):
        """Bekannte npm-Packages werden mit hoher Confidence erkannt."""
        _write(tmp_project, "package.json", json.dumps({
            "name": "test",
            "dependencies": {
                "react": "^18.2.0",
                "express": "^4.18.0",
                "next": "^14.0.0",
            },
            "devDependencies": {
                "typescript": "^5.3.0",
                "jest": "^29.0.0",
            },
        }))

        detector = GenericDependencyDetector()
        results = detector.detect(tmp_project)

        names = {r.name for r in results}
        assert "react" in names
        assert "express" in names
        assert "next" in names
        assert "typescript" in names
        assert "jest" in names

        react = next(r for r in results if r.name == "react")
        assert react.category == "frontend"
        assert react.confidence == "high"
        assert react.version == "18.2.0"

        typescript = next(r for r in results if r.name == "typescript")
        assert typescript.category == "language"

    def test_prefix_matching(self, tmp_project):
        """Prefix-basierte Kategorisierung funktioniert."""
        _write(tmp_project, "package.json", json.dumps({
            "name": "test",
            "dependencies": {
                "@medusajs/medusa": "^2.0.0",
                "@radix-ui/react-dialog": "^1.0.0",
                "@types/react": "^18.0.0",
                "eslint-plugin-react": "^7.0.0",
            },
        }))

        detector = GenericDependencyDetector()
        results = detector.detect(tmp_project)

        def get(name: str) -> DetectedFramework:
            return next(r for r in results if r.name == name)

        assert get("@medusajs/medusa").category == "backend"
        assert get("@radix-ui/react-dialog").category == "ui_library"
        assert get("@types/react").category == "tooling"
        assert get("eslint-plugin-react").category == "tooling"

    def test_unknown_dependencies(self, tmp_project):
        """Unbekannte Dependencies erhalten 'other' mit low confidence."""
        _write(tmp_project, "package.json", json.dumps({
            "name": "test",
            "dependencies": {
                "some-obscure-lib": "^1.0.0",
                "another-random-pkg": "^2.0.0",
            },
        }))

        detector = GenericDependencyDetector()
        results = detector.detect(tmp_project)

        for r in results:
            assert r.category == "other"
            assert r.confidence == "low"

    def test_dev_and_peer_dependencies(self, tmp_project):
        """devDependencies und peerDependencies werden auch erfasst."""
        _write(tmp_project, "package.json", json.dumps({
            "name": "test",
            "dependencies": {
                "react": "^18.0.0",
            },
            "devDependencies": {
                "vitest": "^1.0.0",
            },
            "peerDependencies": {
                "react-dom": "^18.0.0",
            },
        }))

        detector = GenericDependencyDetector()
        results = detector.detect(tmp_project)

        names = {r.name for r in results}
        assert "react" in names
        assert "vitest" in names
        assert "react-dom" in names

        vitest = next(r for r in results if r.name == "vitest")
        assert vitest.category == "testing"
        assert vitest.confidence == "high"

    def test_version_cleaning(self, tmp_project):
        """Version-Strings werden bereinigt (^ ~ etc. entfernt)."""
        _write(tmp_project, "package.json", json.dumps({
            "name": "test",
            "dependencies": {
                "next": "^14.2.1",
                "react": "~18.2.0",
                "vue": ">=3.4.0 <4.0.0",
            },
        }))

        detector = GenericDependencyDetector()
        results = detector.detect(tmp_project)

        next_fw = next(r for r in results if r.name == "next")
        assert next_fw.version == "14.2.1"

        react_fw = next(r for r in results if r.name == "react")
        assert react_fw.version == "18.2.0"


# ---------------------------------------------------------------------------
# GenericDependencyDetector: requirements.txt
# ---------------------------------------------------------------------------


class TestRequirementsTxtDetection:
    def test_known_python_packages(self, tmp_project):
        """Bekannte Python-Packages werden kategorisiert."""
        _write(tmp_project, "requirements.txt", textwrap.dedent("""
            django==5.0.0
            fastapi==0.110.0
            pandas==2.1.0
            pytest==8.0.0
            psycopg2-binary==2.9.9
        """).strip())

        detector = GenericDependencyDetector()
        results = detector.detect(tmp_project)

        def get(name: str) -> DetectedFramework:
            return next(r for r in results if r.name == name)

        assert get("django").category == "backend"
        assert get("django").confidence == "high"
        assert get("fastapi").category == "backend"
        assert get("pandas").category == "other"
        assert get("pytest").category == "testing"
        assert get("psycopg2-binary").category == "database"

    def test_version_specifiers(self, tmp_project):
        """Verschiedene Version-Specifier werden korrekt extrahiert."""
        _write(tmp_project, "requirements.txt", textwrap.dedent("""
            django>=5.0.0,<6.0.0
            flask~=3.0.0
            numpy!=1.25.0
            requests
            celery>=5.3.0
        """).strip())

        detector = GenericDependencyDetector()
        results = detector.detect(tmp_project)

        names = {r.name for r in results}
        assert "django" in names
        assert "flask" in names
        assert "numpy" in names
        assert "requests" in names
        assert "celery" in names

        django = next(r for r in results if r.name == "django")
        assert django.version == "5.0.0"

    def test_comments_and_options_ignored(self, tmp_project):
        """Kommentare und Optionen (--index-url) werden ignoriert."""
        _write(tmp_project, "requirements.txt", textwrap.dedent("""
            # This is a comment
            --index-url https://example.com/simple
            django==5.0.0
            # Another comment
            flask==3.0.0
        """).strip())

        detector = GenericDependencyDetector()
        results = detector.detect(tmp_project)

        names = {r.name for r in results}
        assert "django" in names
        assert "flask" in names
        assert len(results) == 2


# ---------------------------------------------------------------------------
# GenericDependencyDetector: go.mod
# ---------------------------------------------------------------------------


class TestGoModDetection:
    def test_block_require(self, tmp_project):
        """go.mod mit require-Block wird korrekt geparst."""
        _write(tmp_project, "go.mod", textwrap.dedent("""
            module github.com/example/myapp

            go 1.22

            require (
                github.com/gin-gonic/gin v1.9.1
                github.com/stretchr/testify v1.8.4
                github.com/lib/pq v1.10.9
                go.uber.org/zap v1.26.0
            )
        """).strip())

        detector = GenericDependencyDetector()
        results = detector.detect(tmp_project)

        def get(name: str) -> DetectedFramework:
            return next(r for r in results if r.name == name)

        assert get("github.com/gin-gonic/gin").category == "backend"
        assert get("github.com/gin-gonic/gin").confidence == "high"
        assert get("github.com/stretchr/testify").category == "testing"
        assert get("github.com/lib/pq").category == "database"
        assert get("go.uber.org/zap").category == "other"

    def test_single_line_require(self, tmp_project):
        """Single-line require wird korrekt geparst."""
        _write(tmp_project, "go.mod", textwrap.dedent("""
            module test

            go 1.22

            require github.com/gin-gonic/gin v1.9.1
        """).strip())

        detector = GenericDependencyDetector()
        results = detector.detect(tmp_project)

        assert len(results) == 1
        assert results[0].name == "github.com/gin-gonic/gin"
        assert results[0].version == "1.9.1"

    def test_unknown_go_packages(self, tmp_project):
        """Unbekannte Go-Packages erhalten 'other' Kategorie."""
        _write(tmp_project, "go.mod", textwrap.dedent("""
            module test

            go 1.22

            require (
                github.com/obscure/lib v0.1.0
                example.com/unknown v2.0.0
            )
        """).strip())

        detector = GenericDependencyDetector()
        results = detector.detect(tmp_project)

        for r in results:
            assert r.category == "other"
            assert r.confidence == "low"


# ---------------------------------------------------------------------------
# GenericDependencyDetector: Cargo.toml
# ---------------------------------------------------------------------------


class TestCargoTomlDetection:
    def test_basic_dependencies(self, tmp_project):
        """Einfache Cargo-Abhängigkeiten werden korrekt erkannt."""
        _write(tmp_project, "Cargo.toml", textwrap.dedent("""
            [package]
            name = "myapp"
            version = "0.1.0"

            [dependencies]
            tokio = { version = "1.35", features = ["full"] }
            serde = { version = "1.0", features = ["derive"] }
            reqwest = "0.11"
            chrono = "0.4"
            sqlx = { version = "0.7", features = ["postgres"] }
        """).strip())

        detector = GenericDependencyDetector()
        results = detector.detect(tmp_project)

        def get(name: str) -> DetectedFramework:
            return next(r for r in results if r.name == name)

        assert get("tokio").category == "backend"
        assert get("serde").category == "other"
        assert get("reqwest").category == "other"
        assert get("chrono").category == "other"
        assert get("sqlx").category == "database"

    def test_dev_and_build_dependencies(self, tmp_project):
        """dev-dependencies und build-dependencies werden erfasst."""
        _write(tmp_project, "Cargo.toml", textwrap.dedent("""
            [package]
            name = "myapp"

            [dependencies]
            tokio = "1.35"

            [dev-dependencies]
            tokio-test = "0.4"

            [build-dependencies]
            cc = "1.0"
        """).strip())

        detector = GenericDependencyDetector()
        results = detector.detect(tmp_project)

        names = {r.name for r in results}
        assert "tokio" in names
        assert "tokio-test" in names
        assert "cc" in names

    def test_simple_version_format(self, tmp_project):
        """Einfaches name = 'version' Format wird unterstützt."""
        _write(tmp_project, "Cargo.toml", textwrap.dedent("""
            [package]
            name = "myapp"

            [dependencies]
            actix-web = "4.4"
            diesel = { version = "2.1", features = ["postgres"] }
            redis = "0.24"
        """).strip())

        detector = GenericDependencyDetector()
        results = detector.detect(tmp_project)

        def get(name: str) -> DetectedFramework:
            return next(r for r in results if r.name == name)

        assert get("actix-web").category == "backend"
        assert get("actix-web").confidence == "high"
        assert get("diesel").category == "database"
        assert get("redis").category == "database"


# ---------------------------------------------------------------------------
# Integration: GenericDependencyDetector in FrameworkDetector
# ---------------------------------------------------------------------------


class TestGenericIntegration:
    def test_auto_discovery_in_full_detect(self, tmp_project):
        """GenericDependencyDetector läuft automatisch in FrameworkDetector.detect()."""
        _write(tmp_project, "package.json", json.dumps({
            "name": "test",
            "dependencies": {
                "react": "^18.0.0",
                "express": "^4.18.0",
                "some-obscure-pkg": "^1.0.0",
            },
        }))

        detector = FrameworkDetector(str(tmp_project))
        profile = detector.detect()

        # react wird auch vom REACT_DETECTOR erkannt → dedupliziert
        assert profile.has_framework("react")
        # express wird vom EXPRESS_DETECTOR erkannt
        assert profile.has_framework("express")
        # some-obscure-pkg wird NUR vom GenericDependencyDetector erkannt
        assert profile.has_framework("some-obscure-pkg")

        obscure = profile.get_framework("some-obscure-pkg")
        assert obscure is not None
        assert obscure.category == "other"
        assert obscure.confidence == "low"

    def test_no_duplicates_with_existing_detectors(self, tmp_project):
        """Keine Duplikate mit bestehenden YAML/Python-Detectors."""
        _write(tmp_project, "package.json", json.dumps({
            "name": "test",
            "dependencies": {
                "react": "^18.0.0",
                "vue": "^3.4.0",
                "next": "^14.0.0",
            },
        }))
        _write(tmp_project, "next.config.js",
               "module.exports = {}")

        detector = FrameworkDetector(str(tmp_project))
        profile = detector.detect()

        # Jedes Framework sollte nur einmal vorkommen
        for cat, fw_list in profile.frameworks.items():
            names = [fw.name for fw in fw_list]
            assert len(names) == len(set(names)), f"Duplikate in {cat}: {names}"

    def test_auto_discovery_with_category_filter(self, tmp_project):
        """Auto-Discovery respektiert den categories-Filter."""
        _write(tmp_project, "package.json", json.dumps({
            "name": "test",
            "dependencies": {
                "django": "^5.0.0",
                "react": "^18.0.0",
                "pytest": "^8.0.0",
            },
        }))
        _write(tmp_project, "requirements.txt",
               "django==5.0.0\npytest==8.0.0\n")

        detector = FrameworkDetector(str(tmp_project))
        profile = detector.detect(categories=["backend", "testing"])

        assert profile.has_framework("django")
        assert profile.has_framework("pytest")
        # react ist frontend → sollte nicht auftauchen
        assert not profile.has_framework("react")

    def test_mixed_ecosystems(self, tmp_project):
        """Verschiedene Ecosystems gleichzeitig werden unterstützt."""
        _write(tmp_project, "package.json", json.dumps({
            "name": "test",
            "dependencies": {
                "react": "^18.0.0",
                "axios": "^1.6.0",
            },
        }))
        _write(tmp_project, "requirements.txt",
               "flask==3.0.0\nnumpy==1.26.0\n")
        _write(tmp_project, "go.mod", textwrap.dedent("""
            module test
            go 1.22
            require github.com/gin-gonic/gin v1.9.1
        """).strip())
        _write(tmp_project, "Cargo.toml", textwrap.dedent("""
            [package]
            name = "test"
            [dependencies]
            tokio = "1.35"
        """).strip())

        detector = FrameworkDetector(str(tmp_project))
        profile = detector.detect()

        # Dependencies aus allen Ecosystems sollten da sein
        assert profile.has_framework("react")
        assert profile.has_framework("flask")
        assert profile.has_framework("github.com/gin-gonic/gin")
        assert profile.has_framework("tokio")


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestGenericEdgeCases:
    def test_empty_project(self, tmp_project):
        """Leeres Projekt ohne Dependencies gibt leere Liste."""
        detector = GenericDependencyDetector()
        results = detector.detect(tmp_project)
        assert len(results) == 0

    def test_empty_package_json(self, tmp_project):
        """package.json ohne dependencies gibt leere Liste."""
        _write(tmp_project, "package.json", json.dumps({
            "name": "test",
        }))

        detector = GenericDependencyDetector()
        results = detector.detect(tmp_project)
        assert len(results) == 0

    def test_invalid_json(self, tmp_project):
        """Ungültiges JSON wird ignoriert (kein Crash)."""
        _write(tmp_project, "package.json", "{ invalid json }")

        detector = GenericDependencyDetector()
        results = detector.detect(tmp_project)  # no crash
        assert len(results) == 0

    def test_no_side_effects(self, tmp_project):
        """Detector ist read-only (keine Side-Effects)."""
        _write(tmp_project, "package.json", json.dumps({
            "name": "test",
            "dependencies": {"react": "^18.0.0"},
        }))
        original_content = (tmp_project / "package.json").read_text()

        detector = GenericDependencyDetector()
        detector.detect(tmp_project)

        # Datei-Inhalt muss unverändert sein
        assert (tmp_project / "package.json").read_text() == original_content

    def test_nonexistent_files(self, tmp_project):
        """Keine existierenden Dependency-Dateien → leeres Ergebnis."""
        detector = GenericDependencyDetector()
        results = detector.detect(tmp_project)
        assert len(results) == 0

    def test_performance(self, tmp_project):
        """GenericDependencyDetector ist schnell (< 50ms pro Projekt)."""
        _write(tmp_project, "package.json", json.dumps({
            "name": "test",
            "dependencies": {
                f"pkg{i}": f"^{i}.0.0" for i in range(100)
            },
        }))

        import time
        detector = GenericDependencyDetector()

        start = time.time()
        detector.detect(tmp_project)
        elapsed = (time.time() - start) * 1000  # ms

        assert elapsed < 50, f"Zu langsam: {elapsed:.1f}ms"


# ---------------------------------------------------------------------------
# _lookup_category Unit-Tests
# ---------------------------------------------------------------------------


class TestLookupCategory:
    def test_exact_match(self):
        """Exakter Match in known-Dict wird gefunden."""
        cat = _lookup_category("react", _TOP_NPM, _KNOWN_PREFIXES)
        assert cat == "frontend"

    def test_prefix_match(self):
        """Prefix-Match funktioniert."""
        cat = _lookup_category(
            "@medusajs/client", _TOP_NPM, _KNOWN_PREFIXES
        )
        assert cat == "backend"

    def test_no_match(self):
        """Kein Match → None."""
        cat = _lookup_category(
            "completely-random-package", _TOP_NPM, _KNOWN_PREFIXES
        )
        assert cat is None

    def test_prefix_over_exact(self):
        """Exakter Match hat Vorrang vor Prefix."""
        cat = _lookup_category("react", _TOP_NPM, _KNOWN_PREFIXES)
        assert cat == "frontend"
        # 'react' matched auch 'react-' prefix, aber exact match gewinnt
