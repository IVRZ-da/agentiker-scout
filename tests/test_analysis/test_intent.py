"""Tests für shared/intent.py — Intent-Erkennung + Context-Building."""

from __future__ import annotations

from scout.shared.intent import _build_intent_context, _detect_intent


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
        """Web-Intent wird erkannt."""
        assert _detect_intent("website analysieren") == "web"

    def test_no_match(self):
        assert _detect_intent("hallo wie geht es dir") is None
        assert _detect_intent("") is None

    def test_case_insensitive(self):
        assert _detect_intent("BUG IN DER LOGIK") == "bug"

    def test_bug_over_code(self):
        """Bug hat höhere Priorität als Code."""
        assert _detect_intent("analysiere den bug") == "bug"

    def test_research_over_code(self):
        """Research hat höhere Priorität als Code."""
        assert _detect_intent("recherchiere und analysiere") == "research"


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

    def test_unknown_domain(self):
        context = _build_intent_context("unknown_domain_xyz")
        assert context is None or context == ""

    def test_cache_hit(self):
        """Zweiter Aufruf innerhalb TTL trifft Cache."""
        ctx1 = _build_intent_context("code")
        ctx2 = _build_intent_context("code")
        assert ctx1 == ctx2
