"""Coverage-Ergänzung für scout/research/research_hooks.py.

Die Hooks laufen bei Session-Events (pre_llm_call, post_tool_call,
on_session_end). Hier werden Fehlerpfade (kaputte Tracker-/Ergebnisdateien,
fehlendes Honcho, fehlende Registry-Einträge) und die Kontext-Injektion
abgedeckt.

Tracker-Pfade und Ergebnisverzeichnisse zeigen auf tmp_path; der globale
Tracker-Dict wird nach jedem Test zurückgesetzt.
"""

from __future__ import annotations

import json

import pytest
from scout.research import research_hooks as hooks
from scout.shared.registry import registry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def hook_env(tmp_path, monkeypatch):
    """Isoliert Tracker-Datei, Plan- und Ergebnisverzeichnis."""
    results = tmp_path / "results"
    plans = tmp_path / "plans"
    results.mkdir()
    plans.mkdir()
    tracker_file = tmp_path / "tracker.json"

    monkeypatch.setattr(hooks, "RESULTS_DIR", results, raising=True)
    monkeypatch.setattr(hooks, "PLANS_DIR", plans, raising=True)
    monkeypatch.setattr(hooks, "TRACKER_PATH", tracker_file, raising=True)

    saved = dict(hooks._tool_call_tracker)
    hooks._tool_call_tracker.clear()
    hooks._tool_call_tracker.update({
        "firecrawl_calls": [],
        "research_started": None,
        "research_saved": False,
    })
    try:
        yield tracker_file
    finally:
        hooks._tool_call_tracker.clear()
        hooks._tool_call_tracker.update(saved)


def _result_file(results_dir, rid: str, **fields) -> None:
    payload = {"id": rid, "query": f"Query {rid}", "status": "completed"}
    payload.update(fields)
    (results_dir / f"{rid}.json").write_text(json.dumps(payload), encoding="utf-8")


# ---------------------------------------------------------------------------
# Tracker-Persistenz
# ---------------------------------------------------------------------------


class TestTrackerPersistence:
    def test_save_and_load_roundtrip(self, hook_env):
        hooks._tool_call_tracker["research_started"] = "r-42"

        hooks._save_tracker()

        assert json.loads(hook_env.read_text(encoding="utf-8"))["research_started"] == "r-42"

        hooks._tool_call_tracker["research_started"] = None
        hooks._load_tracker()

        assert hooks._tool_call_tracker["research_started"] == "r-42"

    def test_save_failure_is_silent(self, hook_env, monkeypatch):
        # Verzeichnis statt Datei → write_text scheitert mit OSError
        broken = hook_env.parent / "broken_dir"
        broken.mkdir()
        monkeypatch.setattr(hooks, "TRACKER_PATH", broken, raising=True)

        hooks._save_tracker()  # darf nicht werfen

    def test_load_ignores_corrupt_json(self, hook_env):
        hook_env.write_text("{ kein json", encoding="utf-8")
        hooks._tool_call_tracker["research_started"] = "unveraendert"

        hooks._load_tracker()

        assert hooks._tool_call_tracker["research_started"] == "unveraendert"

    def test_load_ignores_unreadable_path(self, hook_env, monkeypatch):
        broken = hook_env.parent / "broken_dir2"
        broken.mkdir()
        monkeypatch.setattr(hooks, "TRACKER_PATH", broken, raising=True)

        hooks._load_tracker()  # darf nicht werfen


# ---------------------------------------------------------------------------
# on_pre_llm_call
# ---------------------------------------------------------------------------


