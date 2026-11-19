"""Intent-Hints nennen nur Tool-Namen, die im aktiven Modus existieren.

Die ``[SCOUT]``-Blöcke landen im Prompt (``pre_llm_call``). Vor der Fusion nannten sie
42 Einzelnamen; mit ``SCOUT_NAMESPACES=0`` gilt das weiterhin. Beides muss stimmen —
ein Hint auf ein nicht existierendes Tool ist ein toter Verweis, den das Modell
brav zu benutzen versucht.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from scout import namespaces  # noqa: E402
from scout.shared import intent  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_contexts():
    intent._CONTEXT_CACHE = None
    intent._CONTEXT_MODE = None
    intent._INTENT_CACHE.clear()
    yield
    intent._CONTEXT_CACHE = None
    intent._CONTEXT_MODE = None
    intent._INTENT_CACHE.clear()


def test_namespace_mode_uses_op_style(monkeypatch):
    monkeypatch.delenv(namespaces.NAMESPACES_ENV, raising=False)
    contexts = intent._contexts_for_mode()
    assert 'bughunt(op="start"' in contexts["bug"]
    assert 'analysis(op="inspect"' in contexts["code"]
    assert 'research(op="start"' in contexts["research"]
    assert "bug_hunt_start(" not in contexts["bug"]


def test_legacy_mode_uses_flat_names(monkeypatch):
    monkeypatch.setenv(namespaces.NAMESPACES_ENV, "0")
    contexts = intent._contexts_for_mode()
    assert "bug_hunt_start(project)" in contexts["bug"]
    assert "analysis_inspect(path, depth=1-5)" in contexts["code"]
    assert 'bughunt(op=' not in contexts["bug"]


def test_mode_switch_rebuilds_hints(monkeypatch):
    """Ein Wechsel zur Laufzeit darf keine veralteten Namen stehen lassen."""
    monkeypatch.delenv(namespaces.NAMESPACES_ENV, raising=False)
    assert 'bughunt(op="start"' in intent._contexts_for_mode()["bug"]
    monkeypatch.setenv(namespaces.NAMESPACES_ENV, "0")
    assert "bug_hunt_start(" in intent._contexts_for_mode()["bug"]
    monkeypatch.delenv(namespaces.NAMESPACES_ENV, raising=False)
    assert 'bughunt(op="start"' in intent._contexts_for_mode()["bug"]


def test_hint_ops_exist_in_the_dispatchers(monkeypatch):
    """Jeder genannte op muss im Enum seines Dispatchers stehen."""
    monkeypatch.delenv(namespaces.NAMESPACES_ENV, raising=False)
    from scout.shared.tool_registry import collect

    specs = namespaces.build_tool_specs(namespaces.build_catalog(collect()), lambda t: None)
    enum = {s["name"]: set(s["schema"]["parameters"]["properties"]["op"]["enum"]) for s in specs}

    for key, domain in (("bug", "bughunt"), ("code", "analysis"), ("research", "research")):
        for spec_domain, op, _args, _desc in intent._INTENT_SPECS[key][1]:
            assert spec_domain in enum, spec_domain
            assert op in enum[spec_domain], f"{key}: op {op!r} fehlt in {spec_domain}"


def test_unknown_intent_returns_none():
    assert intent._contexts_for_mode().get("gibtsnicht") is None


# ─── v0.6.7: kopierbares Bridge-Muster gegen tote Verweise ──────────────────

import json as _json  # noqa: E402
import re as _re  # noqa: E402


def _bridge_payload(context: str) -> dict:
    """Zieht den ``tool_call({...})``-Block aus einem Hint und parst ihn als JSON."""
    match = _re.search(r"tool_call\((\{.*?\})\)", context, _re.DOTALL)
    assert match, f"kein tool_call-Muster im Hint: {context!r}"
    return _json.loads(match.group(1))


def _reset_hint_cache() -> None:
    """Hints sind modulweit gecacht — Tests muessen den Cache nach dem Mock leeren."""
    intent._CONTEXT_CACHE = None
    intent._CONTEXT_MODE = None
    intent._INTENT_CACHE.clear()


def test_deferred_hints_carry_a_callable_payload(monkeypatch):
    """Bridge aktiv (Plugin-Tools deferred) — der Hint muss den Aufruf mitliefern."""
    monkeypatch.delenv(namespaces.NAMESPACES_ENV, raising=False)
    monkeypatch.setattr(intent, "_tool_search_active", lambda: True)
    _reset_hint_cache()
    contexts = intent._contexts_for_mode()
    for key, domain in (("code", "analysis"), ("bug", "bughunt"), ("research", "research")):
        payload = _bridge_payload(contexts[key])
        call = payload["calls"][0]
        assert call["name"] == domain
        assert isinstance(call["arguments"].get("op"), str) and call["arguments"]["op"]


def test_eager_hints_have_no_bridge_payload(monkeypatch):
    """``tools.tool_search.enabled: off`` — alle Tools eager, ``tool_call`` existiert nicht.

    Der Hint darf dann keinen Aufrufblock nennen; ein toter Tool-Name im Prompt ist genau
    der Fehler, den die Kopplung an ``namespaces_enabled()`` erzeugt hat.
    """
    monkeypatch.delenv(namespaces.NAMESPACES_ENV, raising=False)
    monkeypatch.setattr(intent, "_tool_search_active", lambda: False)
    _reset_hint_cache()
    contexts = intent._contexts_for_mode()
    for key in ("code", "bug", "research", "framework"):
        assert "tool_call(" not in contexts[key], f"{key} nennt tool_call trotz eager-Set"


def test_legacy_hints_have_no_bridge_payload(monkeypatch):
    """Im Legacy-Modus sind die 42 Einzel-Tools eager — kein Bridge-Muster nötig."""
    monkeypatch.setenv(namespaces.NAMESPACES_ENV, "0")
    monkeypatch.setattr(intent, "_tool_search_active", lambda: False)
    _reset_hint_cache()
    for key in ("code", "bug", "research"):
        assert "tool_call(" not in intent._contexts_for_mode()[key]


def test_mcp_hints_stay_bridge_free(monkeypatch):
    """db/web/debug zielen auf eager MCP-Tools — kein tool_call-Muster."""
    monkeypatch.delenv(namespaces.NAMESPACES_ENV, raising=False)
    monkeypatch.setattr(intent, "_tool_search_active", lambda: True)
    _reset_hint_cache()
    contexts = intent._contexts_for_mode()
    for key in ("db", "web"):
        assert "tool_call(" not in contexts[key]
