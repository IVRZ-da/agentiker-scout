"""
Hooks für das Deep Research Plugin.

pre_llm_call: Injiziert relevante Research-Ergebnisse in den Context vor jedem LLM-Call.
post_tool_call: Trackt Firecrawl-Tool-Aufrufe für Research-Fortschritt.
on_session_end: Automatische Honcho-Persistenz bei Session-Ende.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent
RESULTS_DIR = PLUGIN_DIR / "data" / "results"
PLANS_DIR = PLUGIN_DIR / "data" / "plans"
TRACKER_PATH = PLUGIN_DIR / "data" / "_tracker.json"

logger = logging.getLogger(__name__)

# In-Memory Tracking-Store (lebt pro Session, mit Disk-Persistenz)
_tool_call_tracker = {
    "firecrawl_calls": [],
    "research_started": None,
    "research_saved": False,
}


def _save_tracker():
    """Speichert den Tracker auf Disk für Session-übergreifende Persistenz."""
    try:
        TRACKER_PATH.write_text(json.dumps(_tool_call_tracker, indent=2))
    except (OSError, IOError) as e:
        logger.debug("Tracker save failed: %s", e)


def _load_tracker():
    """Lädt den Tracker von Disk (falls vorhanden)."""
    if TRACKER_PATH.exists():
        try:
            data = json.loads(TRACKER_PATH.read_text())
            _tool_call_tracker.update(data)
        except (json.JSONDecodeError, OSError) as e:
            logger.debug("Tracker load failed: %s", e)

# Lade gespeicherten Tracker von Disk (Session-übergreifend)
_load_tracker()


# ---------------------------------------------------------------------------
# pre_llm_call
# ---------------------------------------------------------------------------

def on_pre_llm_call(**kwargs) -> str | None:
    """
    Vor jedem LLM-Call: Injiziert relevante Research-Ergebnisse.

    Durchsucht gespeicherte Ergebnisse nach Keyword-Überlappung mit
    der aktuellen User-Nachricht. Zeigt auch Tracking-Status an.
    """
    try:
        from tools.registry import registry
    except ImportError:
        return None

    honcho_available = _check_honcho_available()

    # Alle gespeicherten Ergebnisse laden
    results = _load_all_results()
    user_input = _get_user_input(**kwargs)
    context_parts = []

    # Research-Tracking-Status (wenn research gestartet wurde)
    if _tool_call_tracker["research_started"]:
        rid = _tool_call_tracker["research_started"]
        fc_count = len(_tool_call_tracker["firecrawl_calls"])
        saved = _tool_call_tracker["research_saved"]
        auto_synth = _tool_call_tracker.get("_auto_synth_triggered", False)

        if saved:
            status = "✅ gespeichert"
            if auto_synth:
                status += " · 🧠 Auto-Synthese ausgelöst"
            context_parts.append(
                f"📋 **Aktive Research-Session:** `{rid}` — {status}"
            )
        else:
            # Fortschrittsbalken
            progress = min(fc_count * 20, 95) if fc_count > 0 else 5
            bar_len = 20
            filled = max(1, int(progress / 100 * bar_len))
            bar = "█" * filled + "░" * (bar_len - filled)
            context_parts.append(
                f"📋 **Aktive Research-Session:** `{rid}`\n"
                f"   🔄 Status: läuft ({fc_count} Firecrawl-Calls)\n"
                f"   📊 Fortschritt: |{bar}| {progress}%\n"
                f"   💡 Nächster Schritt: firecrawl_search/scrape → research_save"
            )
        if not saved and fc_count == 0:
            context_parts.append(
            "   ⚠️ Noch keine Firecrawl-Tools aufgerufen. "
            "Führe die Recherche durch: firecrawl_search, firecrawl_scrape, ..."
        )

    # Stale-Data Warning: Wenn über 80 Results, als Banner anzeigen
    if len(results) > 80:
        context_parts.append(
            f"⚠️ **Datenmüll:** {len(results)} alte Recherche-Ergebnisse gespeichert. "
            f"Der nächste research_save löscht automatisch die ältesten (>100)."
        )

    # Relevante Ergebnisse aus lokalen JSONs
    relevant = _find_relevant(user_input, results, max_results=3) if user_input else []
    if relevant:
        context_parts.append("📚 **Gespeicherte Recherche-Ergebnisse (deep-research Plugin):**")
        for r in relevant:
            context_parts.append(f"  • **{r['query']}** ({r['status']}, {r['sources_count']} Quellen)")
            if r.get("summary"):
                context_parts.append(f"    → {r['summary'][:200]}...")
            context_parts.append(f"    → ID: `{r['id']}`")

    if honcho_available:
        context_parts.append(
            "💡 *Nutze `honcho_search(peer='research')` für semantische Suche "
            "in Honcho — dort sind alle Research-Conclusions gespeichert.*"
        )

    if not context_parts:
        return None

    return "\n".join(context_parts)


# ---------------------------------------------------------------------------
# post_tool_call
# ---------------------------------------------------------------------------

def on_post_tool_call(**kwargs) -> None:
    """
    Nach jedem Tool-Call: Trackt Firecrawl-Tools für Research-Fortschritt.

    Erkennt Aufrufe von firecrawl_search, firecrawl_scrape, firecrawl_agent
    und aggregiert sie im In-Memory-Tracker.
    """
    tool_name = kwargs.get("tool_name", "")
    kwargs.get("result", "")

    # research_save erkennen + Auto-Synthese anregen
    if tool_name == "research_save" and _tool_call_tracker["research_started"]:
        _tool_call_tracker["research_saved"] = True
        _save_tracker()

        # Versuche honcho_reasoning für Auto-Synthese zu triggern
        # (Nur als Hinweis — der Hook kann keine Tools direkt aufrufen)
        try:
            from tools.registry import registry
            if registry.get_entry("honcho_conclude"):
                _tool_call_tracker["_auto_synth_triggered"] = True
        except (ImportError, AttributeError):
            _tool_call_tracker["_auto_synth_triggered"] = False
        return

    # Nur Firecrawl-Tools tracken
    if not tool_name.startswith("mcp_firecrawl_"):
        return

    # Wenn research_started, tracke den Call
    if _tool_call_tracker["research_started"]:
        _tool_call_tracker["firecrawl_calls"].append({
            "tool": tool_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        _save_tracker()


# ---------------------------------------------------------------------------
# on_session_end
# ---------------------------------------------------------------------------

def on_session_end(**kwargs) -> None:
    """
    Bei Session-Ende: Automatische Honcho-Persistenz.

    Falls research_start aufgerufen wurde aber research_save nicht,
    wird eine 'partial' Sicherung angelegt.
    """
    if not _tool_call_tracker["research_started"]:
        return

    if _tool_call_tracker["research_saved"]:
        return  # Wurde bereits gespeichert

    # Automatische Partial-Sicherung
    rid = _tool_call_tracker["research_started"]
    plan_path = PLANS_DIR / f"{rid}.json"
    if not plan_path.exists():
        return

    fc_count = len(_tool_call_tracker["firecrawl_calls"])
    try:
        plan = json.loads(plan_path.read_text())
    except (json.JSONDecodeError, OSError):
        return

    # Partial-Ergebnis schreiben
    partial = {
        "id": rid,
        "query": plan.get("query", ""),
        "depth": plan.get("depth", 0),
        "summary": f"Session beendet bevor research_save aufgerufen wurde. "
                   f"{fc_count} Firecrawl-Tool-Calls getrackt.",
        "findings": [],
        "sources": [],
        "status": "partial",
        "created_at": plan.get("created_at", ""),
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "_auto_saved": True,
    }
    result_path = RESULTS_DIR / f"{rid}.json"
    result_path.write_text(json.dumps(partial, indent=2, ensure_ascii=False))
    if plan_path.exists():
        plan_path.unlink()

    # Tracker zurücksetzen — kein stale research mehr im pre_llm_call
    reset_tracker(None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def reset_tracker(research_id: str | None = None) -> None:
    """Setzt den Tool-Call-Tracker zurück. Wird von research_start aufgerufen."""
    _tool_call_tracker["firecrawl_calls"] = []
    _tool_call_tracker["research_started"] = research_id
    _tool_call_tracker["research_saved"] = False
    _save_tracker()


def _check_honcho_available() -> bool:
    try:
        from tools.registry import registry
        return registry.get_entry("honcho_search") is not None
    except Exception:
        return False


def _load_all_results() -> list[dict]:
    if not RESULTS_DIR.exists():
        return []
    results = []
    for f in sorted(RESULTS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text())
            if data:
                results.append({
                    "id": data.get("id", f.stem),
                    "query": data.get("query", ""),
                    "status": data.get("status", ""),
                    "summary": data.get("summary", ""),
                    "findings_count": len(data.get("findings", [])),
                    "sources_count": len(data.get("sources", [])),
                    "saved_at": data.get("saved_at", ""),
                })
        except (json.JSONDecodeError, OSError):
            continue
    return results


def _get_user_input(**kwargs) -> str:
    for key in ("user_message", "message", "input", "text"):
        if key in kwargs and isinstance(kwargs[key], str):
            return kwargs[key]
    return ""


def _find_relevant(user_input: str, results: list[dict], max_results: int = 3) -> list[dict]:
    if not user_input or not results:
        return []

    stop_words = {"der", "die", "das", "ein", "eine", "ist", "sind", "war",
                  "wie", "was", "wer", "wann", "wo", "und", "oder", "aber",
                  "mit", "von", "für", "auf", "bei", "nach", "aus", "zu",
                  "den", "dem", "des", "the", "a", "an", "in", "to", "of",
                  "it", "is", "are", "was", "were", "be", "been", "being",
                  "have", "has", "had", "do", "does", "did", "will", "would",
                  "can", "could", "shall", "should", "may", "might", "i"}

    user_words = set(
        w.lower().strip(".,!?;:()[]{}'\"")
        for w in re.split(r'\s+', user_input)
        if len(w) > 2 and w.lower() not in stop_words
    )

    if not user_words:
        return results[:max_results]

    scored = []
    for r in results:
        search_text = f"{r['query']} {r['summary']}".lower()
        matches = sum(1 for w in user_words if w in search_text)
        if matches > 0:
            scored.append((matches, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:max_results]]
