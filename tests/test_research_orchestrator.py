"""Recherche-Orchestrierung ohne Netzwerk: Planer, Fetcher-Degradation, Extraktion.

Der Orchestrator muss auch dann sinnvoll antworten, wenn Firecrawl nicht
erreichbar ist — eine Recherche darf nicht mit einem Stacktrace enden.
"""
from __future__ import annotations

import pytest

from scout.research.fetcher import Fetcher, Page, SearchHit
from scout.research.orchestrator import _is_boilerplate, extract_findings, run_research
from scout.research.planner import MAX_SUB_QUERIES, build_plan

# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

def test_plan_minimal_depth_has_only_the_question():
    plan = build_plan("Wann wurde Medusa v2 veroeffentlicht?", depth=1)
    assert plan.sub_queries == ["Wann wurde Medusa v2 veroeffentlicht?"]
    assert plan.rounds == 1


def test_plan_depth_clamped():
    assert build_plan("x", depth=99).depth == 5
    assert build_plan("x", depth=0).depth == 1


def test_plan_strips_filler():
    plan = build_plan("bitte recherchiere Docker buildkit cache mounts", depth=1)
    assert not plan.sub_queries[0].lower().startswith("bitte")
    assert "Docker buildkit cache mounts" in plan.sub_queries[0]


def test_plan_adds_variants_with_depth():
    plan = build_plan("Next.js caching", depth=3)
    assert len(plan.sub_queries) >= 2
    assert len(plan.sub_queries) <= MAX_SUB_QUERIES


def test_plan_splits_compound_question():
    plan = build_plan("Vergleiche SQLite und PostgreSQL fuer Metriken", depth=3)
    joined = " ".join(plan.sub_queries).lower()
    assert "sqlite" in joined and "postgresql" in joined
    assert plan.needs_compare is True


def test_plan_detects_explanation_question():
    assert build_plan("Warum ist HTTP/3 schneller?", depth=2).needs_explanation is True


def test_plan_rounds_for_deep_research():
    assert build_plan("irgendwas wichtiges hier", depth=4).rounds == 2


def test_plan_budget_split():
    plan = build_plan("Frage zu mehreren Dingen und Themen", depth=3, max_sources=20)
    assert 3 <= plan.per_query_limit <= 10


def test_plan_serialisable():
    data = build_plan("Testfrage mit Substanz", depth=2).as_dict()
    assert set(data) >= {"query", "sub_queries", "rounds", "per_query_limit"}


# ---------------------------------------------------------------------------
# Fetcher-Degradation
# ---------------------------------------------------------------------------

def test_fetcher_returns_empty_on_unreachable_host():
    fetcher = Fetcher(base_url="http://127.0.0.1:9", timeout=0.2, retries=0)
    assert fetcher.search("egal", limit=3) == []
    assert fetcher.scrape("http://127.0.0.1:9/x").ok is False


def test_fetcher_uses_injected_functions():
    fetcher = Fetcher(
        search_fn=lambda q, n: [SearchHit(url="https://example.com/a", title="A")],
        scrape_fn=lambda url: Page(url=url, title="A", content="Inhalt " * 60, status=200),
    )
    hits = fetcher.search("frage", limit=2)
    assert hits[0].url == "https://example.com/a"
    assert fetcher.scrape("https://example.com/a").ok is True


# ---------------------------------------------------------------------------
# Extraktion
# ---------------------------------------------------------------------------

def test_extract_findings_picks_relevant_sentences():
    page = Page(
        url="https://example.com/x",
        content=(
            "Next.js cached fetch requests per default in Version 15. "
            "Die Farbe der Seite ist blau und gruen. "
            "In Version 16 ist Caching explizit opt-in und muss aktiviert werden."
        ),
        status=200,
    )
    findings = extract_findings(page, "Next.js caching defaults Version")
    assert findings
    assert all(f.sources == ["https://example.com/x"] for f in findings)
    assert any("cached" in f.text.lower() or "opt-in" in f.text.lower() for f in findings)


def test_extract_findings_skips_irrelevant_page():
    page = Page(url="https://example.com/y", content="Nur ueber Gaertnern und Pflanzen. " * 10)
    assert extract_findings(page, "Docker Buildkit cache mounts") == []


def test_extract_findings_handles_empty_content():
    assert extract_findings(Page(url="https://example.com/z", content=""), "irgendwas") == []


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def _fake_fetcher(pages_by_url: dict, hits: list[SearchHit], searches: list):
    def search_fn(query, limit):
        searches.append(query)
        return hits[:limit]

    def scrape_fn(url):
        if url in pages_by_url:
            return pages_by_url[url]
        return Page(url=url, error="404")

    return Fetcher(search_fn=search_fn, scrape_fn=scrape_fn)


