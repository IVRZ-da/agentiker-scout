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
    "debug": {
        "console", "browser console", "devtools", "ui error",
        "ui debug", "ui debugging", "runtime error",
        "network error", "seite lädt nicht", "page not loading",
        "javascript fehler", "js error", "browser error",
        "layout kaputt", "seite kaputt",
    },
}

# Reverse-Map: Keyword → Domain (für schnellen Lookup)
_KEYWORD_TO_DOMAIN: dict[str, str] = {}
for domain, keywords in INTENT_MAP.items():
    for kw in keywords:
        _KEYWORD_TO_DOMAIN[kw] = domain

# ─── Intent Context Builder ─────────────────────────────────────────────
#
# Die Hints nennen konkrete Tool-Namen. Seit der Namespace-Fusion (v0.6.5) heissen die
# Tools ``analysis``/``bughunt``/``research`` mit ``op``-Parameter; mit
# ``SCOUT_NAMESPACES=0`` sind es wieder die 42 Einzelnamen. Die Hints werden deshalb
# aus ``(domain, op, args, beschreibung)`` gebaut statt als feste Strings — sonst
# verweisen sie nach jedem Moduswechsel ins Leere (tote Namen im Prompt sind der
# Normalfall, siehe plugin-tool-surface-economics).


def _bridge_preamble(domain: str, op: str, extra: str = "") -> str:
    """Kopierbares Aufrufmuster für die deferred Dispatcher (v0.6.7).

    Seit v0.6.6 sind ``analysis``/``bughunt``/``research`` deferred: sie stehen nicht im
    Tool-Set, nur im Tool-Search-Katalog. Ein Hint, der nur ``bughunt(op="scan")`` nennt,
    verweist damit ins Leere — das Modell müsste erst ``tool_search`` raten. Deshalb steht
    der fertige ``tool_call``-Block im Hint: ein Turn statt drei.
    """
    args = f'"op":"{op}"' + (f", {extra}" if extra else "")
    return (
        "Deferred — Aufruf in EINEM Schritt:\n"
        f'tool_call({{"calls":[{{"name":"{domain}","arguments":{{{args}}}}}]}})\n'
        "Mehrere ops in einem tool_call bündeln.\n"
    )


def _hint(domain: str, op: str, args: str, beschreibung: str) -> str:
    """Eine Tool-Zeile in der Form, die im aktuellen Modus tatsaechlich existiert."""
    try:
        from scout.namespaces import DOMAIN_PREFIXES, namespaces_enabled

        if namespaces_enabled():
            call = f'{domain}(op="{op}"' + (f", {args}" if args else "") + ")"
        else:
            call = f"{DOMAIN_PREFIXES[domain][0]}{op}({args})"
    except Exception:  # Import defekt: lieber Legacy-Form als gar kein Hint
        call = f"{domain}_{op}({args})"
    return f"- {call} — {beschreibung}"


_INTENT_SPECS: dict[str, tuple[str, list[tuple[str, str, str, str]]]] = {
    "code": ("Analyse-Intent", [
        ("analysis", "inspect", "path, depth=1-5", "mehrstufige Code-Analyse"),
        ("analysis", "architecture", "path", "Abhängigkeitsgraph + Zyklen"),
        ("analysis", "deadcode", "path", "unused imports/functions/errors"),
        ("analysis", "performance", "path", "Complexity-Hotspots"),
        ("analysis", "security", "path", "Security-Pattern-Scan"),
        ("analysis", "ask", "question", "KI-gestützte Code-Frage"),
        ("analysis", "report", "scope, findings", "Ergebnisse persistieren"),
    ]),
    "bug": ("Bug-Hunt-Intent", [
        ("bughunt", "start", "project", "Session starten"),
        ("bughunt", "scan", "patterns", "Automatische grep-Scans"),
        ("bughunt", "finding", "title, severity", "Finding erfassen"),
        ("bughunt", "fix", "session_id, finding_id", "Auto-Fix via Subagent"),
        ("bughunt", "report", "format", "Report generieren"),
        ("bughunt", "pattern", "list|save", "Pattern-Bibliothek"),
    ]),
    "research": ("Research-Intent", [
        ("research", "start", "query, depth, pattern", "Recherche starten"),
        ("research", "save", "id, summary, findings", "Ergebnisse speichern"),
        ("research", "search", "query", "Lokale Recherchen durchsuchen"),
        ("research", "synthesize", "query", "Honcho-Synthese"),
        ("research", "update", "id, findings", "Recherche fortschreiben"),
        ("research", "status", "id", "Fortschritt prüfen"),
    ]),
    "framework": ("Framework-Analyse-Intent", [
        ("analysis", "framework", "path", "Framework-Profil anzeigen"),
        ("bughunt", "scan", "patterns, frameworks=...", "Framework-spezifischer Scan"),
        ("bughunt", "scan", "preset='medusa-full'", "Preset-Scan für erkannten Stack"),
    ]),
}

