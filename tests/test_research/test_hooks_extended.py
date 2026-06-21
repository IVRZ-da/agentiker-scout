"""
test_hooks_extended.py — Erweiterte Hook-Tests fuer scout.research Plugin.

Deckt die pre_llm_call Hook und interne Helfer ab.
"""

import json
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# pre_llm_call
# ---------------------------------------------------------------------------

class TestPreLlmCall:
    def test_returns_none_without_tracker(self):
        """pre_llm_call gibt None zurueck wenn kein Context da ist."""
        from scout.research.research_hooks import _tool_call_tracker, on_pre_llm_call

        _tool_call_tracker["research_started"] = None
        result = on_pre_llm_call()
        assert result is None

    def test_shows_active_research(self):
        """Zeigt aktive Research-Session im Context."""
        from scout.research.research_hooks import _tool_call_tracker, on_pre_llm_call

        _tool_call_tracker["research_started"] = "abc123"
        _tool_call_tracker["firecrawl_calls"] = [
            {"tool": "mcp_firecrawl_firecrawl_search", "timestamp": "..."}
        ]
        _tool_call_tracker["research_saved"] = False

        result = on_pre_llm_call()
        assert result is not None
        assert "abc123" in result

    def test_shows_saved_research(self):
        """Zeigt gespeicherte Research-Session."""
        from scout.research.research_hooks import _tool_call_tracker, on_pre_llm_call

        _tool_call_tracker["research_started"] = "abc456"
        _tool_call_tracker["firecrawl_calls"] = []
        _tool_call_tracker["research_saved"] = True

        result = on_pre_llm_call()
        assert result is not None
        assert "gespeichert" in result

    def test_no_firecrawl_calls_hint(self):
        """Warnt wenn research gestartet aber keine Firecrawl-Calls."""
        from scout.research.research_hooks import _tool_call_tracker, on_pre_llm_call

        _tool_call_tracker["research_started"] = "abc789"
        _tool_call_tracker["firecrawl_calls"] = []
        _tool_call_tracker["research_saved"] = False

        result = on_pre_llm_call()
        assert result is not None
        assert "Keine" in result or "noch keine" in result.lower()

    def test_graceful_on_import_error(self):
        """pre_llm_call crasht nicht wenn tools.registry nicht verfuegbar."""
        import sys
        saved = sys.modules.pop("tools.registry", None)

        from scout.research.research_hooks import on_pre_llm_call

        result = on_pre_llm_call()
        assert result is None

        if saved:
            sys.modules["tools.registry"] = saved


# ---------------------------------------------------------------------------
# post_tool_call Erweiterungen
# ---------------------------------------------------------------------------

class TestPostToolCallExtended:
    def test_tracks_agent_calls(self):
        """Trackt auch firecrawl_agent calls."""
        from scout.research.research_hooks import _tool_call_tracker, on_post_tool_call

        _tool_call_tracker["research_started"] = "test"
        _tool_call_tracker["firecrawl_calls"] = []

        on_post_tool_call(tool_name="mcp_firecrawl_firecrawl_agent", result="{}")
        assert len(_tool_call_tracker["firecrawl_calls"]) == 1

    def test_tracks_extract_calls(self):
        """Trackt auch firecrawl_extract calls."""
        from scout.research.research_hooks import _tool_call_tracker, on_post_tool_call

        _tool_call_tracker["research_started"] = "test"
        _tool_call_tracker["firecrawl_calls"] = []

        on_post_tool_call(tool_name="mcp_firecrawl_firecrawl_extract", result="{}")
        assert len(_tool_call_tracker["firecrawl_calls"]) == 1

    def test_ignores_empty_tool_name(self):
        """Kein Crash bei leerem tool_name."""
        from scout.research.research_hooks import _tool_call_tracker, on_post_tool_call

        _tool_call_tracker["research_started"] = "test"
        _tool_call_tracker["firecrawl_calls"] = []

        on_post_tool_call(tool_name="", result="")
        assert len(_tool_call_tracker["firecrawl_calls"]) == 0


# ---------------------------------------------------------------------------
# _find_relevant
# ---------------------------------------------------------------------------

