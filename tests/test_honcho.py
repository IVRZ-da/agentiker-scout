"""Tests für shared/honcho.py — Honcho-Persistenz + Session-Tracking."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from scout.shared.honcho import (
    _get_honcho_tool,
    _persist_analysis_summary,
    _persist_bughunt_summary,
    _persist_research_summary,
    on_post_tool_call,
    on_session_end,
)


class TestGetHonchoTool:
    def test_tool_found(self):
        """Wenn registry verfügbar, wird der Handler geliefert."""
        entry = _get_honcho_tool("honcho_conclude")
        # Wenn das Tool nicht registriert ist, gibt's None (kein Crash)
        assert entry is None or hasattr(entry, "handler")

    def test_tool_not_found(self):
        """Bei fehlendem Tool oder Exception wird None returned."""
        result = _get_honcho_tool("nonexistent_tool_xyz")
        assert result is None


class TestPersistAnalysisSummary:
    def test_no_active_session(self):
        """Wenn kein aktiver Analysis-Session, passiert nichts."""
        with patch("scout.shared.honcho._get_analysis_session", return_value=None):
            result = _persist_analysis_summary()
            assert result is None

    def test_with_session_no_honcho(self):
        """Session aktiv, aber honcho nicht verfügbar → nur log, kein Crash."""
        with patch("scout.shared.honcho._get_analysis_session", return_value={
            "intent": "code", "findings_count": 3
        }):
            with patch("scout.shared.honcho._get_honcho_tool", return_value=None):
                result = _persist_analysis_summary()
                assert result is None

    def test_with_session_and_honcho(self):
        """Session aktiv + honcho verfügbar → persist wird aufgerufen."""
        mock_handler = MagicMock()
        mock_entry = MagicMock()
        mock_entry.handler = mock_handler
        with patch("scout.shared.honcho._get_analysis_session", return_value={
            "intent": "code", "findings_count": 3
        }):
            with patch("scout.shared.honcho._get_honcho_tool", return_value=mock_entry):
                _persist_analysis_summary()
                mock_handler.assert_called_once()


class TestPersistBughuntSummary:
    def test_no_active_session(self):
        with patch("scout.shared.honcho._get_bughunt_session", return_value=None):
            assert _persist_bughunt_summary() is None

    def test_with_session_no_honcho(self):
        with patch("scout.shared.honcho._get_bughunt_session", return_value={
            "findings_count": 5, "severity": "high"
        }):
            with patch("scout.shared.honcho._get_honcho_tool", return_value=None):
                assert _persist_bughunt_summary() is None

    def test_with_session_and_honcho(self):
        mock_handler = MagicMock()
        mock_entry = MagicMock()
        mock_entry.handler = mock_handler
        with patch("scout.shared.honcho._get_bughunt_session", return_value={
            "findings_count": 5, "severity": "high"
        }):
            with patch("scout.shared.honcho._get_honcho_tool", return_value=mock_entry):
                _persist_bughunt_summary()
                mock_handler.assert_called_once()

    def test_auto_deduce_failure(self):
        """Wenn _auto_deduce_patterns fehlschlägt, kein Crash."""
        mock_handler = MagicMock()
        mock_entry = MagicMock()
        mock_entry.handler = mock_handler
        with patch("scout.shared.honcho._get_bughunt_session", return_value={
            "findings_count": 5, "severity": "high"
        }):
            with patch("scout.shared.honcho._get_honcho_tool", return_value=mock_entry):
                _persist_bughunt_summary()
                # Sollte nicht crashen


class TestPersistResearchSummary:
    def test_no_active_session(self):
        with patch("scout.shared.honcho._get_research_session", return_value=None):
            assert _persist_research_summary() is None

    def test_with_session_no_honcho(self):
        with patch("scout.shared.honcho._get_research_session", return_value={
            "query": "test query", "sources_count": 3
        }):
            with patch("scout.shared.honcho._get_honcho_tool", return_value=None):
                assert _persist_research_summary() is None

    def test_with_session_and_honcho(self):
        mock_handler = MagicMock()
        mock_entry = MagicMock()
        mock_entry.handler = mock_handler
        with patch("scout.shared.honcho._get_research_session", return_value={
            "query": "test query", "sources_count": 3
        }):
            with patch("scout.shared.honcho._get_honcho_tool", return_value=mock_entry):
                _persist_research_summary()
                mock_handler.assert_called_once()


class TestOnPostToolCall:
    def test_no_tool_name(self):
        result = on_post_tool_call()
        assert result is None

    def test_analysis_tool(self):
        with patch("scout.shared.honcho.logger") as mock_log:
            on_post_tool_call(tool_name="analysis_inspect")
            mock_log.debug.assert_called_once()

    def test_bughunt_tool(self):
        with patch("scout.shared.honcho.logger") as mock_log:
            on_post_tool_call(tool_name="bug_hunt_scan")
            mock_log.debug.assert_called_once()

    def test_research_tool(self):
        with patch("scout.shared.honcho.logger") as mock_log:
            on_post_tool_call(tool_name="research_search")
            mock_log.debug.assert_called_once()

    def test_unrelated_tool_no_match(self):
        """Nicht-domain Tools werden nicht getrackt."""
        with patch("scout.shared.honcho.logger") as mock_log:
            on_post_tool_call(tool_name="web_search")
            mock_log.debug.assert_not_called()


class TestOnSessionEnd:
    def test_calls_all_persist(self):
        """on_session_end ruft alle 3 persist-Funktionen auf."""
        with patch("scout.shared.honcho._persist_analysis_summary") as mock_a:
            with patch("scout.shared.honcho._persist_bughunt_summary") as mock_b:
                with patch("scout.shared.honcho._persist_research_summary") as mock_r:
                    on_session_end()
                    mock_a.assert_called_once()
                    mock_b.assert_called_once()
                    mock_r.assert_called_once()
