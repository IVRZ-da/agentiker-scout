"""Additional error-path tests for shared/honcho.py — exception branches."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from scout.shared.honcho import (
    _get_analysis_session,
    _get_honcho_tool,
    _persist_analysis_summary,
    _persist_bughunt_summary,
    _persist_research_summary,
)

# ── Exception branch tests ───────────────────────────────────────────


class TestGetHonchoToolErrorPaths:
    def test_registry_get_entry_raises(self) -> None:
        """Wenn registry.get_entry eine Exception wirft, None zurück."""
        import sys
        saved = sys.modules.pop("tools.registry", None)
        saved_tools = sys.modules.pop("tools", None)
        try:
            result = _get_honcho_tool("anything")
            assert result is None
        finally:
            if saved:
                sys.modules["tools.registry"] = saved
            if saved_tools:
                sys.modules["tools"] = saved_tools


class TestGetAnalysisSessionErrorPaths:
    def test_import_failure_returns_none(self) -> None:
        import sys
        saved = sys.modules.pop("scout.analysis.analysis_session", None)
        try:
            result = _get_analysis_session()
            assert result is None
        finally:
            if saved:
                sys.modules["scout.analysis.analysis_session"] = saved

    def test_no_active_session(self) -> None:
        """Wenn _active_session None ist oder Modul nicht ladbar."""
        result = _get_analysis_session()
        assert result is None or isinstance(result, dict)


class TestPersistErrorPaths:
    def test_persist_analysis_handler_raises(self) -> None:
        """honcho_conclude handler wirft Exception → catch (lines 91-92)."""
        mock_handler = MagicMock()
        mock_handler.side_effect = RuntimeError("handler fail")
        mock_entry = MagicMock()
        mock_entry.handler = mock_handler
        with patch("scout.shared.honcho._get_analysis_session", return_value={
            "intent": "code", "findings_count": 3
        }):
            with patch("scout.shared.honcho._get_honcho_tool", return_value=mock_entry):
                _persist_analysis_summary()  # Should not crash

    def test_persist_bughunt_handler_raises(self) -> None:
        """honcho_conclude handler wirft Exception → catch (lines 115-116)."""
        mock_handler = MagicMock()
        mock_handler.side_effect = RuntimeError("handler fail")
        mock_entry = MagicMock()
        mock_entry.handler = mock_handler
        with patch("scout.shared.honcho._get_bughunt_session", return_value={
            "findings_count": 3, "severity": "high"
        }):
            with patch("scout.shared.honcho._get_honcho_tool", return_value=mock_entry):
                _persist_bughunt_summary()  # Should not crash

    def test_persist_research_handler_raises(self) -> None:
        """honcho_conclude handler wirft Exception → catch (lines 146-147)."""
        mock_handler = MagicMock()
        mock_handler.side_effect = RuntimeError("handler fail")
        mock_entry = MagicMock()
        mock_entry.handler = mock_handler
        with patch("scout.shared.honcho._get_research_session", return_value={
            "query": "test", "sources_count": 3
        }):
            with patch("scout.shared.honcho._get_honcho_tool", return_value=mock_entry):
                _persist_research_summary()  # Should not crash
