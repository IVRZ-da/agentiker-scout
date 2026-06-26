"""Test: Hooks — pre_llm_call, post_tool_call, on_session_end."""



from scout.bughunt.bughunt_hooks import (
    _hook_cache,
    _is_bughunt_related,
    on_post_tool_call,
    on_pre_llm_call,
    on_session_end,
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
# pre_llm_call Tests
# ======================================================================

class TestPreLlmCall:
    def test_no_messages(self):
        assert on_pre_llm_call() is None
        assert on_pre_llm_call(messages=[]) is None

    def test_no_keyword(self):
        result = on_pre_llm_call(messages=[
            {"role": "user", "content": "Wie ist das Wetter?"}
        ])
        assert result is None

    def test_keyword_triggers_injection(self):
        clear_cache()
        result = on_pre_llm_call(messages=[
            {"role": "user", "content": "Starte einen Bug-Hunt"}
        ])
        assert result is not None
        assert "[BUG-HUNT PLUGIN]" in result

    def test_active_session_in_banner(self):
        clear_cache()
        import bughunt_core as core
        tracker = core.get_tracker()
        s = core.BugHuntSession(project="/test")
        core.save_session(s)
        tracker.start(s.session_id)

        result = on_pre_llm_call(messages=[
            {"role": "user", "content": "Zeige die Bugs"}
        ])
        # Cleanup
        tracker.reset()
        assert result is not None
        assert s.session_id in result

    def test_non_dict_message(self):
        """Messages mit non-dict content werden ignoriert."""
        result = on_pre_llm_call(messages=["just a string"])
        assert result is None

    def test_cached_recent_sessions(self):
        clear_cache()
        # Erster Aufruf ohne aktive Session
        on_pre_llm_call(messages=[
            {"role": "user", "content": "Bug-Hunt starten"}
        ])
        # Cache sollte jetzt gefüllt sein
        assert "recent_sessions" in _hook_cache


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


# ======================================================================
# on_session_end Tests
# ======================================================================

class TestOnSessionEnd:
    def test_no_active_session(self):
        import bughunt_core as core
        core.get_tracker().reset()
        # Sollte nicht crashen
        on_session_end()

    def test_active_session_gets_closed(self):
        import bughunt_core as core
        tracker = core.get_tracker()
        s = core.BugHuntSession(project="/test")
        core.save_session(s)
        tracker.start(s.session_id)

        on_session_end()

        # Session sollte geschlossen sein
        loaded = core.load_session(s.session_id)
        assert loaded is not None
        assert loaded.status == "closed"
        assert "Bug-Hunt" in loaded.summary
        # Tracker sollte zurückgesetzt sein
        assert not tracker.is_active()

    def test_session_with_findings(self):
        import bughunt_core as core
        tracker = core.get_tracker()
        s = core.BugHuntSession(project="/test")
        s.add_finding(core.Finding(title="P0 Bug", severity="P0"))
        s.add_finding(core.Finding(title="P1 Bug", severity="P1"))
        core.save_session(s)
        tracker.start(s.session_id)

        on_session_end()

        loaded = core.load_session(s.session_id)
        assert loaded.status == "closed"
        assert "P0=1" in loaded.summary
        assert "P1=1" in loaded.summary

    def test_honcho_dispatch(self):
        import bughunt_core as core
        tracker = core.get_tracker()
        s = core.BugHuntSession(project="/test")
        core.save_session(s)
        tracker.start(s.session_id)

        # on_session_end versucht honcho_conclude zu dispatchen
        # Should not crash even if honcho is not available
        on_session_end()
        assert not tracker.is_active()
