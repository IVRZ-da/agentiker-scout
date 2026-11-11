"""Planung einer Recherche: Frage zerlegen, Budget verteilen, Runden festlegen.

Bewusst ohne LLM und ohne IO — reine Funktionen, damit die Planung
deterministisch testbar bleibt. Die eigentliche Arbeit macht der Orchestrator.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Fragewoerter, die auf eine erklaerende Antwort deuten (vs. einer Faktenliste).
EXPLAIN_HINTS = ("warum", "wieso", "weshalb", "how does", "why", "erklaer", "erklär")

#: Vergleichs-/Entscheidungsfragen brauchen mehr Quellen als Faktenfragen.
COMPARE_HINTS = ("vs", "versus", "vergleich", "compare", "unterschied", "besser", "statt")

#: Hoechstzahl Teilfragen — mehr bringt bei den meisten Fragen keinen Gewinn.
MAX_SUB_QUERIES = 5


@dataclass
class ResearchPlan:
    """Ergebnis der Planung."""

    query: str
    depth: int
    max_sources: int
    sub_queries: list[str] = field(default_factory=list)
    rounds: int = 1
    per_query_limit: int = 5
    needs_compare: bool = False
    needs_explanation: bool = False

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "depth": self.depth,
            "max_sources": self.max_sources,
            "sub_queries": list(self.sub_queries),
            "rounds": self.rounds,
            "per_query_limit": self.per_query_limit,
            "needs_compare": self.needs_compare,
            "needs_explanation": self.needs_explanation,
        }


def _normalise(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip()


def _strip_filler(query: str) -> str:
    """Entfernt Hoeflichkeitsfloskeln, die die Suche nur verwässern."""
    filler = (
        "bitte ", "kannst du ", "könntest du ", "kannst du mir ", "ich möchte ",
        "ich moechte ", "please ", "could you ", "would you ", "finde heraus ",
        "recherchiere ", "recherchiere zu ", "suche nach ", "research ",
    )
    out = query
    lowered = out.lower()
    for prefix in filler:
        if lowered.startswith(prefix):
            out = out[len(prefix):]
            lowered = out.lower()
    return out.strip()


def _split_topics(query: str) -> list[str]:
    """Zerlegt an Konjunktionen/Aufzaehlungen — aber nur wenn es echte Teile gibt."""
    parts = re.split(r"\s+(?:und|and|sowie|plus)\s+|;\s*|\s+\+\s+", query, flags=re.I)
    return [p.strip(" ,.") for p in parts if len(p.strip()) > 8]


def _year_hint(query: str) -> str | None:
    years = re.findall(r"\b(19|20)\d{2}\b", query)
    return years[-1] if years else None


def build_plan(query: str, depth: int = 3, max_sources: int = 10) -> ResearchPlan:
    """Erzeugt einen Rechercheplan.

    depth 1 = nur die Frage selbst, 3 = Frage + Varianten, 5 = zusaetzlich
    Teilthemen und eine Nachfassrunde.
    """
    query = _normalise(query)
    depth = max(1, min(5, int(depth)))
    max_sources = max(1, min(50, int(max_sources)))

    core = _strip_filler(query)
    lowered = core.lower()

    plan = ResearchPlan(
        query=core,
        depth=depth,
        max_sources=max_sources,
        needs_compare=any(h in lowered for h in COMPARE_HINTS),
        needs_explanation=any(h in lowered for h in EXPLAIN_HINTS),
    )

    subs = [core]

    if depth >= 2:
        # Eine praezisere Variante hilft bei vagen Fragen ("X caching").
        if len(core.split()) <= 4:
            subs.append(f"{core} best practices")

    if depth >= 3:
        topics = _split_topics(core)
        if len(topics) > 1:
            subs.extend(topics)
        year = _year_hint(core)
        if year is None and len(core.split()) > 2:
            subs.append(f"{core} 2026")

    if depth >= 4:
        subs.append(f"{core} limitations OR problems")
        if plan.needs_compare:
            subs.append(f"{core} benchmark")

    # Duplikate entfernen, Reihenfolge erhalten
    seen: set[str] = set()
    unique: list[str] = []
    for item in subs:
        key = item.lower()
        if key not in seen and len(item) >= 3:
            seen.add(key)
            unique.append(item)

    plan.sub_queries = unique[:MAX_SUB_QUERIES]

    # Runden: bei depth>=4 wird eine Nachfassrunde fuer Luecken eingeplant.
    plan.rounds = 2 if depth >= 4 else 1

    # Budget pro Teilfrage so verteilen, dass die Gesamtzahl nicht explodiert.
    plan.per_query_limit = max(3, min(10, -(-max_sources // max(1, len(plan.sub_queries)))))

    return plan
