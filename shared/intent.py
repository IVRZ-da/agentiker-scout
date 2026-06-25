"""Shared intent detection — single pre_llm_call hook for all 3 domains.

Fasst die Keyword-Detection aus analysis (intent_helpers.py),
bughunt (bughunt_hooks.py pre_llm_call) und deep-research (research_hooks.py pre_llm_call)
zusammen. Vermeidet 3× Hook-Overhead + dedupliziert Keywords.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

logger = logging.getLogger("scout.intent")

# ─── TTL-Cache (shared) ───────────────────────────────────────────────────

_INTENT_CACHE: dict[str, tuple[float, str | None]] = {}
_CACHE_TTL = 60.0  # 60 seconds

# ─── Domain-Keywords (dedupliziert!) ─────────────────────────────────────

# Vorher: analysis + bughunt hatten 4 Overlaps (bug, analyse, untersuch, problem)
# Jetzt: klare Trennung, Domain mit höherer Spezifität gewinnt bei Overlap

INTENT_MAP: dict[str, set[str]] = {
    "code": {
        "analysier", "untersuch", "code", "struktur", "architektur",
        "dependency", "abhängigkeit", "zirkulär", "hot path",
        "performance", "bottleneck", "langsam", "komplexität",
        "analyze", "architecture", "structure", "dependency",
        "circular", "hot path", "performance", "complexity",
    },
    "bug": {
        "bug", "fehler", "error", "exception", "crash", "absturz",
        "stacktrace", "trace", "debug", "debugge", "fix",
        "security", "vulnerability", "sicherheitslücke",
        "audit", "scan", "lint", "warnung", "warning",
        "regression", "defekt",
    },
    "research": {
        "recherchier", "research", "find heraus", "find out",
        "extrahiere", "extract", "suche", "search", "look up",
        "vergleiche", "compare", "markt", "market", "competitor",
        "wettbewerb", "analyse zu", "gründlich", "thorough",
        "hintergrund", "background", "zusammenfassung", "summary",
    },
    "db": {
        "datenbank", "database", "query", "sql", "postgres",
        "schema", "table", "index", "performance",
    },
    "web": {
        "api", "docs", "dokumentation", "dokumentation",
        "website", "homepage", "url", "endpoint",
    },
    "framework": {
        "framework", "techstack", "stack", "technologie",
        "technologie-stack", "technology", "erkenne", "detect",
        "welche technologien", "was wird verwendet",
        "project profile", "project analysis",
    },
}

# Reverse-Map: Keyword → Domain (für schnellen Lookup)
_KEYWORD_TO_DOMAIN: dict[str, str] = {}
for domain, keywords in INTENT_MAP.items():
    for kw in keywords:
        _KEYWORD_TO_DOMAIN[kw] = domain

# ─── Intent Context Builder ─────────────────────────────────────────────

_INTENT_CONTEXTS: dict[str, str] = {
    "code": (
        "[SCOUT] Analyse-Intent erkannt. Verfügbare Tools:\n"
        "- analysis_inspect(path, depth=1-5) — mehrstufige Code-Analyse\n"
        "- analysis_architecture(path) — Abhängigkeitsgraph + Zyklen\n"
        "- analysis_deadcode(path) — unused imports/functions/errors\n"
        "- analysis_performance(path) — Complexity-Hotspots\n"
        "- analysis_security(path) — Security-Pattern-Scan\n"
        "- analysis_ask(question) — KI-gestützte Code-Frage\n"
        "- analysis_report(scope, findings) — Ergebnisse persistieren"
    ),
    "bug": (
        "[SCOUT] Bug-Hunt-Intent erkannt. Verfügbare Tools:\n"
        "- bug_hunt_start(project) — Session starten\n"
        "- bug_hunt_scan(patterns) — Automatische grep-Scans\n"
        "- bug_hunt_finding(title, severity) — Finding erfassen\n"
        "- bug_hunt_fix(session_id, finding_id) — Auto-Fix via Subagent\n"
        "- bug_hunt_report(format) — Report generieren\n"
        "- bug_hunt_pattern(list|save) — Pattern-Bibliothek"
    ),
    "research": (
        "[SCOUT] Research-Intent erkannt. Verfügbare Tools:\n"
        "- research_start(query, depth, pattern) — Recherche starten\n"
        "- research_save(id, summary, findings) — Ergebnisse speichern\n"
        "- research_search(query) — Lokale Recherchen durchsuchen\n"
        "- research_compare(ids) — Recherchen vergleichen\n"
        "- research_synthesize(query) — Honcho-Synthese\n"
        "- research_schedule(query, interval) — Periodische Recherche"
    ),
    "db": (
        "[SCOUT] Datenbank-Intent erkannt. Nutze PostgreSQL MCP Tools:\n"
        "- execute_sql(sql) — Read-Only Queries\n"
        "- explain_query(sql) — Execution Plan\n"
        "- get_object_details(schema, table) — Schema-Info\n"
        "- list_objects(schema) — Tabellen auflisten"
    ),
    "web": (
        "[SCOUT] Web-Recherche-Intent erkannt. Nutze Firecrawl:\n"
        "- firecrawl_search(query, limit) — Web-Suche\n"
        "- firecrawl_scrape(url) — Seite extrahieren\n"
        "- firecrawl_extract(urls, prompt) — Strukturierte Extraktion"
    ),
    "framework": (
        "[SCOUT] Framework-Analyse-Intent erkannt. Verfügbare Tools:\n"
        "- analysis_framework(path) — Framework-Profil anzeigen\n"
        "- bug_hunt_scan(patterns, frameworks=...) — Framework-spezifischer Scan\n"
        "- bug_hunt_scan(preset='medusa-full') — Preset-Scan für erkannten Stack"
    ),
}

# ─── Intent Detection (Single pre_llm_call) ──────────────────────────────

_DOMAIN_PRIORITY = ["bug", "research", "framework", "db", "web", "code"]
_DOMAIN_PRIORITY_WEIGHTS = {"bug": 10, "research": 8, "framework": 7, "db": 6, "web": 4, "code": 2}

def _detect_intent(message: str) -> str | None:
    """Detect which domain(s) a message belongs to. Returns most specific domain.

    Bei Mehrfachmatches (z.B. "analysiere den bug" → code + bug) gewinnt
    die spezifischere Domain (bug > code, research > code).
    """
    msg_lower = message.lower()
    matched_domains: list[tuple[str, int]] = []

    for domain, keywords in INTENT_MAP.items():
        for kw in keywords:
            if kw in msg_lower:
                score = _DOMAIN_PRIORITY_WEIGHTS.get(domain, 1)
                matched_domains.append((domain, score))
                break  # Ein Keyword pro Domain reicht

    if not matched_domains:
        return None

    # Sort by priority (highest score wins)
    matched_domains.sort(key=lambda x: x[1], reverse=True)
    return matched_domains[0][0]

def _build_intent_context(domain: str) -> str | None:
    """Return cached context for a detected domain."""
    now = time.monotonic()
    cached = _INTENT_CACHE.get(domain)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    context = _INTENT_CONTEXTS.get(domain)
    _INTENT_CACHE[domain] = (now, context)
    return context

def on_pre_llm_call(**kwargs: Any) -> Optional[str]:
    """Single pre_llm_call hook — detects intent across all 3 domains.

    Replaces 3 separate hooks from analysis, bughunt, and deep-research.
    Returns tool recommendations if a domain intent is detected.
    """
    messages = kwargs.get("messages", [])
    if not messages:
        return None

    # Find the last user message
    last_user_msg = None
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    if not last_user_msg:
        return None

    # Quick gate: if no relevant keywords, skip everything
    msg_lower = last_user_msg.lower()
    has_relevant_keyword = False
    for domain_kws in INTENT_MAP.values():
        for kw in domain_kws:
            if kw in msg_lower:
                has_relevant_keyword = True
                break
        if has_relevant_keyword:
            break

    if not has_relevant_keyword:
        return None

    domain = _detect_intent(last_user_msg)
    if not domain:
        return None

    context = _build_intent_context(domain)
    if context:
        logger.debug("scout: injected %s context", domain)
    return context
