"""Vertragstest fuer den pre_llm_call-Hook gegen Hermes 0.23.1.

Hermes 0.23.1 ruft pre_llm_call mit genau diesem Kwarg-Satz auf
(agent/turn_context.py::_collect_pre_llm_call_context):

    session_id, task_id, turn_id, user_message, conversation_history,
    is_first_turn, model, platform, parent_session_id, sender_id

``messages`` gibt es nicht mehr. Dieser Test haelt den Vertrag fest, damit ein
stiller Ausfall (Hook liefert immer None) nicht wieder unbemerkt bleibt.
"""

from __future__ import annotations

import pytest
from scout.shared import intent


def hermes_kwargs(user_message: object = "", conversation_history=None, **extra):
    """Kwarg-Satz exakt wie Hermes 0.23.1 (plus optionale Zusatzfelder)."""
    kwargs = {
        "session_id": "s1",
        "task_id": "t1",
        "turn_id": "turn1",
        "user_message": user_message,
        "conversation_history": conversation_history or [],
        "is_first_turn": not conversation_history,
        "model": "deepseek-v4-flash",
        "platform": "cli",
        "parent_session_id": "",
        "sender_id": "",
    }
    kwargs.update(extra)
    return kwargs


def test_current_contract_returns_context():
    """Der echte 0.23.1-Kwarg-Satz muss Intent-Kontext liefern."""
    result = intent.on_pre_llm_call(**hermes_kwargs("analysiere die architektur dieses projekts"))
    assert isinstance(result, str)
    assert result.strip()
    assert "SCOUT" in result


def test_user_message_is_primary_source():
    """user_message gewinnt gegen den legacy messages-Key."""
    result = intent.on_pre_llm_call(
        **hermes_kwargs(
            "analysiere die architektur",
            messages=[{"role": "user", "content": "Wie ist das Wetter?"}],
        )
    )
    assert result and "SCOUT" in result


def test_conversation_history_fallback():
    """Ohne user_message greift die letzte User-Nachricht aus conversation_history."""
    history = [
        {"role": "user", "content": "hallo"},
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "starte einen bug-hunt im projekt"},
    ]
    result = intent.on_pre_llm_call(**hermes_kwargs("", history))
    assert result and "SCOUT" in result


def test_legacy_messages_still_work():
    """Alte Hermes-Versionen (nur messages) duerfen weiter funktionieren."""
    result = intent.on_pre_llm_call(messages=[{"role": "user", "content": "analysiere den code"}])
    assert result and "SCOUT" in result


def test_block_list_content_is_normalized():
    """user_message darf eine Block-Liste sein (multimodale Nachrichten)."""
    blocks = [{"type": "text", "text": "analysiere die architektur"}]
    result = intent.on_pre_llm_call(**hermes_kwargs(blocks))
    assert result and "SCOUT" in result


def test_unknown_kwargs_do_not_break():
    """Hermes darf Felder ergaenzen, ohne den Hook zu killen."""
    result = intent.on_pre_llm_call(**hermes_kwargs("analysiere den code", brand_new_field=123))
    assert result and "SCOUT" in result


def test_no_user_message_returns_none():
    assert intent.on_pre_llm_call(**hermes_kwargs("")) is None
    assert intent.on_pre_llm_call() is None
    assert intent.on_pre_llm_call(conversation_history=[]) is None


def test_non_matching_message_returns_none():
    assert intent.on_pre_llm_call(**hermes_kwargs("Wie ist das Wetter morgen?")) is None


def test_only_user_role_counts():
    """Assistenten-Nachrichten duerfen keinen Intent ausloesen."""
    history = [{"role": "assistant", "content": "analysiere die architektur"}]
    assert intent.on_pre_llm_call(**hermes_kwargs("", history)) is None


def test_returns_str_or_none_only():
    """Der Hook darf nur str/None liefern - alles andere wuerde Hermes verwerfen."""
    for msg in ("analysiere den code", "hallo", ""):
        result = intent.on_pre_llm_call(**hermes_kwargs(msg))
        assert result is None or isinstance(result, str)


def test_hook_never_raises(monkeypatch):
    """Ein Fehler in der Detection darf den Turn nicht abbrechen."""

    def boom(_msg):
        raise RuntimeError("detector kaputt")

    monkeypatch.setattr(intent, "_detect_intent", boom)
    assert intent.on_pre_llm_call(**hermes_kwargs("analysiere den code")) is None


def test_content_to_text_handles_shapes():
    assert intent._content_to_text("abc") == "abc"
    assert intent._content_to_text([{"text": "a"}, "b"]) == "a\nb"
    assert intent._content_to_text(None) == ""
    assert intent._content_to_text(42) == ""


@pytest.mark.parametrize(
    "message,expected_domain",
    [
        ("analysiere die architektur", "code"),
        ("starte einen bug-hunt", "bug"),
    ],
)
def test_intent_domains(message, expected_domain):
    assert intent._detect_intent(message) == expected_domain
