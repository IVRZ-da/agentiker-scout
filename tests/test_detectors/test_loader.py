"""Tests für shared/detectors/loader.py + public.py — FrameworkDetector + Public API."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from scout.shared.detectors.loader import FrameworkDetector
from scout.shared.detectors.public import detect_frameworks, format_profile_summary


class TestFrameworkDetectorInit:
    def test_invalid_root(self):
        with pytest.raises(ValueError, match="nicht gefunden"):
            FrameworkDetector("/nonexistent/path/12345")

    def test_valid_root(self, tmp_path: Path):
        detector = FrameworkDetector(str(tmp_path))
        assert detector.project_root == tmp_path.resolve()

    def test_with_custom_detectors(self, tmp_path: Path):
        from scout.shared.detectors.base import _TechDetector
        CustomDet = type("_C", (_TechDetector,), {
            "name": "custom", "category": "testing",
            "markers": [("flag.txt", "CUSTOM_MARKER", "high")],
        })
        # Instanz erzeugen für custom_detectors
        custom_instance = CustomDet()
        detector = FrameworkDetector(str(tmp_path), custom_detectors=[custom_instance])
        # Should not crash
        profile = detector.detect()
        assert profile.has_framework("custom") is False  # flag.txt doesn't exist

    def test_disable_yaml_rules(self, tmp_path: Path):
        detector = FrameworkDetector(str(tmp_path), use_yaml_rules=False)
        profile = detector.detect()
        assert profile is not None

    def test_yaml_rules_warns_if_missing(self, tmp_path: Path, caplog):
        with patch("scout.shared.detectors.loader.logger") as mock_log:
            FrameworkDetector(str(tmp_path), yaml_rules_dir="/nonexistent/rules")
            # Should warn and continue with Python detectors
            mock_log.warning.assert_called_once()


class TestFrameworkDetectorDetect:
    def test_detect_empty_project(self, tmp_path: Path):
        detector = FrameworkDetector(str(tmp_path), use_yaml_rules=False)
        profile = detector.detect()
        assert profile.project_root == str(tmp_path.resolve())
        assert isinstance(profile.frameworks, dict)

    def test_detect_with_python_marker(self, tmp_path: Path):
        (tmp_path / "main.py").write_text("from flask import Flask\napp = Flask(__name__)\n")
        detector = FrameworkDetector(str(tmp_path), use_yaml_rules=False)
        profile = detector.detect()
        # Should find python language
        assert profile.has_framework("python") or profile.get_frameworks_by_category("language")

    def test_detect_with_category_filter(self, tmp_path: Path):
        (tmp_path / "main.py").write_text("print('hello')\n")
        (tmp_path / "Dockerfile").write_text("FROM python:3.12\n")
        detector = FrameworkDetector(str(tmp_path), use_yaml_rules=False)
        profile = detector.detect(categories=["infra"])
        # Nur infra-Detectors sollten laufen
        for cat, fws in profile.frameworks.items():
            assert cat in ["infra"], f"Unerwartete Kategorie: {cat}"

    def test_detect_with_generic_deps(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"react": "^19.0.0"}}))
        detector = FrameworkDetector(str(tmp_path), use_yaml_rules=False)
        profile = detector.detect()
        assert profile.has_framework("react")

    def test_detect_dotenv(self, tmp_path: Path):
        (tmp_path / ".env.example").write_text("REDIS_URL=redis://localhost\nPOSTGRES_HOST=db\n")
        detector = FrameworkDetector(str(tmp_path), use_yaml_rules=False)
        profile = detector.detect()
        # Sollte redis und postgres erkennen via dotenv prefixes
        assert profile.has_framework("redis") or profile.has_framework("postgresql")

    def test_detect_docker(self, tmp_path: Path):
        (tmp_path / "docker-compose.yml").write_text("services:\n  db:\n    image: postgres:16\n")
        detector = FrameworkDetector(str(tmp_path), use_yaml_rules=False)
        profile = detector.detect()
        # Sollte docker + postgres erkennen
        assert profile.get_frameworks_by_category("infra") or profile.get_frameworks_by_category("database")

    def test_detect_fast_mode(self, tmp_path: Path):
        (tmp_path / "main.py").write_text("print('test')\n")
        detector = FrameworkDetector(str(tmp_path), use_yaml_rules=False)
        profile = detector.detect_fast()
        assert profile is not None

    def test_detect_twice_returns_fresh_profile(self, tmp_path: Path):
        detector = FrameworkDetector(str(tmp_path), use_yaml_rules=False)
        p1 = detector.detect()
        p2 = detector.detect()
        # Beide sollten unabhängige Profile sein
        assert p1 is not p2
        assert p1.project_root == p2.project_root


class TestDetectFrameworksPublic:
    def test_public_api(self, tmp_path: Path):
        result = detect_frameworks(str(tmp_path))
        assert isinstance(result, dict)
        assert "project_root" in result
        assert "frameworks" in result

    def test_public_api_fast(self, tmp_path: Path):
        result = detect_frameworks(str(tmp_path), fast=True)
        assert isinstance(result, dict)

    def test_public_api_with_categories(self, tmp_path: Path):
        result = detect_frameworks(str(tmp_path), categories=["language"])
        assert isinstance(result, dict)


class TestFormatProfileSummary:
    def test_empty_profile(self):
        text = format_profile_summary({})
        assert "Keine Frameworks" in text

    def test_empty_frameworks(self):
        text = format_profile_summary({"project_root": "/tmp", "frameworks": {}})
        assert "Keine Frameworks" in text

    def test_with_frameworks(self):
        profile = {
            "project_root": "/app",
            "overall_confidence": 0.85,
            "frameworks": {
                "frontend": [
                    {"name": "react", "confidence": "high", "version": "19.0", "evidence": [
                        {"source": "package.json", "confidence": "high"}
                    ]}
                ]
            }
        }
        text = format_profile_summary(profile)
        assert "react" in text
        assert "frontend" in text
        assert "19.0" in text
        assert "package.json" in text

    def test_without_version(self):
        profile = {
            "project_root": "/x",
            "overall_confidence": 0.5,
            "frameworks": {
                "backend": [{"name": "flask", "confidence": "medium", "version": None, "evidence": []}]
            }
        }
        text = format_profile_summary(profile)
        assert "flask" in text
        # Kein v ohne version