class TestPreLlmCall:
    def test_no_context_without_data(self, hook_env, monkeypatch):
        monkeypatch.setattr(hooks, "_check_honcho_available", lambda: False, raising=True)

        assert hooks.on_pre_llm_call(user_message="irgendwas") is None

    def test_honcho_hint_and_auto_synth_status(self, hook_env, monkeypatch):
        monkeypatch.setattr(hooks, "_check_honcho_available", lambda: True, raising=True)
        hooks._tool_call_tracker.update({
            "research_started": "r-1",
            "research_saved": True,
            "_auto_synth_triggered": True,
        })

        context = hooks.on_pre_llm_call(user_message="")

        assert "r-1" in context
        assert "Auto-Synthese ausgelöst" in context
        assert "honcho_search" in context

    def test_running_session_shows_progress_bar(self, hook_env, monkeypatch):
        monkeypatch.setattr(hooks, "_check_honcho_available", lambda: False, raising=True)
        hooks._tool_call_tracker.update({
            "research_started": "r-2",
            "firecrawl_calls": [{"tool": "mcp_firecrawl_search"}],
        })

        context = hooks.on_pre_llm_call(user_message="")

        assert "läuft (1 Firecrawl-Calls)" in context
        assert "▓" in context or "█" in context
        assert "Noch keine Firecrawl-Tools" not in context

    def test_running_session_without_tool_calls_warns(self, hook_env, monkeypatch):
        monkeypatch.setattr(hooks, "_check_honcho_available", lambda: False, raising=True)
        hooks._tool_call_tracker["research_started"] = "r-3"

        context = hooks.on_pre_llm_call(user_message="")

        assert "Noch keine Firecrawl-Tools aufgerufen" in context

    def test_many_results_trigger_dirty_data_banner(self, hook_env, monkeypatch):
        monkeypatch.setattr(hooks, "_check_honcho_available", lambda: False, raising=True)
        for i in range(81):
            _result_file(hooks.RESULTS_DIR, f"r{i:03d}")

        context = hooks.on_pre_llm_call(user_message="")

        assert "Datenmüll" in context
        assert "81" in context

    def test_relevant_results_are_injected(self, hook_env, monkeypatch):
        monkeypatch.setattr(hooks, "_check_honcho_available", lambda: False, raising=True)
        _result_file(
            hooks.RESULTS_DIR,
            "cbd1",
            query="CBD Legalisierung Deutschland",
            summary="Zusammenfassung zur Legalisierung von Cannabis.",
            sources=[{"url": "u1"}, {"url": "u2"}],
        )

        context = hooks.on_pre_llm_call(user_message="Wie ist die CBD Legalisierung?")

        assert "CBD Legalisierung Deutschland" in context
        assert "2 Quellen" in context
        assert "Zusammenfassung zur Legalisierung" in context
        assert "ID: `cbd1`" in context

    def test_only_stop_words_show_first_results(self, hook_env, monkeypatch):
        monkeypatch.setattr(hooks, "_check_honcho_available", lambda: False, raising=True)
        for i in range(4):
            _result_file(hooks.RESULTS_DIR, f"x{i}", query=f"Query {i}")

        context = hooks.on_pre_llm_call(user_message="was ist das und die der")

        # max_results=3, ohne verwertbare Wörter die ersten drei
        assert context.count("ID: `x") == 3


# ---------------------------------------------------------------------------
# post_tool_call
# ---------------------------------------------------------------------------


class TestPostToolCall:
    def test_ignores_unrelated_tools(self, hook_env):
        hooks.on_post_tool_call(tool_name="analysis_inspect", result="{}")

        assert hooks._tool_call_tracker["firecrawl_calls"] == []

    def test_firecrawl_call_is_tracked(self, hook_env, ):
        hooks._tool_call_tracker["research_started"] = "r-9"

        hooks.on_post_tool_call(tool_name="mcp_firecrawl_scrape", result="ok")

        calls = hooks._tool_call_tracker["firecrawl_calls"]
        assert len(calls) == 1
        assert calls[0]["tool"] == "mcp_firecrawl_scrape"
        assert "timestamp" in calls[0]
        assert hook_env.exists()

    def test_firecrawl_call_without_active_research_is_ignored(self, hook_env):
        hooks.on_post_tool_call(tool_name="mcp_firecrawl_search", result="ok")

        assert hooks._tool_call_tracker["firecrawl_calls"] == []

    def test_research_save_marks_saved_and_triggers_synthesis(self, hook_env, monkeypatch):
        hooks._tool_call_tracker["research_started"] = "r-10"
        monkeypatch.setattr(
            registry, "get_entry", lambda name: object() if name == "honcho_conclude" else None
        )

        hooks.on_post_tool_call(tool_name="research_save", result="{}")

        assert hooks._tool_call_tracker["research_saved"] is True
        assert hooks._tool_call_tracker["_auto_synth_triggered"] is True

    def test_research_save_without_honcho_entry(self, hook_env, monkeypatch):
        hooks._tool_call_tracker["research_started"] = "r-11"
        monkeypatch.setattr(registry, "get_entry", lambda name: None, raising=True)

        hooks.on_post_tool_call(tool_name="research_save", result="{}")

        assert hooks._tool_call_tracker["research_saved"] is True
        assert "_auto_synth_triggered" not in hooks._tool_call_tracker

    def test_research_save_survives_registry_error(self, hook_env, monkeypatch):
        hooks._tool_call_tracker["research_started"] = "r-12"

        def _boom(name):
            raise AttributeError("registry kaputt")

        monkeypatch.setattr(registry, "get_entry", _boom, raising=True)

        hooks.on_post_tool_call(tool_name="research_save", result="{}")

        assert hooks._tool_call_tracker["_auto_synth_triggered"] is False

    def test_research_save_without_started_research(self, hook_env):
        hooks.on_post_tool_call(tool_name="research_save", result="{}")

        assert hooks._tool_call_tracker["research_saved"] is False


# ---------------------------------------------------------------------------
# on_session_end
# ---------------------------------------------------------------------------


