"""Test: Hooks — pre_llm_call, post_tool_call, on_session_end."""



from scout.bughunt.bughunt_hooks import (
    _hook_cache,
    _is_bughunt_related,
    on_post_tool_call,
    session_context,
)


def clear_cache():
    _hook_cache.clear()


# ======================================================================
# Keyword Detection Tests
# ======================================================================

class TestKeywordDetection:
    def test_detects_bug(self):
        assert _is_bughunt_related("Ich habe einen Bug gefunden")

    def test_detects_security(self):
        assert _is_bughunt_related("Security-Lücke in der API")

    def test_detects_scan(self):
        assert _is_bughunt_related("Scannen wir den Code")

    def test_detects_audit(self):
        assert _is_bughunt_related("Führe ein Audit durch")

    def test_detects_bughunt(self):
        assert _is_bughunt_related("Starte einen Bug-Hunt")

    def test_detects_vulnerability(self):
        assert _is_bughunt_related("Gibt es eine vulnerability?")

    def test_ignores_normal(self):
        assert not _is_bughunt_related("Hallo, wie geht es dir?")

    def test_ignores_empty(self):
        assert not _is_bughunt_related("")

    def test_ignores_irrelevant(self):
        assert not _is_bughunt_related("Erstelle ein neues Produkt")

    def test_unicode_normalization(self):
        assert _is_bughunt_related("Sicherheitsprüfung")


# ======================================================================
# session_context Tests (Baustein des zentralen pre_llm_call-Hooks)
# ======================================================================

class TestSessionContext:
    def test_no_active_session_still_returns_block(self):
        import bughunt_core as core
        core.get_tracker().reset()
        clear_cache()
        result = session_context()
        assert result is not None
        assert "[BUG-HUNT PLUGIN]" in result

    def test_active_session_in_context(self):
        clear_cache()
        import bughunt_core as core
        tracker = core.get_tracker()
        s = core.BugHuntSession(project="/test")
        core.save_session(s)
        tracker.start(s.session_id)
        try:
            result = session_context()
            assert s.session_id in result
            assert "Aktive Session" in result
        finally:
            tracker.reset()

    def test_active_session_with_findings(self):
        clear_cache()
        import bughunt_core as core
        tracker = core.get_tracker()
        s = core.BugHuntSession(project="/test")
        s.add_finding(core.Finding(title="P0 Bug", severity="P0"))
        core.save_session(s)
        tracker.start(s.session_id)
        try:
            assert "P0=1" in session_context()
        finally:
            tracker.reset()


# ======================================================================
# Integration: der registrierte pre_llm_call-Hook haengt den Block an
# ======================================================================

class TestIntentHookIntegration:
    def test_bug_intent_appends_session_block(self):
        from scout.shared.intent import on_pre_llm_call

        clear_cache()
        result = on_pre_llm_call(
            user_message="Starte einen Bug-Hunt",
            conversation_history=[],
            is_first_turn=True,
        )
        assert result is not None
        assert "BUG-HUNT" in result


# ======================================================================
# post_tool_call Tests
# ======================================================================

class TestPostToolCall:
    def test_inactive_tracker_ignores(self):
        import bughunt_core as core
        tracker = core.get_tracker()
        tracker.reset()
        # Sollte nicht crashen
        on_post_tool_call(tool_name="code_search", args={"path": "/x"})

    def test_tracks_code_search(self):
        import bughunt_core as core
        tracker = core.get_tracker()
        s = core.BugHuntSession(project="/test")
        core.save_session(s)
        tracker.start(s.session_id)

        on_post_tool_call(tool_name="code_search", args={"path": "/src"},
                          status="ok", result="some result")
        assert len(tracker.tools_used) == 1
        assert tracker.tools_used[0]["tool_name"] == "code_search"
        assert "/src" in tracker.files_touched
        tracker.reset()

    def test_tracks_bug_hunt_tools(self):
        import bughunt_core as core
        tracker = core.get_tracker()
        s = core.BugHuntSession(project="/test")
        core.save_session(s)
        tracker.start(s.session_id)

        on_post_tool_call(tool_name="bug_hunt_finding", args={"title": "Bug"})
        assert len(tracker.tools_used) == 1
        tracker.reset()

    def test_ignores_other_tools(self):
        import bughunt_core as core
        tracker = core.get_tracker()
        s = core.BugHuntSession(project="/test")
        core.save_session(s)
        tracker.start(s.session_id)

        on_post_tool_call(tool_name="terminal", args={})
        assert len(tracker.tools_used) == 0
        tracker.reset()

    def test_ignores_error_results(self):
        import bughunt_core as core
        tracker = core.get_tracker()
        s = core.BugHuntSession(project="/test")
        core.save_session(s)
        tracker.start(s.session_id)

        on_post_tool_call(tool_name="code_search", args={},
                          result='{"error": "something failed"}')
        assert len(tracker.tools_used) == 0
        tracker.reset()

    def test_extracts_path_from_args(self):
        import bughunt_core as core
        tracker = core.get_tracker()
        s = core.BugHuntSession(project="/test")
        core.save_session(s)
        tracker.start(s.session_id)

        on_post_tool_call(tool_name="code_diagnostics",
                          args={"path": "/src/main.ts"})
        assert "/src/main.ts" in tracker.files_touched
        tracker.reset()

    def test_tracks_mcp_devtools_tools(self):
        """mcp_chrome_devtools_* Tools werden in aktiver Session getrackt."""
        import bughunt_core as core
        tracker = core.get_tracker()
        s = core.BugHuntSession(project="/test")
        core.save_session(s)
        tracker.start(s.session_id)

        on_post_tool_call(tool_name="mcp_chrome_devtools_navigate_page",
                          args={"url": "https://example.com"})
        assert len(tracker.tools_used) == 1
        assert tracker.tools_used[0]["tool_name"] == "mcp_chrome_devtools_navigate_page"
        tracker.reset()

    def test_ignores_non_mcp_devtools(self):
        """Nicht-MCP-DevTools werden nicht getrackt (kein aktiver Session-Bezug)."""
        import bughunt_core as core
        tracker = core.get_tracker()
        s = core.BugHuntSession(project="/test")
        core.save_session(s)
        tracker.start(s.session_id)

        on_post_tool_call(tool_name="mcp_not_devtools_test", args={})
        assert len(tracker.tools_used) == 0
        tracker.reset()