def test_run_research_happy_path():
    body = ("Docker buildkit cache mounts beschleunigen npm ci erheblich, weil das "
            "Layer-Caching erhalten bleibt. " * 6)
    fetcher = _fake_fetcher(
        {"https://example.com/a": Page(url="https://example.com/a", title="A", content=body, status=200)},
        [SearchHit(url="https://example.com/a", title="A")],
        [],
    )
    outcome = run_research("Docker buildkit cache mounts", depth=2, max_sources=5, fetcher=fetcher)
    assert outcome.ok, outcome.error
    assert outcome.findings
    assert outcome.sources
    assert outcome.pages_read == 1


def test_run_research_without_hits_reports_gap():
    fetcher = _fake_fetcher({}, [], [])
    outcome = run_research("irgendeine Frage", depth=1, fetcher=fetcher)
    assert outcome.ok is False
    assert "keine Suchtreffer" in outcome.error
    assert outcome.gaps


def test_run_research_survives_failing_scrape():
    body = ("Buildkit cache mounts halten Abhaengigkeiten zwischen Builds im Cache. " * 6)
    pages = {"https://example.com/gut": Page(url="https://example.com/gut", content=body, status=200)}
    fetcher = _fake_fetcher(
        pages,
        [SearchHit(url="https://example.com/gut"), SearchHit(url="https://example.com/kaputt")],
        [],
    )
    outcome = run_research("Buildkit cache mounts", depth=1, max_sources=5, fetcher=fetcher)
    assert outcome.ok
    assert outcome.pages_failed >= 1


def test_run_research_second_round_fills_gaps():
    body = ("Postgres Indizes beschleunigen Abfragen mit vielen Zeilen deutlich. " * 6)
    pages = {"https://example.com/pg": Page(url="https://example.com/pg", content=body, status=200)}
    searches: list[str] = []
    fetcher = _fake_fetcher(pages, [SearchHit(url="https://example.com/pg")], searches)
    outcome = run_research("Postgres Indizes Performance Vergleich", depth=4, fetcher=fetcher)
    assert outcome.rounds_run in (1, 2)
    # depth>=4 plant zwei Runden; ob die zweite greift, haengt von den Luecken ab
    assert len(searches) >= len(outcome.plan.sub_queries)


def test_outcome_serialisable():
    fetcher = _fake_fetcher({}, [], [])
    data = run_research("leere Frage hier", depth=1, fetcher=fetcher).as_dict()
    assert set(data) >= {"query", "findings", "sources", "gaps", "error"}


@pytest.mark.parametrize("depth", [1, 2, 3, 4, 5])
def test_all_depths_run(depth):
    body = ("Ein Satz mit ausreichend Inhalt zur Frage nach dem Thema hier. " * 8)
    pages = {"https://example.com/d": Page(url="https://example.com/d", content=body, status=200)}
    fetcher = _fake_fetcher(pages, [SearchHit(url="https://example.com/d")], [])
    outcome = run_research("Frage nach dem Thema", depth=depth, fetcher=fetcher)
    assert outcome.rounds_run >= 1


# ---------------------------------------------------------------------------
# Boilerplate-Filter
# ---------------------------------------------------------------------------

def test_boilerplate_navigation_is_filtered():
    page = Page(
        url="https://example.com/nav",
        content=(
            "Learn more about our caching approach here and subscribe to the newsletter. "
            "Next.js cached fetch requests per default in Version 15 und das ist relevant. "
            "Skip to content or accept all cookies before you continue reading this page."
        ),
        status=200,
    )
    findings = extract_findings(page, "Next.js caching defaults")
    assert findings
    joined = " ".join(f.text.lower() for f in findings)
    assert "learn more" not in joined
    assert "skip to content" not in joined
    assert "cached fetch" in joined


@pytest.mark.parametrize("sentence", [
    "Learn more about our product",
    "We use cookies to improve your experience",
    "All rights reserved by Example Inc",
    "[Home](/) | [Blog](/blog) | [Contact](/contact) | [About](/about)",
    "}}}",
])
def test_boilerplate_detector(sentence):
    assert _is_boilerplate(sentence) is True


@pytest.mark.parametrize("sentence", [
    "Next.js cached fetch requests per default in Version 15.",
    "Docker buildkit cache mounts beschleunigen npm ci erheblich.",
])
def test_real_content_is_not_boilerplate(sentence):
    assert _is_boilerplate(sentence) is False
