"""intent_helpers — Helfer für Intent-Erkennung (genutzt von analysis_core.py).

Enthält _extract_file_refs, _is_analysis_query, _build_tool_recommendations
und _query_honcho_analysis_history, die in shared/intent.py nicht existieren.

Der pre_llm_call Hook lebt in shared/intent.py — diese Datei ist nur Helper."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger("analysis")


# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

# Keywords für Analyse-Erkennung (erweiterbar via Umgebungsvariable)
DEFAULT_ANALYSIS_KEYWORDS: List[str] = [
    # Deutsch
    "analysier", "untersuch", "debugg", "warum", "wieso",
    "recherchier", "vergleich", "find.*heraus", "was macht",
    "ist los", "problem", "fehler", "fehlt", "performance",
    "bottleneck", "hängt", "langsam", "absturz", "crash",
    "trace", "stacktrace", "log", "exception", "error",
    "warning", "deprecated", "architektur", "struktur",
    "abhängigkeit", "dependency", "modul", "schicht", "layer",
    "pattern", "workflow", "pipeline", "data flow", "datenfluss",
    "zirkulär", "cycle", "import chain",
    "dead code", "unused", "obsolet", "toter code",
    "refactoring", "umbau", "modernisier", "optimier", "verbesser",
    "code review", "pull request", "diff", "änderung", "change",
    "security", "sicherheit", "angriff", "vulnerability",
    "datenbank", "query", "sql", "index",
    # Englisch
    "analyze", "investigate", "debug", "examine",
    "research", "compare", "find out", "what does",
    "what is", "problem", "error", "bug", "performance",
    "slow", "crash", "trace", "stack.?trace",
    "architecture", "structure", "dependency",
    "module", "layer", "pattern", "workflow",
    "circular", "dead code", "unused", "obsolete",
    "refactor", "optimize", "improve",
    "code review", "pull request", "diff",
    "security", "vulnerability",
    "database", "query",
    # Datei-bezogen
    "zeig.*mir", "show.*me", "erklär", "explain",
    "übersicht", "overview", "zusammenfassung", "summary",
]

# Tools die als analyse-relevant markiert sind
ANALYSIS_TOOLS: Set[str] = {
    # code-intel AST
    "code_symbols", "code_search", "code_capsule",
    "code_callers", "code_callees", "code_highlight",
    "code_complexity", "code_search_by_error", "code_hot_paths",
    "code_cycle_detector", "code_dependency_graph",
    "code_blast_radius", "code_pr_impact",
    "code_tests_for_symbol", "code_unused_finder",
    "code_overview", "code_workspace_summary",
    "code_impact", "code_query", "code_document_symbols",
    # code-intel LSP
    "code_definition", "code_references", "code_diagnostics",
    "code_hover", "code_workspace_symbols",
    "code_call_hierarchy", "code_type_hierarchy",
    "code_type_definition", "code_inlay_hints",
    "code_implementations", "code_signatures",
    # code-intel Refactoring
    "code_refactor", "code_rename", "code_action",
    "code_format", "code_replace_body", "code_safe_delete",
    "code_insert_before", "code_insert_after",
    # Firecrawl
    "firecrawl_search", "firecrawl_scrape", "firecrawl_extract",
    "firecrawl_agent", "firecrawl_map",
    # PostgreSQL MCP
    "execute_sql", "get_object_details", "analyze_db_health",
    "list_schemas", "list_objects", "explain_query",
    # Honcho
    "honcho_search", "honcho_profile", "honcho_reasoning",
    "honcho_context", "honcho_conclude",
    # Builtins
    "web_search", "web_extract",
    # Analysis Plugin eigene Tools
    "analysis_performance", "analysis_security", "analysis_ask",
}

# Cache-TTL für Honcho-Suche
_HONCHO_CACHE_TTL = 60  # Sekunden

# Cache-Datei für Cross-Session-Persistenz

_HONCHO_CACHE_FILE = str(Path(__file__).resolve().parent / ".honcho_cache.json")

# Cache für _query_honcho_analysis_history
_honcho_cache: Dict[str, tuple[str, float]] = {}


# ---------------------------------------------------------------------------
# Cross-Session-Cache Persistenz
# ---------------------------------------------------------------------------


def _load_honcho_cache() -> None:
    """Lädt den Honcho-Cache aus JSON-Datei (Cross-Session)."""
    global _honcho_cache
    try:
        cache_path = Path(_HONCHO_CACHE_FILE)
        if cache_path.exists():
            import json as _json
            raw = _json.loads(cache_path.read_text())
            if isinstance(raw, dict):
                # In-place update statt reassignment (Import-Referenzen bleiben gültig)
                loaded = {}
                for k, v in raw.items():
                    if isinstance(v, list) and len(v) == 2:
                        loaded[k] = (str(v[0]), float(v[1]))
                _honcho_cache.clear()
                _honcho_cache.update(loaded)
                logger.debug("loaded %d honcho cache entries from %s", len(loaded), _HONCHO_CACHE_FILE)
    except Exception as e:
        logger.debug("honcho cache load skipped: %s", e)


def _save_honcho_cache() -> None:
    """Speichert den Honcho-Cache als JSON-Datei (Cross-Session)."""
    try:
        # Konvertiere Dict mit tuple-Werten zu JSON
        raw = {k: [v[0], v[1]] for k, v in _honcho_cache.items()}
        cache_path = Path(_HONCHO_CACHE_FILE)
        import json as _json
        cache_path.write_text(_json.dumps(raw, ensure_ascii=False))
    except Exception as e:
        logger.debug("honcho cache save skipped: %s", e)


# ---------------------------------------------------------------------------
# Intent Detection (Regex-basiert)
# ---------------------------------------------------------------------------

def _detect_intent(text: str) -> Optional[str]:
    """Ermittelt die Analyse-Intention aus dem Text.

    Returns:
        Intent-String oder None wenn keine Analyse erkannt.
    """
    import unicodedata
    if not text:
        return None
    # Unicode normalisieren (é → e) für robustes Matching
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    text_lower = text.lower()

    # Intentionen mit spezifischen Keywords
    intent_map = {
        "architecture": [
            "architektur", "struktur", "schicht", "layer",
            "architecture", "structure",
            "zirkulär", "cycle", "dependency.*graph",
            "abhängigkeit", "modul", "module",
            "workspace", "projektstruktur",
            "dependency", "circular",
        ],
        "deadcode": [
            "dead.code", "unused", "obsolet", "toter.code",
            "toten", "tote", "unnötig",
            "obsolete", "unused", "remove", "entfern", "lösch", "delete",
        ],
        "performance": [
            "performance", "bottleneck", "slow", "langsam",
            "optimier", "optimize", "latenz", "latency",
            "overhead", "cache", "speicher", "memory",
        ],
        "bug": [
            "bug", "error", "exception", "crash", "absturz",
            "fehler", "problem", "trace", "stacktrace",
            "log", "warning", "deprecated",
        ],
        "db": [
            "datenbank", "database", "query", "sql",
            "index", "table", "schema", "relation",
        ],
        "web": [
            "recherchier", "research", "search",
            "find.*out", "look.*up", "googl",
        ],
        "code": [
            "code", "funktion", "methode", "klasse",
            "function", "method", "class",
            "implementation", "implementierung",
            "code.*review", "pull.request", "diff",
        ],
    }

    # Score-basierte Erkennung
    scores: Dict[str, int] = {}
    for intent, keywords in intent_map.items():
        score = 0
        for kw in keywords:
            if re.search(kw, text_lower):
                score += 1
        if score > 0:
            scores[intent] = score

    if not scores:
        # Fallback: AI-gestützte Intent-Detection via Honcho Reasoning
        ai_intent = _ai_detect_intent(text_lower)
        if ai_intent:
            logger.debug("ai fallback detected intent=%s", ai_intent)
            return ai_intent
        return None

    # Höchsten Score nehmen
    best = max(scores, key=lambda k: scores.get(k) or 0)
    logger.debug("detected analysis intent=%s (scores=%s)", best, scores)
    return best


# ---------------------------------------------------------------------------
# AI-Intent-Detection (Fallback)
# ---------------------------------------------------------------------------

# Cache für AI-Intent-Erkennung
_ai_intent_cache: Dict[str, tuple] = {}
_AI_INTENT_CACHE_TTL = 300  # 5 Minuten


def _ai_detect_intent(text: str) -> Optional[str]:
    """KI-gestützte Intent-Detection als Fallback.

    Nutzt honcho_reasoning wenn Regex keine Intention gefunden hat.
    Gecached für 5 Minuten.
    """
    now = time.time()
    cache_key = hashlib.md5(text.encode()).hexdigest()[:16]
    cached = _ai_intent_cache.get(cache_key)
    if cached is not None:
        value, timestamp = cached
        if now - timestamp < _AI_INTENT_CACHE_TTL:
            return value if value else None
        del _ai_intent_cache[cache_key]

    try:
        from tools.registry import registry
        result = registry.dispatch("honcho_reasoning", {
            "query": f"Classify the intent of this user message into one of: "
                     f"code, architecture, deadcode, bug, performance, db, web. "
                     f"Message: '{text[:200]}'",
            "reasoning_level": "minimal",
        })
        if result:
            text_result = str(result).lower().strip()
            if text_result.startswith("{") or text_result.startswith("["):
                _ai_intent_cache[cache_key] = ("", now)
                return None
            for intent in ("architecture", "deadcode", "performance", "bug", "db", "web", "code"):
                if intent in text_result:
                    _ai_intent_cache[cache_key] = (intent, now)
                    return intent
        _ai_intent_cache[cache_key] = ("", now)
        return None
    except Exception as e:
        logger.warning("ai intent detection failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# File-Ref-Extraktion
# ---------------------------------------------------------------------------

_MAX_CONTEXT_FILES = 3


def _extract_file_refs(text: str) -> List[str]:
    """Extrahiert Datei-Referenzen aus dem Text."""
    refs = []
    patterns = [
        r'(?:^|[\s"\'`({])((?:@/|\./|/)?[\w/_.-]+\.(?:tsx|ts|jsx|js|py|rs|go|java|css|scss|md))',
        r'(?:^|[\s"\'`({])((?:@/|\./)?[\w/_.-]+/(?:[\w/_.-]+\.(?:tsx|ts|jsx|js|py|rs|go|java)))',
    ]
    for pat in patterns:
        found = re.findall(pat, text)
        refs.extend(found)
    return refs[:_MAX_CONTEXT_FILES]

# ---------------------------------------------------------------------------
# Analyse-Query-Prüfung
# ---------------------------------------------------------------------------

def _is_analysis_query(text: str) -> bool:
    """Prüft ob der Text eine Analyse-Anfrage ist."""
    import unicodedata
    if not text:
        return False
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")

    keywords_env = os.environ.get("ANALYSIS_KEYWORDS", "")
    if keywords_env:
        keywords = [kw.strip() for kw in keywords_env.split(",")]
    else:
        keywords = DEFAULT_ANALYSIS_KEYWORDS

    text_lower = text.lower()
    for kw in keywords:
        if re.search(kw, text_lower):
            logger.debug("analysis keyword matched: '%s'", kw)
            return True
    return False


# ---------------------------------------------------------------------------
# Tool-Empfehlungen
# ---------------------------------------------------------------------------

def _build_tool_recommendations(intent: str, file_refs: List[str]) -> str:
    """Baut Tool-Empfehlungen basierend auf Analyse-Intention."""
    parts = []

    intent_recommendations = {
        "code": [
            "code_symbols(path) — Datei-Struktur abrufen",
            "code_capsule(path, line) — Symbol-Überblick",
            "code_callers(path, line) — Wer ruft auf?",
            "code_call_hierarchy(path, line) — Aufruf-Hierarchie",
            "code_complexity(path) — Zyklomatische Komplexität",
            "code_diagnostics(path) — LSP-Fehler/Warnungen",
        ],
        "architecture": [
            "code_workspace_summary(path) — Projekt-Überblick",
            "code_dependency_graph(path) — Abhängigkeitsgraph",
            "code_cycle_detector(path) — Zirkuläre Imports",
        ],
        "deadcode": [
            "code_unused_finder(path) — Unbenutzte Imports",
            "code_search_by_error(path) — Orphaned Error Handler",
            "code_impact(path) — Auswirkungsanalyse",
        ],
        "bug": [
            "code_diagnostics(path) — LSP-Fehler/Warnungen",
            "code_definition(path, line) — Definition suchen",
            "code_call_hierarchy(path, line) — Aufruf-Hierarchie",
            "code_references(path, line) — Alle Referenzen",
        ],
        "performance": [
            "code_complexity(path) — Complexity-Analyse",
            "code_hot_paths(path) — Heisse Import-Pfade",
            "code_inlay_hints(path) — Type-Hints",
        ],
        "db": [
            "execute_sql(sql) — SQL ausführen",
            "explain_query(sql) — Query-Plan analysieren",
            "list_schemas() — Alle Schemas anzeigen",
        ],
        "web": [
            "firecrawl_search(query) — Web-Suche",
            "firecrawl_scrape(url) — Seite extrahieren",
            "firecrawl_extract(urls) — Strukturierte Daten",
        ],
    }

    tools = intent_recommendations.get(intent, [])
    if tools:
        parts.append(f"  Empfohlen für {intent}:")
        for t in tools:
            parts.append(f"    • {t}")

    # Basis-Tools immer anzeigen
    base_tools = [
        "code_symbols(path) — Datei-Struktur abrufen",
        "code_definition(path, line) — Definition suchen",
        "code_references(path, line) — Referenzen finden",
        "code_diagnostics(path) — LSP-Diagnostik",
        "honcho_search(query) — Historische Analysen durchsuchen",
        "web_search(query) — Web-Suche",
    ]
    parts.append("  Basis-Tools:")
    for t in base_tools:
        parts.append(f"    • {t}")

    # Analyse-Tools
    analysis_tools = [
        "analysis_inspect(path, depth) — Mehrstufige Code-Analyse",
        "analysis_architecture(path) — Architektur-Analyse",
        "analysis_deadcode(path) — Dead-Code-Analyse",
    ]
    parts.append("  Analyse-Automation:")
    for t in analysis_tools:
        parts.append(f"    • {t}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Honcho-Analyse-Historie
# ---------------------------------------------------------------------------

def _query_honcho_analysis_history(query: str) -> Optional[str]:
    """Ruft frühere Analyse-Ergebnisse aus Honcho ab (gecached)."""
    cache_key = f"honcho_analysis:{hash(query)%10000}"
    cached = _honcho_cache.get(cache_key)
    if cached is not None:
        value, timestamp = cached
        if time.time() - timestamp < _HONCHO_CACHE_TTL:
            return value

    try:
        from tools.registry import registry
        result = registry.dispatch("honcho_search", {
            "query": f"analysis:{query[:100]}",
            "max_tokens": 300,
        })
        text = str(result)[:300] if result else ""
        _honcho_cache[cache_key] = (text, time.time())
        _save_honcho_cache()
        return text
    except Exception as e:
        logger.debug("honcho analysis history query failed: %s", e)
        return None


# Cache beim Modul-Import laden (für Cross-Session-Persistenz)
_load_honcho_cache()
