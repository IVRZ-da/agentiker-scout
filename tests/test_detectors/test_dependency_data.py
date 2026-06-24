"""Tests für shared/detectors/dependency_data.py — Lookup-Tabellen."""

from __future__ import annotations

from scout.shared.detectors.dependency_data import (
    _DOCKER_IMAGE_MAP,
    _DOTENV_PREFIXES,
    _KNOWN_PREFIXES,
    _TOP_CARGO,
    _TOP_GO,
    _TOP_NPM,
    _TOP_PYPI,
    _lookup_category,
)


class TestTopNpm:
    def test_has_common_packages(self):
        assert "react" in _TOP_NPM
        assert "next" in _TOP_NPM
        assert "express" in _TOP_NPM
        assert "vue" in _TOP_NPM

    def test_categories_are_strings(self):
        for pkg, cat in _TOP_NPM.items():
            assert isinstance(cat, str), f"{pkg}: category ist kein String"

    def test_no_duplicates(self):
        names = list(_TOP_NPM.keys())
        duplicates = [n for n in names if names.count(n) > 1]
        assert not duplicates, f"Doppelte Einträge: {duplicates}"


class TestTopGo:
    def test_has_common_libs(self):
        assert "github.com/gin-gonic/gin" in _TOP_GO
        assert "github.com/labstack/echo" in _TOP_GO

    def test_values_are_categories(self):
        for lib, cat in _TOP_GO.items():
            assert isinstance(cat, str)


class TestTopPypi:
    def test_has_common_packages(self):
        assert "flask" in _TOP_PYPI
        assert "django" in _TOP_PYPI
        assert "fastapi" in _TOP_PYPI

    def test_values_are_categories(self):
        for pkg, cat in _TOP_PYPI.items():
            assert isinstance(cat, str)


class TestTopCargo:
    def test_has_common_crates(self):
        assert "serde" in _TOP_CARGO
        assert "tokio" in _TOP_CARGO

    def test_values_are_categories(self):
        for crate, cat in _TOP_CARGO.items():
            assert isinstance(cat, str)


class TestKnownPrefixes:
    def test_has_common_prefixes(self):
        assert "@angular/" in _KNOWN_PREFIXES
        assert "@nestjs/" in _KNOWN_PREFIXES

    def test_all_start_with_at_or_special(self):
        """Prefixes können mit @ oder anderen Mustern starten."""
        for prefix in _KNOWN_PREFIXES:
            assert len(prefix) > 0, "Leeres Prefix"


class TestLookupCategory:
    def test_npm_top_found(self):
        result = _lookup_category("react", _TOP_NPM, _KNOWN_PREFIXES)
        assert result == "frontend"

    def test_npm_prefix_found(self):
        result = _lookup_category("@angular/core", _TOP_NPM, _KNOWN_PREFIXES)
        assert result is not None

    def test_unknown_package(self):
        result = _lookup_category("some-random-pkg-123", _TOP_NPM, _KNOWN_PREFIXES)
        assert result is None

    def test_empty_name(self):
        result = _lookup_category("", _TOP_NPM, _KNOWN_PREFIXES)
        assert result is None


class TestDotenvPrefixes:
    def test_has_common_prefixes(self):
        assert "SENTRY_" in _DOTENV_PREFIXES
        assert "STRIPE_" in _DOTENV_PREFIXES

    def test_values_are_tuples(self):
        """Values sind (category, framework_name) Tupel."""
        for prefix, val in _DOTENV_PREFIXES.items():
            assert isinstance(val, tuple), f"{prefix}: value ist kein Tuple"
            assert len(val) == 2, f"{prefix}: Tuple hat nicht 2 Elemente"
            assert isinstance(val[0], str), f"{prefix}: category kein String"


class TestDockerImageMap:
    def test_has_common_images(self):
        assert "postgres" in _DOCKER_IMAGE_MAP
        assert "redis" in _DOCKER_IMAGE_MAP
        assert "nginx" in _DOCKER_IMAGE_MAP

    def test_values_have_category(self):
        """Values sind (category, name) Tupel."""
        for img, meta in _DOCKER_IMAGE_MAP.items():
            assert isinstance(meta, tuple), f"{img}: value ist kein Tuple"
            assert len(meta) >= 1
            assert isinstance(meta[0], str), f"{img}: category kein String"
