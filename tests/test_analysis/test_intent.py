"""Tests für shared/intent.py — Intent-Erkennung + Context-Building."""

from __future__ import annotations

from scout.shared.intent import INTENT_MAP, _build_intent_context, _detect_intent


class TestDetectIntent:
    def test_bug_intent(self):
        assert _detect_intent("analysiere den bug") == "bug"
        assert _detect_intent("there is an error in the code") == "bug"
        assert _detect_intent("crash beim start") == "bug"

    def test_analysis_code_intent(self):
        assert _detect_intent("zeig mir die struktur") == "code"
        assert _detect_intent("explain the code") == "code"

    def test_research_intent(self):
        assert _detect_intent("recherchiere was ist das") == "research"
        assert _detect_intent("suche informationen über") == "research"

    def test_db_intent(self):
        assert _detect_intent("sql query ist langsam") == "db"

    def test_web_intent(self):
        assert _detect_intent("website analysieren") == "web"

    def test_debug_intent(self):
        """Debug-Keywords werden erkannt."""
        assert _detect_intent("prüf die browser console") == "debug"
        assert _detect_intent("devtools check") == "debug"
        assert _detect_intent("seite lädt nicht richtig") == "debug"

    def test_no_match(self):
        assert _detect_intent("hallo wie geht es dir") is None
        assert _detect_intent("") is None

    def test_case_insensitive(self):
        assert _detect_intent("BUG IN DER LOGIK") == "bug"

    def test_priority_bug_over_debug(self):
        """Bug hat höhere Priorität als Debug."""
        assert _detect_intent("prüf die browser console auf errors") == "bug"

    def test_priority_debug_over_code(self):
        """Debug hat höhere Priorität als Code."""
        assert _detect_intent("console devtools check") == "debug"

    def test_priority_research_over_debug(self):
        """Research hat höhere Priorität als Debug."""
        assert _detect_intent("recherchiere console") == "research"

    def test_debug_in_domain_map(self):
        """debug ist in INTENT_MAP registriert."""
        assert "debug" in INTENT_MAP
        assert "console" in INTENT_MAP["debug"]
        assert "devtools" in INTENT_MAP["debug"]
        assert "ui error" in INTENT_MAP["debug"]


class TestBuildIntentContext:
    def test_code_context(self):
        context = _build_intent_context("code")
        assert context is not None
        assert "code" in context.lower() or "analyse" in context.lower() or "analys" in context.lower()

    def test_bug_context(self):
        context = _build_intent_context("bug")
        assert context is not None

    def test_research_context(self):
        context = _build_intent_context("research")
        assert context is not None

    def test_debug_context(self):
        """debug-Context enthält DevTools-Tool-Hinweise."""
        context = _build_intent_context("debug")
        assert context is not None
        assert "DevTools" in context or "devtools" in context
        assert "console_messages" in context
        assert "network_requests" in context

    def test_unknown_domain(self):
        context = _build_intent_context("unknown_domain_xyz")
        assert context is None or context == ""

    def test_cache_hit(self):
        """Zweiter Aufruf innerhalb TTL trifft Cache."""
        ctx1 = _build_intent_context("code")
        ctx2 = _build_intent_context("code")
        assert ctx1 == ctx2


class TestOnPreLlmCall:
    """Testet die on_pre_llm_call Hook-Funktion."""

    def test_no_messages(self):
        from scout.shared.intent import on_pre_llm_call
        result = on_pre_llm_call()
        assert result is None

    def test_empty_messages(self):
        from scout.shared.intent import on_pre_llm_call
        result = on_pre_llm_call(messages=[])
        assert result is None

    def test_no_user_message(self):
        from scout.shared.intent import on_pre_llm_call
        result = on_pre_llm_call(messages=[{"role": "assistant", "content": "hallo"}])
        assert result is None

    def test_no_relevant_keyword(self):
        from scout.shared.intent import on_pre_llm_call
        result = on_pre_llm_call(messages=[
            {"role": "user", "content": "wie ist das Wetter heute?"}
        ])
        assert result is None

    def test_with_bug_keyword(self):
        from scout.shared.intent import on_pre_llm_call
        result = on_pre_llm_call(messages=[
            {"role": "user", "content": "analysiere den bug in der login funktion"}
        ])
        assert result is not None

    def test_with_code_keyword(self):
        from scout.shared.intent import on_pre_llm_call
        result = on_pre_llm_call(messages=[
            {"role": "user", "content": "zeig mir die codestruktur"}
        ])
        assert result is not None

    def test_with_debug_keyword(self):
        """on_pre_llm_call erkennt Debug-Keywords."""
        from scout.shared.intent import on_pre_llm_call
        result = on_pre_llm_call(messages=[
            {"role": "user", "content": "bitte console devtools prüfen"}
        ])
        assert result is not None
        assert "DevTools" in result or "devtools" in result
