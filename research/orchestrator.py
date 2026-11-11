"""Fuehrt eine Recherche aus: suchen, lesen, extrahieren, Luecken nachfassen.

Der Orchestrator liefert *Material* (Fundstellen mit Quellenbezug), keine
Prosa-Zusammenfassung. Die Synthese bleibt beim Modell — es sieht die
Fundstellen und kann sie gewichten, statt eine vorformatierte Meinung zu
uebernehmen.
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from .fetcher import Fetcher, Page, SearchHit
from .planner import ResearchPlan, build_plan

logger = logging.getLogger(__name__)

MAX_WORKERS = 6
MIN_CONTENT_CHARS = 200
SENTENCE_MAX_CHARS = 400
FINDINGS_PER_PAGE = 4


@dataclass
class Finding:
    """Eine Fundstelle mit Quellenbezug."""

    text: str
    sources: list[str] = field(default_factory=list)
    query: str = ""

    def as_dict(self) -> dict:
        return {"finding": self.text, "sources": list(self.sources), "query": self.query}


@dataclass
class Outcome:
    """Ergebnis eines Recherche-Laufs."""

    query: str
    plan: ResearchPlan
    findings: list[Finding] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    rounds_run: int = 0
    pages_read: int = 0
    pages_failed: int = 0
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and bool(self.findings)

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "findings": [f.as_dict() for f in self.findings],
            "sources": list(self.sources),
            "gaps": list(self.gaps),
            "rounds_run": self.rounds_run,
            "pages_read": self.pages_read,
            "pages_failed": self.pages_failed,
            "error": self.error,
        }


def _terms(text: str) -> set[str]:
    """Inhaltswoerter fuer den Relevanzvergleich (bewusst simpel, kein NLP)."""
    stop = {
        "der", "die", "das", "und", "oder", "ist", "sind", "ein", "eine", "für",
        "the", "and", "or", "is", "are", "a", "an", "to", "of", "in", "on", "for",
        "mit", "von", "bei", "wie", "was", "wer", "wann", "wo", "im", "den",
    }
    words = re.findall(r"[A-Za-zÄÖÜäöüß][\wäöüß-]{2,}", text.lower())
    return {w for w in words if w not in stop}


#: Navigation, Cookie-Hinweise und Call-to-Actions sind keine Fundstellen.
BOILERPLATE = (
    "learn more", "read more", "skip to", "cookie", "privacy policy",
    "subscribe", "sign in", "log in", "newsletter", "share this",
    "click here", "all rights reserved", "javascript is disabled",
    "we use cookies", "accept all", "follow us",
)


def _is_boilerplate(sentence: str) -> bool:
    """True fuer Navigations-/Werbetext, der inhaltlich nichts beitraegt."""
    lowered = sentence.lower()
    if any(phrase in lowered for phrase in BOILERPLATE):
        return True
    letters = sum(ch.isalpha() for ch in sentence)
    if letters == 0:
        return True
    # Viele Klammern/Doppelpunkte deuten auf Menue- oder Breadcrumb-Reste
    noise = sum(sentence.count(ch) for ch in "[]{}()|/\\:•→»")
    return noise / max(1, len(sentence)) > 0.08


def _sentences(content: str) -> list[str]:
    """Zerlegt Markdown/Text grob in Saetze und wirft Navigation weg."""
    cleaned = re.sub(r"```.*?```", " ", content, flags=re.S)
    cleaned = re.sub(r"[#*_>`|-]{1,}", " ", cleaned)
    cleaned = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", cleaned)
    parts = re.split(r"(?<=[.!?])\s+|\n{2,}", cleaned)
    out = []
    for part in parts:
        text = re.sub(r"\s+", " ", part).strip()
        if not 40 <= len(text) <= SENTENCE_MAX_CHARS:
            continue
        if _is_boilerplate(text):
            continue
        out.append(text)
    return out


def extract_findings(page: Page, query: str, limit: int = FINDINGS_PER_PAGE) -> list[Finding]:
    """Zieht die relevantesten Saetze einer Seite zur Frage heraus."""
    if not page.content:
        return []

    wanted = _terms(query)
    if not wanted:
        return []

    scored: list[tuple[float, str]] = []
    for sentence in _sentences(page.content):
        overlap = wanted & _terms(sentence)
        if not overlap:
            continue
        # Anteil abgedeckter Fragebegriffe, leicht belohnt fuer laengere Ueberlappung
        score = len(overlap) / len(wanted) + 0.05 * len(overlap)
        scored.append((score, sentence))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        Finding(text=text, sources=[page.url], query=query)
        for _score, text in scored[:limit]
    ]


def _merge_findings(existing: list[Finding], new: list[Finding]) -> None:
    """Fuegt Fundstellen zusammen und dedupliziert nach Textanfang."""
    seen = {f.text[:80].lower() for f in existing}
    for finding in new:
        key = finding.text[:80].lower()
        if key in seen:
            # gleiche Aussage: Quelle ergaenzen statt Dublette anlegen
            for known in existing:
                if known.text[:80].lower() == key:
                    known.sources.extend(
                        url for url in finding.sources if url not in known.sources
                    )
                    break
            continue
        seen.add(key)
        existing.append(finding)


def _search_round(
    fetcher: Fetcher,
    queries: list[str],
    per_query_limit: int,
    outcome: Outcome,
) -> list[SearchHit]:
    """Sucht alle Teilfragen und sammelt eindeutige Treffer."""
    hits: list[SearchHit] = []
    seen: set[str] = set()
    for query in queries:
        for hit in fetcher.search(query, limit=per_query_limit):
            if hit.url in seen:
                continue
            seen.add(hit.url)
            hits.append(hit)
    return hits


def _read_pages(fetcher: Fetcher, hits: list[SearchHit], outcome: Outcome) -> list[Page]:
    """Laedt Treffer parallel und extrahiert Fundstellen."""
    pages: list[Page] = []
    if not hits:
        return pages

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetcher.scrape, hit.url): hit for hit in hits}
        for future in as_completed(futures):
            try:
                page = future.result()
            except Exception as exc:  # noqa: BLE001 - ein kaputter Scrape stoppt nicht alles
                logger.warning("scrape fehlgeschlagen: %s", exc)
                outcome.pages_failed += 1
                continue
            if page.ok and len(page.content) >= MIN_CONTENT_CHARS:
                pages.append(page)
                outcome.pages_read += 1
            else:
                outcome.pages_failed += 1
    return pages


def run_research(
    query: str,
    depth: int = 3,
    max_sources: int = 10,
    fetcher: Fetcher | None = None,
    plan: ResearchPlan | None = None,
) -> Outcome:
    """Fuehrt die Recherche aus.

    depth>=4 plant eine zweite Runde ein, die gezielt die Luecken der ersten
    Runde nachfasst (Teilfragen ohne Treffer, zu wenige Quellen).
    """
    fetcher = fetcher or Fetcher()
    plan = plan or build_plan(query, depth=depth, max_sources=max_sources)
    outcome = Outcome(query=plan.query, plan=plan)

    hits = _search_round(fetcher, plan.sub_queries, plan.per_query_limit, outcome)
    if not hits:
        outcome.error = "keine Suchtreffer (Firecrawl nicht erreichbar oder leere Suche)"
        outcome.gaps = list(plan.sub_queries)
        return outcome

    pages = _read_pages(fetcher, hits[: max_sources * 2], outcome)
    for page in pages:
        _merge_findings(outcome.findings, extract_findings(page, plan.query))

    outcome.sources = [
        {"url": page.url, "title": page.title, "relevance": 0.5}
        for page in pages
    ]

    # Teilfragen ohne Fundstelle sind eine Luecke
    covered = {s["url"] for s in outcome.sources}
    for sub_query in plan.sub_queries:
        if not any(sub_query.lower() in f.query.lower() for f in outcome.findings):
            outcome.gaps.append(f"keine Fundstelle fuer Teilfrage: {sub_query}")

    outcome.rounds_run = 1

    # Zweite Runde: gezielt Luecken nachfassen
    if plan.rounds > 1 and outcome.gaps:
        gap_queries = [g.split(": ", 1)[-1] for g in outcome.gaps if ": " in g][:3]
        if gap_queries:
            extra_hits = _search_round(fetcher, gap_queries, plan.per_query_limit, outcome)
            extra_hits = [h for h in extra_hits if h.url not in covered]
            extra_pages = _read_pages(fetcher, extra_hits[: max_sources], outcome)
            for page in extra_pages:
                _merge_findings(outcome.findings, extract_findings(page, plan.query))
                outcome.sources.append(
                    {"url": page.url, "title": page.title, "relevance": 0.5}
                )
            outcome.rounds_run = 2

    if not outcome.findings:
        outcome.error = "Seiten gelesen, aber keine relevante Fundstelle extrahiert"
    return outcome