class TestFindRelevant:
    def test_empty_input_returns_empty(self):
        from scout.research.research_hooks import _find_relevant

        result = _find_relevant("", [{"query": "test", "summary": "test"}])
        assert result == []

    def test_empty_results_returns_empty(self):
        from scout.research.research_hooks import _find_relevant

        result = _find_relevant("cbd legalisierung", [])
        assert result == []

    def test_finds_relevant_results(self):
        from scout.research.research_hooks import _find_relevant

        results = [
            {"id": "1", "query": "CBD Legalisierung", "summary": "CBD ist in DE legal", "status": "completed", "sources_count": 5},
            {"id": "2", "query": "Steuertipps 2026", "summary": "Steuern sparen", "status": "completed", "sources_count": 3},
        ]
        result = _find_relevant("CBD Legalisierung Deutschland", results, max_results=2)
        assert len(result) >= 1
        assert result[0]["id"] == "1"

    def test_respects_max_results(self):
        from scout.research.research_hooks import _find_relevant

        results = [
            {"id": str(i), "query": "Topic {}".format(i), "summary": "test", "status": "completed", "sources_count": 1}
            for i in range(10)
        ]
        result = _find_relevant("Topic", results, max_results=3)
        assert len(result) <= 3

    def test_returns_all_if_no_stopwords_match(self):
        from scout.research.research_hooks import _find_relevant

        results = [
            {"id": "1", "query": "Awesome", "summary": "Research", "status": "completed", "sources_count": 5},
        ]
        result = _find_relevant("der die das", results, max_results=3)
        assert len(result) <= 1


# ---------------------------------------------------------------------------
# _get_user_input Helfer
# ---------------------------------------------------------------------------

class TestGetUserInput:
    def test_returns_user_message(self):
        from scout.research.research_hooks import _get_user_input

        result = _get_user_input(user_message="hello world")
        assert result == "hello world"

    def test_returns_message(self):
        from scout.research.research_hooks import _get_user_input

        result = _get_user_input(message="test message")
        assert result == "test message"

    def test_returns_input_key(self):
        from scout.research.research_hooks import _get_user_input

        result = _get_user_input(input="input text")
        assert result == "input text"

    def test_returns_empty_if_no_match(self):
        from scout.research.research_hooks import _get_user_input

        result = _get_user_input(some_other_key="value")
        assert result == ""

    def test_returns_empty_for_non_string(self):
        from scout.research.research_hooks import _get_user_input

        result = _get_user_input(user_message=123)
        assert result == ""

    def test_no_kwargs(self):
        from scout.research.research_hooks import _get_user_input

        result = _get_user_input()
        assert result == ""


# ---------------------------------------------------------------------------
# _load_all_results Helfer
# ---------------------------------------------------------------------------

class TestLoadAllResults:
    def test_returns_empty_if_no_dir(self, tmp_path):
        from scout.research import research_hooks as rh
        from scout.research.research_hooks import _load_all_results

        old_dir = rh.RESULTS_DIR
        try:
            rh.RESULTS_DIR = tmp_path / "nonexistent"
            result = _load_all_results()
            assert result == []
        finally:
            rh.RESULTS_DIR = old_dir

    def test_loads_results_from_dir(self, tmp_path):
        from scout.research import research_hooks as rh
        from scout.research.research_hooks import _load_all_results

        old_dir = rh.RESULTS_DIR
        try:
            results_dir = tmp_path / "results"
            results_dir.mkdir(parents=True)
            rh.RESULTS_DIR = results_dir

            (results_dir / "abc.json").write_text(json.dumps({
                "id": "abc123", "query": "Test Query",
                "status": "completed", "summary": "Test summary",
                "findings": [{"finding": "test"}],
                "sources": [{"url": "https://example.com"}],
                "saved_at": "2026-06-18T12:00:00Z",
            }))

            result = _load_all_results()
            assert len(result) == 1
            assert result[0]["id"] == "abc123"
        finally:
            rh.RESULTS_DIR = old_dir


# ---------------------------------------------------------------------------
# on_session_end Edge Cases
# ---------------------------------------------------------------------------

class TestOnSessionEndExtended:
    def test_no_crash_on_missing_plan_file(self, tmp_path):
        """on_session_end crasht nicht wenn Plan-Datei fehlt."""
        from scout.research import research_hooks as rh
        from scout.research.research_hooks import _tool_call_tracker, on_session_end

        _tool_call_tracker["research_started"] = "missing_plan"
        _tool_call_tracker["research_saved"] = False

        old_dir = rh.PLANS_DIR
        rh.PLANS_DIR = tmp_path / "empty_plans"
        rh.PLANS_DIR.mkdir(parents=True)

        on_session_end()

        rh.PLANS_DIR = old_dir

    def test_no_crash_on_corrupt_plan(self, tmp_path):
        """on_session_end crasht nicht bei korrupter Plan-Datei."""
        from scout.research import research_hooks as rh
        from scout.research.research_hooks import _tool_call_tracker, on_session_end

        _tool_call_tracker["research_started"] = "corrupt"
        _tool_call_tracker["research_saved"] = False

        old_plans = rh.PLANS_DIR
        old_results = rh.RESULTS_DIR

        rh.PLANS_DIR = tmp_path / "plans"
        rh.RESULTS_DIR = tmp_path / "results"
        rh.PLANS_DIR.mkdir(parents=True)
        rh.RESULTS_DIR.mkdir(parents=True)

        (rh.PLANS_DIR / "corrupt.json").write_text("{not valid json")

        on_session_end()

        rh.PLANS_DIR = old_plans
        rh.RESULTS_DIR = old_results
