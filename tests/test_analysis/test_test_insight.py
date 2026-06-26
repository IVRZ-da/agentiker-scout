"""Tests für analysis_test_insight_tool — 100% Coverage."""
from __future__ import annotations

import json
from unittest.mock import patch

from scout.analysis.tools.test_insight import analysis_test_insight_tool


def _parse(raw: str) -> dict:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"status": "error", "raw": raw}


class TestAnalysisTestInsight:
    """Tests covering all code paths in analysis_test_insight_tool."""

    # ------------------------------------------------------------------ #
    #  Basic tests (real tool calls, no mocking)
    # ------------------------------------------------------------------ #

    def test_requires_path(self):
        """Empty/missing path → error."""
        result = analysis_test_insight_tool({})
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_output_structure(self):
        """Valid path returns ok with expected keys."""
        result = analysis_test_insight_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        assert "path" in parsed
        assert "symbol" in parsed
        assert "tests_found" in parsed
        assert "generated_scaffolds" in parsed
        assert "summary" in parsed

    def test_output_size(self):
        """Output stays under 3000 chars."""
        result = analysis_test_insight_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        assert len(result) < 3000, f"Output too long: {len(result)}"

    def test_invalid_path_traversal(self):
        """Path traversal attempt → error."""
        result = analysis_test_insight_tool({
            "path": "../../etc/passwd",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    # ------------------------------------------------------------------ #
    #  Mock-based tests — cover previously uncovered paths
    # ------------------------------------------------------------------ #

    @patch("scout.analysis.tools.test_insight._call_tool")
    @patch("scout.analysis.tools.test_insight._validate_and_resolve_path")
    def test_symbol_matched_in_code_symbols(
        self, mock_validate, mock_call_tool
    ):
        """Symbol found in code_symbols → line set correctly (lines 42-44)."""
        mock_validate.return_value = (None, "/resolved/path")
        mock_call_tool.side_effect = [
            # _call_tool("code_symbols", ...) — multiple symbols, one matches
            {
                "symbols": [
                    {"name": "other_func", "line": 10},
                    {"name": "my_func", "line": 42},
                ]
            },
            # _call_tool("code_tests_for_symbol", ...)
            {"test_files": [{"file": "test_foo.py", "type": "test"}]},
        ]

        result = analysis_test_insight_tool({
            "path": "/some/path",
            "symbol": "my_func",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        assert mock_call_tool.call_count >= 2
        # Second call (code_tests_for_symbol) was passed line=42
        assert mock_call_tool.call_args_list[1][1].get("line") == 42

    @patch("scout.analysis.tools.test_insight._call_tool")
    @patch("scout.analysis.tools.test_insight._validate_and_resolve_path")
    def test_code_tests_for_symbol_exception(
        self, mock_validate, mock_call_tool
    ):
        """Exception from code_tests_for_symbol caught (lines 56-57)."""
        mock_validate.return_value = (None, "/resolved/path")
        mock_call_tool.side_effect = [
            # _call_tool("code_symbols", ...)
            {"symbols": [{"name": "my_func", "line": 42}]},
            # _call_tool("code_tests_for_symbol", ...) raises
            Exception("tests-failed"),
        ]

        result = analysis_test_insight_tool({
            "path": "/some/path",
            "symbol": "my_func",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        assert parsed.get("tests_found") == []

    @patch("scout.analysis.tools.test_insight._call_tool")
    @patch("scout.analysis.tools.test_insight._validate_and_resolve_path")
    def test_generate_true_success(
        self, mock_validate, mock_call_tool
    ):
        """generate=True with successful scaffold (lines 60-63, 73)."""
        mock_validate.return_value = (None, "/resolved/path")
        mock_call_tool.side_effect = [
            # _call_tool("code_symbols", ...)
            {"symbols": [{"name": "my_func", "line": 42}]},
            # _call_tool("code_tests_for_symbol", ...)
            {"test_files": [{"file": "test_foo.py", "type": "test"}]},
            # _call_tool("code_generate_tests", ...) — success
            "def test_my_func(): pass",
        ]

        result = analysis_test_insight_tool({
            "path": "/some/path",
            "symbol": "my_func",
            "generate": True,
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        # generated_scaffolds should be populated → covers line 73
        assert len(parsed.get("generated_scaffolds", [])) == 1

    @patch("scout.analysis.tools.test_insight._call_tool")
    @patch("scout.analysis.tools.test_insight._validate_and_resolve_path")
    def test_generate_true_exception(
        self, mock_validate, mock_call_tool
    ):
        """generate=True with exception caught (lines 64-65)."""
        mock_validate.return_value = (None, "/resolved/path")
        mock_call_tool.side_effect = [
            # _call_tool("code_symbols", ...)
            {"symbols": [{"name": "my_func", "line": 42}]},
            # _call_tool("code_tests_for_symbol", ...)
            {"test_files": [{"file": "test_foo.py", "type": "test"}]},
            # _call_tool("code_generate_tests", ...) raises
            Exception("generate-failed"),
        ]

        result = analysis_test_insight_tool({
            "path": "/some/path",
            "symbol": "my_func",
            "generate": True,
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        # generated_scaffolds stays empty
        assert parsed.get("generated_scaffolds") == []