class TestSessionEnd:
    def _plan(self, rid: str, **fields) -> None:
        payload = {"id": rid, "query": "CBD Markt", "depth": 2}
        payload.update(fields)
        (hooks.PLANS_DIR / f"{rid}.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_noop_without_active_research(self, hook_env):
        hooks.on_session_end()

        assert list(hooks.RESULTS_DIR.glob("*.json")) == []

    def test_noop_when_already_saved(self, hook_env):
        hooks._tool_call_tracker.update({"research_started": "r-20", "research_saved": True})
        self._plan("r-20")

        hooks.on_session_end()

        assert list(hooks.RESULTS_DIR.glob("*.json")) == []
        assert (hooks.PLANS_DIR / "r-20.json").exists()

    def test_noop_without_plan_file(self, hook_env):
        hooks._tool_call_tracker["research_started"] = "gibtsnicht"

        hooks.on_session_end()

        assert list(hooks.RESULTS_DIR.glob("*.json")) == []

    def test_corrupt_plan_file_is_ignored(self, hook_env):
        hooks._tool_call_tracker["research_started"] = "broken"
        (hooks.PLANS_DIR / "broken.json").write_text("{ kein json", encoding="utf-8")

        hooks.on_session_end()

        assert list(hooks.RESULTS_DIR.glob("*.json")) == []
        assert (hooks.PLANS_DIR / "broken.json").exists()

    def test_partial_result_is_written_and_plan_removed(self, hook_env):
        hooks._tool_call_tracker.update({
            "research_started": "r-21",
            "firecrawl_calls": [{"tool": "a"}, {"tool": "b"}],
        })
        self._plan("r-21", created_at="2026-01-01T00:00:00+00:00")

        hooks.on_session_end()

        stored = json.loads((hooks.RESULTS_DIR / "r-21.json").read_text(encoding="utf-8"))
        assert stored["status"] == "partial"
        assert stored["_auto_saved"] is True
        assert stored["query"] == "CBD Markt"
        assert stored["depth"] == 2
        assert "2 Firecrawl-Tool-Calls" in stored["summary"]
        assert stored["created_at"] == "2026-01-01T00:00:00+00:00"
        assert not (hooks.PLANS_DIR / "r-21.json").exists()
        # Tracker wurde zurückgesetzt
        assert hooks._tool_call_tracker["research_started"] is None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_load_all_results_skips_corrupt_files(self, hook_env):
        _result_file(hooks.RESULTS_DIR, "good", summary="ok", findings=[1, 2], sources=[1])
        (hooks.RESULTS_DIR / "bad.json").write_text("kein json", encoding="utf-8")

        results = hooks._load_all_results()

        assert [r["id"] for r in results] == ["good"]
        assert results[0]["findings_count"] == 2
        assert results[0]["sources_count"] == 1

    def test_load_all_results_without_directory(self, hook_env, monkeypatch, tmp_path):
        monkeypatch.setattr(hooks, "RESULTS_DIR", tmp_path / "fehlt", raising=True)

        assert hooks._load_all_results() == []

    def test_honcho_check_returns_false_on_error(self, monkeypatch):
        def _boom(name):
            raise RuntimeError("registry weg")

        monkeypatch.setattr(registry, "get_entry", _boom, raising=True)

        assert hooks._check_honcho_available() is False

    def test_honcho_check_true_for_registered_tool(self, monkeypatch):
        monkeypatch.setattr(registry, "get_entry", lambda name: object(), raising=True)

        assert hooks._check_honcho_available() is True

    def test_user_input_prefers_first_known_key(self):
        assert hooks._get_user_input(message="zweit", user_message="erst") == "erst"
        assert hooks._get_user_input(text="dritt", message="zweit") == "zweit"
        assert hooks._get_user_input(unknown=1) == ""

    def test_find_relevant_empty_input_returns_nothing(self):
        assert hooks._find_relevant("", [{"query": "x", "summary": ""}]) == []

    def test_find_relevant_ranks_by_overlap(self):
        results = [
            {"query": "Steuerrecht", "summary": "Umsatzsteuer"},
            {"query": "CBD Markt", "summary": "CBD Öl Preise"},
        ]

        found = hooks._find_relevant("CBD Preise Markt", results, max_results=1)

        assert [r["query"] for r in found] == ["CBD Markt"]

    def test_reset_tracker_clears_calls(self, hook_env):
        hooks._tool_call_tracker["firecrawl_calls"] = [{"tool": "x"}]
        hooks._tool_call_tracker["research_saved"] = True

        hooks.reset_tracker("neu")

        assert hooks._tool_call_tracker["research_started"] == "neu"
        assert hooks._tool_call_tracker["firecrawl_calls"] == []
        assert hooks._tool_call_tracker["research_saved"] is False
        assert hook_env.exists()