_PREAMBLE_ARGS: dict[str, tuple[str, str, str]] = {
    "code": ("analysis", "inspect", '"path":"<pfad>"'),
    "bug": ("bughunt", "start", '"project":"<projektpfad>"'),
    "research": ("research", "start", '"query":"<thema>"'),
    "framework": ("analysis", "framework", '"path":"<pfad>"'),
}


def _tool_search_active() -> bool:
    """True, wenn Hermes Plugin-Tools hinter die ``tool_call``-Bridge gelegt hat.

    ``namespaces_enabled()`` beantwortet nur, wie die Tools *heissen* (drei Dispatcher
    vs. 42 Einzelnamen) — nicht, ob sie direkt aufrufbar sind. Mit
    ``tools.tool_search.enabled: off`` liegen alle Plugin-Tools eager im Tool-Set und
    ``tool_call`` existiert gar nicht; ein Hint mit ``tool_call(...)`` verweist dann ins
    Leere. Deshalb hier den echten Bridge-Status fragen statt zu raten.
    """
    try:
        from tools.tool_search import load_config_readonly, should_activate

        # deferrable_tokens > 0: „es gibt deferrierbare Tools" ist genau die Bedingung,
        # unter der Hermes die Bridge baut (should_activate() prueft enabled == "off").
        return bool(should_activate(load_config_readonly(), 1, None))
    except Exception:  # Import/Config defekt: ohne Bridge-Hinweis ist der Schaden kleiner
        return False


def _build_contexts() -> dict[str, str]:
    """Hints fuer den aktiven Modus — bei Moduswechsel neu gebaut."""
    # Zwei unabhaengige Schalter: ob die Tools hinter der Bridge liegen (tool_search) und
    # wie sie heissen (SCOUT_NAMESPACES). Der fertige tool_call-Block nennt den
    # Dispatcher-Namen — im Legacy-Modus existiert der nicht, dort also kein Block.
    deferred = _tool_search_active()
    try:
        from scout.namespaces import namespaces_enabled

        dispatch_names = namespaces_enabled()
    except Exception:  # Import defekt: Legacy-Form ist der sichere Default
        dispatch_names = False
    bridge = deferred and dispatch_names

    contexts: dict[str, str] = {}
    for key, (title, specs) in _INTENT_SPECS.items():
        head = f"[SCOUT] {title} erkannt. "
        if bridge and key in _PREAMBLE_ARGS:
            head += _bridge_preamble(*_PREAMBLE_ARGS[key])
        contexts[key] = head + "Verfügbare Tools:\n" + "\n".join(_hint(*spec) for spec in specs)
    contexts.update({
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
        "debug": (
            "[SCOUT] Debug-/UI-Intent erkannt. Chrome DevTools MCP verfügbar:\n"
            "- mcp_chrome_devtools_navigate_page(url) — Seite laden\n"
            "- mcp_chrome_devtools_list_console_messages() — Console Errors prüfen\n"
            "- mcp_chrome_devtools_list_network_requests() — 4xx/5xx prüfen\n"
            "- mcp_chrome_devtools_take_snapshot() — A11y Tree\n"
            "- mcp_chrome_devtools_evaluate_script(fn) — JS ausführen\n"
            + _hint("bughunt", "scan", "patterns=['console_errors']", "Auto-Scan via Bughunt")
        ),
    })
    return contexts


def _contexts_for_mode() -> dict[str, str]:
    """Liefert die Hints des aktiven Modus (Namespace oder Legacy).

    Wird nur beim Cache-Miss in ``_context_for_domain`` aufgerufen — ein Moduswechsel
    (``SCOUT_NAMESPACES``) kann so nicht zu toten Tool-Namen im Prompt fuehren.
    """
    global _CONTEXT_CACHE, _CONTEXT_MODE
    try:
        from scout.namespaces import namespaces_enabled

        enabled = namespaces_enabled()
    except Exception:  # Import defekt: Legacy-Form ist die sicherere Annahme
        enabled = False
    deferred = _tool_search_active()
    mode = (enabled, deferred)
    if _CONTEXT_CACHE is None or _CONTEXT_MODE != mode:
        _CONTEXT_CACHE = _build_contexts()
        # Beide Dimensionen gehoeren in den Cache-Key: die Namensform (SCOUT_NAMESPACES)
        # und der Bridge-Status (tools.tool_search.enabled). Aendert sich einer, sind die
        # alten Hints tote Namen im Prompt.
        _CONTEXT_MODE = mode
        _INTENT_CACHE.clear()
    return _CONTEXT_CACHE


