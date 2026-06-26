"""Error-path tests for analysis/tools/base.py — Path validation, tool dispatch, utilities."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from scout.analysis.tools.base import (
    _build_summary_line,
    _call_tool,
    _call_tool_direct,
    _clear_symbol_line_cache,
    _find_symbol_line,
    _parallel_dispatch,
    _summarize_diagnostics,
    _summarize_symbols,
    _validate_and_resolve_path,
    _validate_path,
)

# ── _validate_path ───────────────────────────────────────────────────


class TestValidatePath:
    def test_empty_returns_error(self) -> None:
        assert _validate_path("") is not None
        assert _validate_path(None) is not None  # type: ignore[arg-type]
        assert _validate_path(42) is not None  # type: ignore[arg-type]

    def test_too_long_returns_error(self) -> None:
        assert _validate_path("x" * 5000) is not None

    def test_control_chars_returns_error(self) -> None:
        assert _validate_path("test\x00file") is not None
        assert _validate_path("bad\x1fpath") is not None

    def test_traversal_patterns_returns_error(self) -> None:
        assert _validate_path("../escape") is not None
        assert _validate_path("a/../../b") is not None

    def test_encoded_traversal_returns_error(self) -> None:
        assert _validate_path("%2e%2e/test") is not None
        assert _validate_path("%252e%252e/test") is not None

    def test_valid_relative_path_returns_none(self) -> None:
        result = _validate_path("/tmp/valid-path")
        assert result is None

    def test_valid_path_without_issues(self) -> None:
        result = _validate_path("/home/user/project/file.py")
        assert result is None

    def test_resolution_error_is_caught(self, tmp_path) -> None:
        with patch(
            "scout.analysis.tools.base.os.path.realpath",
            side_effect=OSError("mock"),
        ):
            error = _validate_path("/some/path")
            assert error is not None
            assert "resolution error" in error

    def test_resolved_non_absolute_returns_error(self) -> None:
        with patch(
            "scout.analysis.tools.base.os.path.realpath", return_value="relative"
        ):
            error = _validate_path("/some/path")
            assert error is not None
            assert "non-absolute" in error

    def test_symlink_divergence_is_logged(self, tmp_path) -> None:
        """When realpath diverges from normpath (symlink), no error, just log."""
        with patch(
            "scout.analysis.tools.base.os.path.realpath",
            return_value="/real/different/path",
        ):
            with patch(
                "scout.analysis.tools.base.os.path.normpath",
                return_value="/apparent/path",
            ):
                with patch("scout.analysis.tools.base.logger") as mock_log:
                    result = _validate_path("/apparent/path")
                    assert result is None  # valid, just logged
                    mock_log.debug.assert_called()


# ── _validate_and_resolve_path ───────────────────────────────────────


class TestValidateAndResolvePath:
    def test_invalid_path_returns_error(self) -> None:
        error, resolved = _validate_and_resolve_path("")
        assert error is not None

    def test_relative_path_gets_resolved(self) -> None:
        error, resolved = _validate_and_resolve_path("/tmp")
        assert error is None
        assert resolved == "/tmp"

    def test_relative_gets_cwd_prepended(self) -> None:
        with patch("scout.analysis.tools.base.os.getcwd", return_value="/base"):
            error, resolved = _validate_and_resolve_path("relative/path")
            assert error is None
            assert resolved.endswith("relative/path")


# ── _call_tool ───────────────────────────────────────────────────────


class TestCallTool:
    def test_returns_error_on_timeout(self) -> None:
        """Timeout wird abgefangen und als Error-Dict zurückgegeben."""
        with patch(
            "scout.analysis.tools.base._timeout_executor"
        ) as mock_executor:
            future = MagicMock()
            from concurrent.futures import TimeoutError as FuturesTimeout

            future.result.side_effect = FuturesTimeout()
            mock_executor.submit.return_value = future

            result = _call_tool("test_tool", timeout=1)
            assert isinstance(result, dict)
            assert "timeout" in result.get("error", "")

    def test_general_exception_returns_error(self) -> None:
        with patch(
            "scout.analysis.tools.base._timeout_executor"
        ) as mock_executor:
            future = MagicMock()
            future.result.side_effect = RuntimeError("boom")
            mock_executor.submit.return_value = future

            result = _call_tool("test_tool")
            assert isinstance(result, dict)
            assert "error" in result

    def test_json_result_is_parsed(self) -> None:
        with patch(
            "scout.analysis.tools.base._timeout_executor"
        ) as mock_executor:
            future = MagicMock()
            future.result.return_value = '{"key": "value"}'
            mock_executor.submit.return_value = future

            result = _call_tool("test_tool")
            assert result == {"key": "value"}

    def test_string_result_not_json_returns_raw(self) -> None:
        with patch(
            "scout.analysis.tools.base._timeout_executor"
        ) as mock_executor:
            future = MagicMock()
            future.result.return_value = "plain string"
            mock_executor.submit.return_value = future

            result = _call_tool("test_tool")
            assert result == "plain string"


# ── _call_tool_direct ────────────────────────────────────────────────


class TestCallToolDirect:
    def test_returns_error_on_exception(self) -> None:
        with patch(
            "tools.registry.registry.dispatch",
            side_effect=RuntimeError("direct boom"),
        ):
            result = _call_tool_direct("test_tool")
            assert isinstance(result, dict)
            assert "error" in result

    def test_returns_result(self) -> None:
        # Conftest already mocks registry; test the call works
        result = _call_tool_direct("test_tool")
        assert result is not None or isinstance(result, (dict, str))

    def test_json_result_parsed(self) -> None:
        with patch(
            "tools.registry.registry.dispatch",
            return_value='{"parsed": true}',
        ):
            result = _call_tool_direct("test_tool")
            assert isinstance(result, dict)
            assert result.get("parsed") is True

    def test_string_result_not_json_returns_raw(self) -> None:
        with patch(
            "tools.registry.registry.dispatch",
            return_value="plain string",
        ):
            result = _call_tool_direct("test_tool")
            assert result == "plain string"


# ── _parallel_dispatch ───────────────────────────────────────────────


class TestParallelDispatch:
    def test_returns_results(self) -> None:
        calls = [{"key": "k1", "name": "tool1", "kwargs": {"a": 1}}]
        with patch(
            "tools.registry.registry.dispatch",
            return_value={"result": "ok"},
        ):
            results = _parallel_dispatch(calls)
            assert results.get("k1") == {"result": "ok"}

    def test_timeout_returns_error_key(self) -> None:
        calls = [{"key": "k1", "name": "tool1", "kwargs": {}}]

        with patch(
            "scout.analysis.tools.base._parallel_executor"
        ) as mock_exec:
            future = MagicMock()
            from concurrent.futures import TimeoutError as FuturesTimeout

            future.result.side_effect = FuturesTimeout()
            mock_exec.submit.return_value = future

            results = _parallel_dispatch(calls, timeout=1)
            assert "k1_error" in results

    def test_exception_returns_error_key(self) -> None:
        calls = [{"key": "k1", "name": "tool1", "kwargs": {}}]

        with patch(
            "scout.analysis.tools.base._parallel_executor"
        ) as mock_exec:
            future = MagicMock()
            future.result.side_effect = RuntimeError("parallel boom")
            mock_exec.submit.return_value = future

            results = _parallel_dispatch(calls)
            assert "k1_error" in results

    def test_json_result_parsed(self) -> None:
        calls = [{"key": "k1", "name": "tool1", "kwargs": {}}]
        with patch(
            "tools.registry.registry.dispatch",
            return_value='{"parsed": true}',
        ):
            results = _parallel_dispatch(calls)
            assert results.get("k1") == {"parsed": True}

    def test_registry_import_fail_returns_empty(self) -> None:
        """Wenn tools.registry nicht importiert werden kann, leeres Dict."""
        import sys
        saved = sys.modules.pop("tools.registry", None)
        saved_tools = sys.modules.pop("tools", None)
        try:
            result = _parallel_dispatch(
                [{"key": "k", "name": "t", "kwargs": {}}]
            )
            assert result == {}
        finally:
            if saved:
                sys.modules["tools.registry"] = saved
            if saved_tools:
                sys.modules["tools"] = saved_tools


# ── _clear_symbol_line_cache / _find_symbol_line ─────────────────────


class TestSymbolLineCache:
    def test_clear_cache(self) -> None:
        _clear_symbol_line_cache()
        # Just ensure no crash
        assert True

    def test_find_symbol_line_cache_hit(self) -> None:
        from scout.analysis.tools.base import _symbol_line_cache

        _symbol_line_cache.clear()
        _symbol_line_cache["/f.py:MyClassCache"] = 42
        result = _find_symbol_line("/f.py", "MyClassCache")
        assert result == 42

    def test_find_symbol_line_list_result(self) -> None:
        from scout.analysis.tools.base import _symbol_line_cache
        _symbol_line_cache.clear()
        with patch(
            "scout.analysis.tools.base._call_tool",
            return_value=[{"name": "MyClass2", "line": 10}],
        ):
            result = _find_symbol_line("/f2.py", "MyClass2")
            assert result == 10

    def test_find_symbol_line_dict_result(self) -> None:
        from scout.analysis.tools.base import _symbol_line_cache
        _symbol_line_cache.clear()
        with patch(
            "scout.analysis.tools.base._call_tool",
            return_value={"symbols": [{"name": "MyClass3", "line": 15}]},
        ):
            result = _find_symbol_line("/f3.py", "MyClass3")
            assert result == 15

    def test_find_symbol_line_no_match(self) -> None:
        from scout.analysis.tools.base import _symbol_line_cache
        _symbol_line_cache.clear()
        with patch(
            "scout.analysis.tools.base._call_tool",
            return_value=[{"name": "Other", "line": 99}],
        ):
            result = _find_symbol_line("/f4.py", "MyClass4")
            assert result == 1  # default

    def test_find_symbol_line_exception(self) -> None:
        from scout.analysis.tools.base import _symbol_line_cache
        _symbol_line_cache.clear()
        with patch(
            "scout.analysis.tools.base._call_tool",
            side_effect=RuntimeError("fail"),
        ):
            result = _find_symbol_line("/f5.py", "MyClass5")
            assert result == 1  # default on error


# ── _summarize_symbols ───────────────────────────────────────────────


class TestSummarizeSymbols:
    def test_list_input(self) -> None:
        symbols = [{"name": "f1", "kind": "function", "line": 1}]
        result = _summarize_symbols(symbols)
        assert len(result) == 1
        assert result[0]["name"] == "f1"

    def test_dict_input(self) -> None:
        symbols = {"symbols": [{"name": "f1", "kind": "function", "line": 1}]}
        result = _summarize_symbols(symbols)
        assert len(result) == 1

    def test_neither_returns_empty_list(self) -> None:
        result = _summarize_symbols("string")
        assert result == []

    def test_empty_list_returns_empty(self) -> None:
        assert _summarize_symbols([]) == []


# ── _summarize_diagnostics ───────────────────────────────────────────


class TestSummarizeDiagnostics:
    def test_dict_with_errors_and_warnings(self) -> None:
        diag = {"errors": 2, "warnings": 3}
        result = _summarize_diagnostics(diag)
        assert result["errors"] == 2
        assert result["warnings"] == 3

    def test_dict_with_diagnostic_count(self) -> None:
        diag = {"errors": 1, "diagnostic_count": 5}
        result = _summarize_diagnostics(diag)
        assert result["total"] == 5

    def test_non_dict_returns_zero_total(self) -> None:
        result = _summarize_diagnostics("bad")
        assert result == {"total": 0}


# ── _build_summary_line ──────────────────────────────────────────────


class TestBuildSummaryLine:
    def test_basic_summary(self) -> None:
        result = _build_summary_line(
            {"summary": {"tools_called": 3}},
            {"path": "/test", "depth": 2},
        )
        assert "path=/test" in result
        assert "depth=2" in result

    def test_with_symbol_and_findings(self) -> None:
        result = _build_summary_line(
            {},
            {"path": "/p", "symbol": "func", "tools_called": 5, "finding_count": 2},
        )
        assert "symbol=func" in result
        assert "tools=5" in result
        assert "findings=2" in result

    def test_no_metadata_keys(self) -> None:
        result = _build_summary_line({}, {})
        assert result == ""
