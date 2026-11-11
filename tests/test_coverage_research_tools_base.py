"""Randpfade in ``research/tools/base.py``.

Bisher ungetestet: die leere ``research_id`` in ``_validate_research_id`` und
der Plan-Follow-Zweig, wenn der Registry-Handler fehlt oder einen JSON-String
statt eines Dicts liefert. Die Registry wird als Fake-Modul in ``sys.modules``
gesetzt (monkeypatch räumt auf).
"""

from __future__ import annotations

import sys
import types

from scout.research.tools import base


def _fake_registry(monkeypatch, get_entry):
    """Ersetzt ``scout.shared.registry`` durch ein Fake-Modul."""
    fake = types.ModuleType("scout.shared.registry")

    class Registry:
        def get_entry(self, name):  # noqa: ARG002
            return get_entry()

    fake.registry = Registry()
    monkeypatch.setitem(sys.modules, "scout.shared.registry", fake)


class TestValidateResearchId:
    def test_empty_id_is_rejected_with_message(self):
        assert base._validate_research_id("") == "research_id ist erforderlich"

    def test_plain_id_is_valid(self):
        assert base._validate_research_id("research-2026-01-01-ab12") is None


class TestTryCreatePlanFollowPlan:
    def test_returns_none_when_handler_is_not_callable(self, monkeypatch):
        class Entry:
            handler = "kein callable"

        _fake_registry(monkeypatch, lambda: Entry())

        assert base._try_create_plan_follow_plan("frage", "rid") is None

    def test_parses_json_string_result(self, monkeypatch):
        recorded: dict = {}

        class Entry:
            @staticmethod
            def handler(args):
                recorded.update(args)
                return '{"plan_id": "p-1", "status": "ok"}'

        _fake_registry(monkeypatch, lambda: Entry())

        result = base._try_create_plan_follow_plan("Docker Caching", "rid-1")

        assert result == {"plan_id": "p-1", "status": "ok"}
        assert recorded["goal"] == "Recherche: Docker Caching"
        assert recorded["template"] == "research"
