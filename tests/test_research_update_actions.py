"""research_update buendelt seit 0.6.0 delete/tag/verify/merge/compare.

Die Einzel-Tools sind nicht mehr registriert; ihre Logik muss ueber
``action=`` erreichbar bleiben, sonst ist die Konsolidierung ein Rueckschritt.
"""
from __future__ import annotations

import json

import pytest

from scout.research.tools.crud import research_save, research_start, research_update
from scout.research.tools.export import research_export


def _payload(raw: str) -> dict:
    return json.loads(raw)


@pytest.fixture
def two_results():
    """Zwei abgeschlossene Recherchen mit Findings und Quellen."""
    ids = []
    for query, summary in [
        ("Next.js 15 caching defaults", "Next 15 cached fetch per default."),
        ("Next.js 16 caching defaults", "Next 16 ist explizit opt-in."),
    ]:
        started = _payload(research_start({"query": query, "depth": 1}))
        rid = started["research_id"]
        saved = _payload(research_save({
            "research_id": rid,
            "summary": summary,
            "status": "completed",
            "findings": [{"finding": f"Fakt zu {query}"}],
            "sources": [{"url": f"https://example.com/{rid}"}],
        }))
        assert saved.get("status") in ("ok", "completed"), f"research_save fehlgeschlagen: {saved}"
        ids.append(rid)
    return ids


def test_action_patch_is_default(two_results):
    rid = two_results[0]
    out = _payload(research_update({"research_id": rid, "summary": "Neue Zusammenfassung"}))
    assert out.get("status") == "ok", out
    assert out["research_id"] == rid


def test_action_tag_via_tag_action(two_results):
    rid = two_results[0]
    out = research_update({
        "research_id": rid,
        "action": "tag",
        "tags": ["docker", "performance"],
        "tag_action": "add",
    })
    payload = _payload(out)
    assert payload.get("status") == "ok", payload
    assert "docker" in json.dumps(payload), payload


def test_action_compare_dispatches(two_results, monkeypatch):
    """action=compare wird an research_compare weitergeleitet (Logik dort getestet)."""
    import scout.research.tools.export as export_mod

    called = {}

    def spy(args):
        called["ids"] = args.get("research_ids")
        return '{"status": "ok", "compared": 2}'

    monkeypatch.setattr(export_mod, "research_compare", spy)
    payload = _payload(research_update({
        "research_id": two_results[0],
        "action": "compare",
        "research_ids": two_results,
    }))
    assert payload.get("status") == "ok", payload
    assert called["ids"] == two_results


def test_action_merge_dispatches(two_results, monkeypatch):
    """action=merge wird an research_merge weitergeleitet."""
    import scout.research.tools.export as export_mod

    def spy(args):
        return '{"status": "ok", "merged": true}'

    monkeypatch.setattr(export_mod, "research_merge", spy)
    payload = _payload(research_update({
        "research_id": two_results[0],
        "action": "merge",
        "research_ids": two_results,
        "summary": "Gemeinsame Antwort",
    }))
    assert payload.get("status") == "ok", payload


def test_action_verify(two_results):
    payload = _payload(research_update({
        "research_id": two_results[0], "action": "verify",
    }))
    assert payload.get("status") == "ok", payload


def test_action_delete(two_results):
    rid = two_results[1]
    payload = _payload(research_update({"research_id": rid, "action": "delete"}))
    assert payload.get("status") == "ok", payload
    # weg ist weg
    again = _payload(research_update({"research_id": rid, "action": "delete"}))
    assert again.get("status") == "error", again


def test_unknown_action_is_rejected(two_results):
    payload = _payload(research_update({
        "research_id": two_results[0], "action": "explode",
    }))
    assert payload.get("status") == "error"
    assert "Unbekannte" in json.dumps(payload)


def test_append_object_form(two_results):
    """Schema-Form ``append: {findings, sources}`` wird entpackt."""
    rid = two_results[0]
    payload = _payload(research_update({
        "research_id": rid,
        "append": {
            "findings": [{"finding": "zusaetzlicher Fakt"}],
            "sources": [{"url": "https://example.com/extra"}],
        },
    }))
    assert payload.get("status") == "ok", payload
    assert payload["findings_count"] >= 2


def test_export_all_true_replaces_export_all_tool(two_results):
    out = research_export({"all": True})
    payload = _payload(out)
    assert payload.get("status") == "ok", payload
    assert payload.get("total", 0) >= 2, payload
    assert payload.get("format") in ("json", "markdown", "text"), payload
