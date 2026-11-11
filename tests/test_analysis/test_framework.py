"""Tests fuer analysis/tools/framework_query_move.py.

Seit 0.6.0 lebt hier nur noch die Framework-Detection. Die beiden
code_intel-Wrapper (analysis_code_query / analysis_code_move) sind ersatzlos
gestrichen — der Aufrufer nutzt direkt code_query / code_move.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scout.analysis.tools.framework_query_move import analysis_framework_tool

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_base():
    """Mock _call_tool, _validate_path, _validate_and_resolve_path im Modul-Namespace."""
    mod_path = "scout.analysis.tools.framework_query_move"
    with (
        patch(f"{mod_path}._call_tool") as call_tool,
        patch(f"{mod_path}._validate_and_resolve_path") as resolve,
        patch(f"{mod_path}._validate_path") as validate,
    ):
        validate.return_value = None  # no error by default
        resolve.return_value = (None, "/resolved/path")
        call_tool.return_value = {"result": "ok"}
        yield {"call_tool": call_tool, "validate": validate, "resolve": resolve}


# ── analysis_framework_tool ──────────────────────────────────────────────


class TestAnalysisFrameworkTool:
    """analysis_framework_tool — Framework-Profil anzeigen."""

    def test_missing_path_returns_error(self):
        """Ohne path → fmt_err."""
        result = analysis_framework_tool({"path": ""})
        assert "ist erforderlich" in result

    def test_no_path_key_returns_error(self):
        """Ohne path-Key → fmt_err."""
        result = analysis_framework_tool({})
        assert "ist erforderlich" in result

    def test_successful_detection(self):
        """Erfolgreiche Framework-Detection mit fmt_ok."""
        mock_profile = MagicMock()
        mock_profile.to_dict.return_value = {"name": "python", "version": "3.12"}
        mock_detector = MagicMock()
        mock_detector.detect.return_value = mock_profile
        mock_detector.detect_fast.return_value = mock_profile

        with (
            patch("scout.shared.framework_detector.FrameworkDetector", return_value=mock_detector) as MockDet,
            patch("scout.shared.framework_detector.format_profile_summary", return_value="Profil: Python 3.12"),
        ):
            result = analysis_framework_tool({"path": "/some/project"})
            MockDet.assert_called_once_with("/some/project")
            mock_detector.detect.assert_called_once()
        assert "python" in result.lower()

    def test_fast_mode(self):
        """fast=True → detect_fast() statt detect()."""
        mock_profile = MagicMock()
        mock_profile.to_dict.return_value = {"name": "node"}
        mock_detector = MagicMock()
        mock_detector.detect_fast.return_value = mock_profile

        with (
            patch("scout.shared.framework_detector.FrameworkDetector", return_value=mock_detector),
            patch("scout.shared.framework_detector.format_profile_summary", return_value="Profil: Node.js"),
        ):
            result = analysis_framework_tool({"path": "/p", "fast": True})
            mock_detector.detect_fast.assert_called_once()
            mock_detector.detect.assert_not_called()
        assert "node" in result.lower()

    def test_value_error_returns_error(self):
        """ValueError → fmt_err."""
        with patch("scout.shared.framework_detector.FrameworkDetector",
                   side_effect=ValueError("invalid path")):
            result = analysis_framework_tool({"path": "/bad"})
        assert "invalid path" in result

    def test_generic_exception_returns_error(self):
        """Beliebige Exception → fmt_err."""
        with patch("scout.shared.framework_detector.FrameworkDetector",
                   side_effect=RuntimeError("unexpected")):
            result = analysis_framework_tool({"path": "/broken"})
        assert "unexpected" in result
