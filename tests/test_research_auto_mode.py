"""mode=auto: research_start fuehrt die Recherche aus und speichert das Ergebnis.

Ohne Netzwerk: der Orchestrator wird ersetzt. Geprueft wird das Verhalten des
Handlers — Fehler ehrlich melden, Material speichern, Luecken weitergeben.
"""
from __future__ import annotations

import json

import pytest

from scout.research.orchestrator import Finding, Outcome
from scout.research.planner import build_plan
from scout.research.tools.crud import due_schedules, research_start
from scout.research.tools.search import research_status


def _outcome(query: str, findings: int = 2, gaps: list[str] | None = None) -> Outcome:
    plan = build_plan(query, depth=2, max_sources=5)
    plan.sub_queries = [query]
    return Outcome(
        query=query,
        plan=plan,
        findings=[
            Finding(text=f"Fundstelle {i} zu {query}", sources=[f"https://example.com/{i}"],
                    query=query)
            for i in range(findings)
        ],
        sources=[{"url": f"https://example.com/{i}", "title": f"Quelle {i}", "relevance": 0.5}
                 for i in range(findings)],
        gaps=gaps or [],
        rounds_run=1,
        pages_read=findings,
    )


@pytest.fixture
def patch_orchestrator(monkeypatch):
    def apply(outcome: Outcome):
        monkeypatch.setattr(
            "scout.research.orchestrator.run_research",
            lambda *a, **k: outcome,
        )

    return apply


def test_auto_mode_returns_findings_and_saves(patch_orchestrator):
    patch_orchestrator(_outcome("Docker buildkit cache mounts"))
    raw = research_start({"query": "Docker buildkit cache mounts", "mode": "auto"})
    payload = json.loads(raw)
    assert payload.get("error") is None, payload
    assert payload["mode"] == "auto"
    assert payload["gaps"] == []
    assert payload["findings_count"] == 2
    assert payload["sources_count"] == 2
    assert "Synthetisiere" in payload["instruction"]


def test_auto_mode_marks_partial_when_gaps(patch_orchestrator):
    patch_orchestrator(_outcome("Postgres Indizes", gaps=["keine Fundstelle fuer Teilfrage: X"]))
    payload = json.loads(research_start({"query": "Postgres Indizes", "mode": "auto"}))
    assert payload["result"]["status"] == "partial"
    assert payload["gaps"]


def test_auto_mode_reports_empty_result_as_error(patch_orchestrator):
    patch_orchestrator(_outcome("Nichts zu finden hier", findings=0))
    payload = json.loads(research_start({"query": "Nichts zu finden hier", "mode": "auto"}))
    assert payload.get("status") == "error"
    assert "ohne Fundstelle" in payload.get("error", "")


def test_auto_mode_survives_exception(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("firecrawl down")

    monkeypatch.setattr("scout.research.orchestrator.run_research", boom)
    payload = json.loads(research_start({"query": "irgendeine Frage", "mode": "auto"}))
    assert payload.get("status") == "error"
    assert "firecrawl down" in payload.get("error", "")


def test_plan_mode_is_default_and_does_not_search(patch_orchestrator):
    called = {"n": 0}

    def spy(*args, **kwargs):
        called["n"] += 1
        return _outcome("Frage")

    patch_orchestrator(None)
    import scout.research.orchestrator as orch

    original = orch.run_research
    orch.run_research = spy
    try:
        payload = json.loads(research_start({"query": "Frage mit Substanz"}))
    finally:
        orch.run_research = original

    assert payload["status"] == "planned"
    assert called["n"] == 0


def test_schedule_is_registered_and_reported_as_due():
    payload = json.loads(research_start({
        "query": "Wiederkehrende Frage zum Monitoring",
        "schedule": "24h",
    }))
    assert payload["status"] == "planned"

    due = due_schedules()
    assert any(d["query"].startswith("Wiederkehrende Frage") for d in due), due


def test_status_reports_due_schedules():
    research_start({"query": "Statusfrage mit Intervall", "schedule": "1h"})
    payload = json.loads(research_status({"show_orphans": True}))
    assert "schedules_due" in payload
    assert any("Statusfrage" in (d.get("query") or "") for d in payload["schedules_due"])
