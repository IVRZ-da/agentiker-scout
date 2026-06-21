"""
Tests für die Hooks des scout.research Plugins.

Testet: post_tool_call Tracking, on_session_end Auto-Persist.
"""

import json


# ---------------------------------------------------------------------------
# post_tool_call Tracking
# ---------------------------------------------------------------------------

class TestPostToolCall:
    def test_tracks_firecrawl_calls(self):
        """post_tool_call trackt firecrawl_* Aufrufe."""
        from scout.research.research_hooks import on_post_tool_call, _tool_call_tracker

        # Tracker initialisieren
        _tool_call_tracker["research_started"] = "test123"
        _tool_call_tracker["firecrawl_calls"] = []
        _tool_call_tracker["research_saved"] = False

        # Firecrawl-Call simulieren
        on_post_tool_call(tool_name="mcp_firecrawl_firecrawl_search", result="...")
        assert len(_tool_call_tracker["firecrawl_calls"]) == 1
        assert _tool_call_tracker["firecrawl_calls"][0]["tool"] == "mcp_firecrawl_firecrawl_search"

        # Zweiter Call
        on_post_tool_call(tool_name="mcp_firecrawl_firecrawl_scrape", result="...")
        assert len(_tool_call_tracker["firecrawl_calls"]) == 2

    def test_ignores_non_firecrawl(self):
        """Nicht-Firecrawl-Tools werden ignoriert."""
        from scout.research.research_hooks import on_post_tool_call, _tool_call_tracker

        _tool_call_tracker["research_started"] = "test456"
        _tool_call_tracker["firecrawl_calls"] = []

        on_post_tool_call(tool_name="code_search", result="...")
        assert len(_tool_call_tracker["firecrawl_calls"]) == 0

    def test_detects_research_save(self):
        """post_tool_call erkennt research_save."""
        from scout.research.research_hooks import on_post_tool_call, _tool_call_tracker

        _tool_call_tracker["research_started"] = "test789"
        _tool_call_tracker["research_saved"] = False

        on_post_tool_call(tool_name="research_save", result="...")
        assert _tool_call_tracker["research_saved"] is True

    def test_no_tracking_without_start(self):
        """Kein Tracking wenn research_started None ist."""
        from scout.research.research_hooks import on_post_tool_call, _tool_call_tracker

        _tool_call_tracker["research_started"] = None
        _tool_call_tracker["firecrawl_calls"] = []

        on_post_tool_call(tool_name="mcp_firecrawl_firecrawl_search", result="...")
        assert len(_tool_call_tracker["firecrawl_calls"]) == 0


# ---------------------------------------------------------------------------
# reset_tracker
# ---------------------------------------------------------------------------

class TestResetTracker:
    def test_reset_sets_research_id(self):
        """reset_tracker setzt research_started."""
        from scout.research.research_hooks import reset_tracker, _tool_call_tracker

        reset_tracker("abc123")
        assert _tool_call_tracker["research_started"] == "abc123"
        assert _tool_call_tracker["firecrawl_calls"] == []
        assert _tool_call_tracker["research_saved"] is False


# ---------------------------------------------------------------------------
# on_session_end
# ---------------------------------------------------------------------------

class TestOnSessionEnd:
    def test_auto_save_partial(self, tmp_path):
        """
        on_session_end erzeugt auto-save wenn research_save vergessen wurde.
        """
        from scout.research.research_hooks import on_session_end, _tool_call_tracker

        # Simuliere: research_start aufgerufen aber kein save
        _tool_call_tracker["research_started"] = "auto_save_test"
        _tool_call_tracker["research_saved"] = False

        # Plan-Datei anlegen (wird von research_start normalerweise erzeugt)
        plans_dir = tmp_path / "data" / "plans"
        results_dir = tmp_path / "data" / "results"
        plans_dir.mkdir(parents=True, exist_ok=True)
        results_dir.mkdir(parents=True, exist_ok=True)

        plan = {
            "id": "auto_save_test",
            "query": "Auto Save Query",
            "depth": 2,
            "max_sources": 5,
            "status": "planned",
            "created_at": "2026-06-18T12:00:00+00:00",
        }
        (plans_dir / "auto_save_test.json").write_text(json.dumps(plan))

        # Patch paths
        from scout.research import research_hooks as rh
        rh.PLANS_DIR = plans_dir
        rh.RESULTS_DIR = results_dir

        # on_session_end auslösen
        on_session_end()

        # Prüfe dass Partial-Ergebnis existiert
        result_path = results_dir / "auto_save_test.json"
        assert result_path.exists()
        saved = json.loads(result_path.read_text())
        assert saved["status"] == "partial"
        assert saved["_auto_saved"] is True

        # Plan sollte gelöscht sein
        assert not (plans_dir / "auto_save_test.json").exists()

    def test_no_save_if_already_saved(self, tmp_path):
        """Kein auto-save wenn research_save bereits aufgerufen wurde."""
        from scout.research.research_hooks import on_session_end, _tool_call_tracker

        _tool_call_tracker["research_started"] = "already_saved"
        _tool_call_tracker["research_saved"] = True

        results_dir = tmp_path / "data" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        from scout.research import research_hooks as rh
        rh.RESULTS_DIR = results_dir

        on_session_end()
        # Keine neue Datei sollte angelegt werden
        assert len(list(results_dir.glob("*.json"))) == 0

    def test_no_save_if_no_start(self):
        """Kein auto-save wenn nie research_start aufgerufen wurde."""
        from scout.research.research_hooks import on_session_end, _tool_call_tracker

        _tool_call_tracker["research_started"] = None
        # Sollte nicht crashen
        on_session_end()
