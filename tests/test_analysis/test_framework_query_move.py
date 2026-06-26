"""Tests für analysis/tools/framework_query_move.py.

3 Tools:
  - analysis_framework_tool  (Framework-Detection)
  - analysis_code_query_tool (Wrapper für code_query)
  - analysis_code_move_tool  (Wrapper für code_move)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scout.analysis.tools.framework_query_move import (
    analysis_code_move_tool,
    analysis_code_query_tool,
    analysis_framework_tool,
)

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
            patch("shared.framework_detector.FrameworkDetector", return_value=mock_detector) as MockDet,
            patch("shared.framework_detector.format_profile_summary", return_value="Profil: Python 3.12"),
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
            patch("shared.framework_detector.FrameworkDetector", return_value=mock_detector),
            patch("shared.framework_detector.format_profile_summary", return_value="Profil: Node.js"),
        ):
            result = analysis_framework_tool({"path": "/p", "fast": True})
            mock_detector.detect_fast.assert_called_once()
            mock_detector.detect.assert_not_called()
        assert "node" in result.lower()

    def test_value_error_returns_error(self):
        """ValueError → fmt_err."""
        with patch("shared.framework_detector.FrameworkDetector",
                   side_effect=ValueError("invalid path")):
            result = analysis_framework_tool({"path": "/bad"})
        assert "invalid path" in result

    def test_generic_exception_returns_error(self):
        """Beliebige Exception → fmt_err."""
        with patch("shared.framework_detector.FrameworkDetector",
                   side_effect=RuntimeError("unexpected")):
            result = analysis_framework_tool({"path": "/broken"})
        assert "unexpected" in result


# ── analysis_code_query_tool ─────────────────────────────────────────────


class TestAnalysisCodeQueryTool:
    """analysis_code_query_tool — Wrapper für code_query."""

    def test_validation_error_returns_error(self, mock_base):
        """_validate_path gibt Fehler zurück → fmt_err."""
        mock_base["validate"].return_value = "invalid path: /dev/null"
        result = analysis_code_query_tool({
            "path": "/dev/null", "intent": "find_usage",
        })
        assert "invalid path" in result

    def test_resolve_error_returns_error(self, mock_base):
        """_validate_and_resolve_path gibt Fehler zurück → fmt_err."""
        mock_base["resolve"].return_value = ("not found", "")
        result = analysis_code_query_tool({
            "path": "/nonexistent", "intent": "definition",
        })
        assert "not found" in result

    def test_success_returns_fmt_ok(self, mock_base):
        """Erfolg → fmt_ok mit result."""
        mock_base["call_tool"].return_value = {"symbol": "foo"}
        result = analysis_code_query_tool({
            "path": "/project/file.ts", "intent": "definition",
        })
        mock_base["call_tool"].assert_called_once_with(
            "code_query", intent="definition", path="/resolved/path",
            line=0, language="",
        )
        assert "symbol" in result.lower() or "foo" in result

    def test_non_dict_result_passed_through(self, mock_base):
        """Wenn _call_tool kein dict zurückgibt, direkt durchreichen."""
        mock_base["call_tool"].return_value = "raw text result"
        result = analysis_code_query_tool({
            "path": "/p", "intent": "overview",
        })
        assert result == "raw text result"


# ── analysis_code_move_tool ──────────────────────────────────────────────


class TestAnalysisCodeMoveTool:
    """analysis_code_move_tool — Wrapper für code_move."""

    def test_missing_source_returns_error(self):
        """Ohne source → fmt_err."""
        result = analysis_code_move_tool({
            "symbol": "foo", "target": "/t/file.ts",
        })
        assert "required" in result

    def test_missing_symbol_returns_error(self):
        """Ohne symbol → fmt_err."""
        result = analysis_code_move_tool({
            "source": "/s/file.ts", "target": "/t/file.ts",
        })
        assert "required" in result

    def test_missing_target_returns_error(self):
        """Ohne target → fmt_err."""
        result = analysis_code_move_tool({
            "source": "/s/file.ts", "symbol": "foo",
        })
        assert "required" in result

    def test_empty_source_returns_error(self):
        """Leeres source → fmt_err."""
        result = analysis_code_move_tool({
            "source": "", "symbol": "foo", "target": "/t/file.ts",
        })
        assert "required" in result

    def test_invalid_source_path_returns_error(self, mock_base):
        """_validate_path für source gibt Fehler → fmt_err."""
        mock_base["validate"].side_effect = lambda p: (
            f"invalid path: {p}" if p in ("/bad/source",) else None
        )
        result = analysis_code_move_tool({
            "source": "/bad/source", "symbol": "foo", "target": "/t/file.ts",
        })
        assert "invalid path" in result

    def test_invalid_target_path_returns_error(self, mock_base):
        """_validate_path für target gibt Fehler → fmt_err."""
        mock_base["validate"].side_effect = lambda p: (
            f"invalid path: {p}" if p in ("/bad/target",) else None
        )
        result = analysis_code_move_tool({
            "source": "/s/file.ts", "symbol": "foo", "target": "/bad/target",
        })
        assert "invalid path" in result

    def test_successful_move_dry_run(self, mock_base):
        """Erfolgreicher move mit dry_run=True (default)."""
        mock_base["call_tool"].return_value = {"moved": True}
        mock_base["validate"].return_value = None

        result = analysis_code_move_tool({
            "source": "/s/file.ts", "symbol": "foo", "target": "/t/file.ts",
        })
        mock_base["call_tool"].assert_called_once_with(
            "code_move",
            source="/s/file.ts", symbol="foo", target="/t/file.ts",
            dry_run=True,
        )
        assert "moved" in result.lower()

    def test_successful_move_dry_run_false(self, mock_base):
        """Erfolgreicher move mit dry_run=False."""
        mock_base["call_tool"].return_value = {"moved": True}
        mock_base["validate"].return_value = None

        result = analysis_code_move_tool({
            "source": "/s/file.ts", "symbol": "foo",
            "target": "/t/file.ts", "dry_run": False,
        })
        mock_base["call_tool"].assert_called_once_with(
            "code_move",
            source="/s/file.ts", symbol="foo", target="/t/file.ts",
            dry_run=False,
        )
        assert result

    def test_non_dict_result_passed_through(self, mock_base):
        """Wenn _call_tool kein dict zurückgibt, direkt durchreichen."""
        mock_base["call_tool"].return_value = "moved!"
        mock_base["validate"].return_value = None
        result = analysis_code_move_tool({
            "source": "/s/file.ts", "symbol": "foo", "target": "/t/file.ts",
        })
        assert result == "moved!"


# ── Module helpers ────────────────────────────────────────────────────────


def test_import_available():
    """Modul ist importierbar und enthält 3 Tools."""
    from scout.analysis.tools import framework_query_move as fqm
    assert callable(fqm.analysis_framework_tool)
    assert callable(fqm.analysis_code_query_tool)
    assert callable(fqm.analysis_code_move_tool)