_CONTEXT_CACHE: dict[str, str] | None = None
_CONTEXT_MODE: tuple[bool, bool] | None = None
_INTENT_CONTEXTS: dict[str, str] = _build_contexts()


# ─── Intent Detection (Single pre_llm_call) ──────────────────────────────

_DOMAIN_PRIORITY = ["bug", "research", "framework", "db", "debug", "web", "code"]
_DOMAIN_PRIORITY_WEIGHTS = {"bug": 10, "research": 8, "framework": 7, "db": 6, "debug": 5, "web": 4, "code": 2}

def _detect_intent(message: str) -> str | None:
    """Detect which domain(s) a message belongs to. Returns most specific domain.

    Single-pass detection: findet den höchstpriorisierten Match.
    Kombiniert Gate-Check + Detection in einem Durchlauf.
    """
    msg_lower = message.lower()
    best_domain: str | None = None
    best_score = 0

    for domain, keywords in INTENT_MAP.items():
        for kw in keywords:
            if kw in msg_lower:
                score = _DOMAIN_PRIORITY_WEIGHTS.get(domain, 1)
                if score > best_score:
                    best_score = score
                    best_domain = domain
                break  # Ein Keyword pro Domain reicht

    return best_domain

def _build_intent_context(domain: str) -> str | None:
    """Return cached context for a detected domain."""
    now = time.monotonic()
    cached = _INTENT_CACHE.get(domain)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    context = _contexts_for_mode().get(domain)
    _INTENT_CACHE[domain] = (now, context)
    return context

def _content_to_text(content: Any) -> str:
    """Normalisiert Message-Content zu Text (str oder Block-Liste)."""
    if isinstance(content, str):
        return content
    if isinstance(content, (list, tuple)):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return ""


def _last_user_message(kwargs: dict[str, Any]) -> str:
    """Aktuelle User-Nachricht aus den Hook-Kwargs ziehen.

    Hermes 0.23.1 uebergibt ``user_message`` (aktueller Turn) plus
    ``conversation_history`` (bisheriger Verlauf). Aeltere Versionen uebergaben
    nur ``messages``. Reihenfolge: user_message -> conversation_history -> messages.
    """
    text = _content_to_text(kwargs.get("user_message"))
    if text.strip():
        return text

    for key in ("conversation_history", "messages"):
        history = kwargs.get(key)
        if not isinstance(history, (list, tuple)):
            continue
        for msg in reversed(history):
            if not isinstance(msg, dict) or msg.get("role") != "user":
                continue
            text = _content_to_text(msg.get("content"))
            if text.strip():
                return text
    return ""


def _bughunt_session_context() -> str | None:
    """Dynamischer Bug-Hunt-Session-Block (nur bei aktiver/letzter Session)."""
    try:
        from scout.bughunt import bughunt_hooks

        return bughunt_hooks.session_context()
    except Exception as e:  # Plugin-Teil nicht ladbar -> Intent-Kontext bleibt
        logger.debug("scout: bughunt session context skipped: %s", e)
        return None


def on_pre_llm_call(**kwargs: Any) -> Optional[str]:
    """Single pre_llm_call hook — detects intent across all 3 domains.

    Replaces 3 separate hooks from analysis, bughunt, and deep-research.
    Returns tool recommendations if a domain intent is detected.
    """
    try:
        last_user_msg = _last_user_message(kwargs)
        if not last_user_msg:
            return None

        # Single-pass detection: findet besten Domain-Match
        domain = _detect_intent(last_user_msg)
        if not domain:
            return None

        context = _build_intent_context(domain)
        if domain == "bug":
            extra = _bughunt_session_context()
            if extra:
                context = f"{context}\n{extra}" if context else extra
        if context:
            logger.debug("scout: injected %s context", domain)
        return context
    except Exception as e:
        logger.warning("scout: on_pre_llm_call error: %s", e)
        return None
