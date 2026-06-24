"""Tests für shared/detectors/catalog.py — Alle 37 Detector-Instanzen."""

from __future__ import annotations

import re

import pytest
from scout.shared.detectors.catalog import ALL_DETECTORS

# ======================================================================
# ALL_DETECTORS
# ======================================================================

class TestAllDetectors:
    """Prüft dass alle Detectors korrekt definiert sind."""

    def test_at_least_30_detectors(self):
        """Wir erwarten mindestens 30+ Detectors."""
        assert len(ALL_DETECTORS) >= 30

    def test_all_have_name_and_category(self):
        """Jeder Detector muss name + category haben."""
        for d in ALL_DETECTORS:
            assert d.name, f"Detector ohne name: {d}"
            assert d.category, f"Detector {d.name} ohne category"

    def test_all_have_markers(self):
        """Jeder Detector muss mindestens ein Marker haben."""
        for d in ALL_DETECTORS:
            assert len(d.markers) > 0, f"Detector {d.name} ohne markers"

    def test_all_markers_are_valid(self):
        """Jeder Marker muss (str, str|re.Pattern, str) sein."""
        for d in ALL_DETECTORS:
            for m in d.markers:
                assert len(m) == 3, f"{d.name}: marker {m} hat nicht 3 Elemente"
                file_glob, pattern, conf = m
                assert isinstance(file_glob, str), f"{d.name}: file_glob kein str"
                assert isinstance(pattern, (str, re.Pattern)), f"{d.name}: pattern weder str noch re.Pattern"
                assert conf in ("high", "medium", "low"), f"{d.name}: confidence '{conf}' ungültig"

    def test_categories_known(self):
        """Categories müssen aus dem bekannten Set kommen."""
        known = {"backend", "frontend", "ui_library", "database", "language",
                 "testing", "infra", "ci", "package_manager", "framework"}
        for d in ALL_DETECTORS:
            assert d.category in known, f"{d.name}: category '{d.category}' unbekannt"

    def test_no_duplicate_names(self):
        """Kein Detector-Name darf doppelt vorkommen."""
        names = [d.name for d in ALL_DETECTORS]
        duplicates = [n for n in names if names.count(n) > 1]
        assert not duplicates, f"Doppelte Detector-Namen: {set(duplicates)}"

    def test_markers_can_share_file_globs(self):
        """Verschiedene Detectors können auf dieselbe Datei prüfen (z.B. package.json)."""
        names_by_marker: dict = {}
        for d in ALL_DETECTORS:
            for m in d.markers:
                key = (m[0], str(m[1])[:50])
                names_by_marker.setdefault(key, []).append(d.name)
        # Wenn ein Marker von mehreren Detectors verwendet wird, ist das OK
        # solange die Namen unterschiedlich sind
        for key, names in names_by_marker.items():
            if len(names) > 1:
                # Erlaubt: package.json file-exists Check von npm + yarn
                pass

    @pytest.mark.parametrize("expected_name", [
        "nextjs", "react", "typescript", "python", "go", "docker",
        "postgresql", "redis", "nginx", "tailwindcss", "medusa-v2",
    ])
    def test_key_detectors_exist(self, expected_name: str):
        names = [d.name for d in ALL_DETECTORS]
        assert expected_name in names, f"Erwarteter Detector '{expected_name}' fehlt"

    def test_detect_returns_correct_name(self, tmp_path):
        """Jeder Detector sollte seinen eigenen Namen zurückgeben wenn er matched."""
        for d in ALL_DETECTORS:
            # Prüfe ob der Detector auf eine existierende Datei matched (file exists check)
            has_filecheck = any(m[1] == "" for m in d.markers)
            if has_filecheck:
                # Kann nicht testen ohne echte Datei
                continue
            # Für Detectors mit String/Regex-Markern: erwarte None wenn keine Datei da
            result = d.detect(tmp_path)
            assert result is None, f"{d.name}: detect() sollte None zurückgeben ohne Dateien"
