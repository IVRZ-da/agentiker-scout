"""analysis_core — Kernlogik des Analyse-Plugins.

Funktionen:
  - inject_analysis_context: pre_llm_call — erkennt Analyse-Intention + injects Kontext
  - track_tool_call: post_tool_call — trackt relevante Tool-Calls
  - persist_analysis_session: on_session_end — persistiert in Honcho

Importiert Sub-Module:
  - intent_helpers: Keywords + Intent-Detection + File-Refs + Recommendations
  - analysis_session: AnalysisSession + Session-State
  - analysis_profiles: Profile + Subagent-Steering + Patching
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Optional

from scout.analysis.intent_helpers import (
    ANALYSIS_TOOLS,
    _build_tool_recommendations,
    _detect_intent,
    _extract_file_refs,
    _is_analysis_query,
    _query_honcho_analysis_history,
)

from .analysis_session import (
    AnalysisSession,
    _analysis_session,
)

logger = logging.getLogger("analysis")


# ---------------------------------------------------------------------------
# Helper: Tool-Ergebnis parsen
# ---------------------------------------------------------------------------

def _parse_result(result: Any) -> Optional[dict]:
    """Parse tool result sicher in ein Dict.

    Unterstützt:
    - bereits ein dict → direkt zurück
    - JSON-String → json.loads
    - Fehler → None (mit Warning-Log)
    """
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            return json.loads(result)
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug("_parse_result: JSON parse error: %s (first 100 chars: %s)",
                         e, result[:100])
            return None
    logger.debug("_parse_result: unexpected type %s", type(result).__name__)
    return None


# ---------------------------------------------------------------------------
# Findings-Aggregation (post_tool_call)
# ---------------------------------------------------------------------------

def _summarize_args(args: dict) -> str:
    """Erzeugt eine kurze Zusammenfassung der Tool-Argumente."""
    parts = []
    for key in ("path", "query", "sql", "url", "pattern", "symbol", "name"):
        value = args.get(key)
        if value:
            if isinstance(value, str) and len(value) > 80:
                value = value[:77] + "..."
            parts.append(f"{key}={value}")
    return ", ".join(parts[:3])  # max 3 args


def _aggregate_findings(tool_name: str, args: dict, result: Any) -> None:
    """Aggregiert Findings aus Tool-Ergebnissen."""
    try:
        parsed = _parse_result(result)

        if tool_name == "code_cycle_detector" and isinstance(parsed, dict):
            cycles = parsed.get("cycles", [])
            if cycles:
                _analysis_session.findings["cycles"] = len(cycles)
                _analysis_session.findings["cycle_details"] = cycles[:5]

        elif tool_name == "code_unused_finder" and isinstance(parsed, dict):
            unused = parsed.get("unused_imports", []) or parsed.get("unused_functions", [])
            if unused:
                _analysis_session.findings["unused_count"] = len(unused)

        elif tool_name == "code_complexity" and isinstance(parsed, list):
            hotspots = [f for f in parsed if isinstance(f, dict) and f.get("complexity", 0) > 15]
            if hotspots:
                _analysis_session.findings["complexity_hotspots"] = len(hotspots)
            elif isinstance(parsed, dict):
                if parsed.get("complexity", 0) > 15:
                    _analysis_session.findings["complexity_hotspots"] = 1

        elif tool_name == "code_diagnostics" and isinstance(parsed, dict):
            errs = parsed.get("errors", 0) or parsed.get("diagnostic_count", 0)
            if errs:
                _analysis_session.findings["diagnostic_errors"] = errs

        elif tool_name in ("code_blast_radius", "code_impact") and isinstance(parsed, dict):
            impacted = parsed.get("affected_files", []) or parsed.get("references", [])
            if impacted:
                _analysis_session.findings["blast_radius"] = len(impacted)

    except Exception as e:
        logger.warning("findings aggregation error for %s: %s", tool_name, e)


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------

def inject_analysis_context(**kwargs: Any) -> Optional[str]:
    """pre_llm_call hook: Erkennt Analyse-Intention und injects Kontext.

    Erkennt Analyse-Keywords in der letzten User-Nachricht, ermittelt die
    Intention (code/architecture/db/...), sucht nach früheren Analysen in
    Honcho und injectt Tool-Empfehlungen + historischen Kontext.
    """
    try:
        messages = kwargs.get("messages", [])
        if not messages:
            return None

        # Letzte User-Nachricht extrahieren
        last_msg = ""
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "user":
                content = m.get("content", "")
                if isinstance(content, str):
                    last_msg = content
                break

        if not last_msg:
            return None

        # Prüfen ob Analyse-Anfrage
        if not _is_analysis_query(last_msg):
            return None

        intent = _detect_intent(last_msg)
        if not intent:
            intent = "code"  # Fallback

        # Analyse-Session starten
        _analysis_session.start(intent, last_msg)

        # Datei-Referenzen extrahieren
        file_refs = _extract_file_refs(last_msg)

        # Tool-Empfehlungen bauen
        recommendations = _build_tool_recommendations(intent, file_refs)

        # Historischen Kontext aus Honcho abrufen
        history_ctx = _query_honcho_analysis_history(last_msg)

        # Endergebnis zusammensetzen
        parts = []
        parts.append(f"[analysis-plugin] 🔍 Analyse erkannt (Typ: {intent})")

        if history_ctx and history_ctx != "None" and history_ctx != "[]":
            parts.append(f"  Bereits bekannt: {history_ctx[:300]}")

        if file_refs:
            parts.append(f"  Dateien: {', '.join(file_refs)}")
            # Versuche code-intel Kontext via tools.registry
            try:
                from tools.registry import registry
                for fref in file_refs:
                    path = fref
                    if not os.path.isabs(path):
                        path = os.path.join(os.getcwd(), path)
                    if os.path.exists(path):
                        syms = registry.dispatch(
                            "code_symbols",
                            {"path": path, "pattern": "", "include_body": False},
                        )
                        if syms:
                            parsed = json.loads(syms) if isinstance(syms, str) else syms
                            sym_list = parsed if isinstance(parsed, list) else parsed.get("symbols", [])
                            if sym_list:
                                summary = f"  {fref}: {len(sym_list)} Symbole"
                                for s in sym_list[:5]:
                                    summary += f"\n    L{s.get('line', '?')} {s.get('kind', '')} {s.get('name', '?')}"
                                parts.append(summary)
            except ImportError:
                pass

        parts.append(f"  Empfohlene Tools:\n{recommendations}")

        return "\n".join(parts)

    except Exception as e:
        logger.warning("analysis-plugin: inject_analysis_context error: %s", e)
        return None


def track_tool_call(**kwargs: Any) -> None:
    """post_tool_call hook: Trackt relevante Tool-Calls während einer Analyse."""
    if not _analysis_session.active:
        return

    tool_name = kwargs.get("tool_name", "")
    if tool_name not in ANALYSIS_TOOLS:
        return

    args = kwargs.get("args", {})
    result = kwargs.get("result", "")
    duration_ms = kwargs.get("duration_ms", 0)
    status = kwargs.get("status", "ok")

    _analysis_session.add_tool_call(tool_name, _summarize_args(args), duration_ms, status)

    for key in ("path",):
        value = args.get(key)
        if isinstance(value, str):
            _analysis_session.add_file(value)

    _aggregate_findings(tool_name, args, result)

    logger.debug(
        "tracked tool call: %s (duration=%dms, status=%s)",
        tool_name, duration_ms, status,
    )


# ---------------------------------------------------------------------------
# on_session_end — Honcho-Persistenz
# ---------------------------------------------------------------------------

def _build_analysis_summary(session: AnalysisSession) -> str:
    """Erzeugt eine menschenlesbare Zusammenfassung der Analyse."""
    parts = []
    parts.append(f"Analyse ({session.intent})")
    parts.append(f"Tools verwendet: {len(session.tools_used)}")

    if session.files_analyzed:
        parts.append(f"Dateien: {len(session.files_analyzed)}")

    findings = session.findings
    if findings:
        parts.append("Ergebnisse:")
        for key, value in findings.items():
            parts.append(f"  - {key}: {value}")

    if session.tools_used:
        total_duration = sum(t.get("duration_ms", 0) for t in session.tools_used)
        parts.append(f"Gesamtdauer: {total_duration}ms")

    return " | ".join(parts)


def persist_analysis_session(**kwargs: Any) -> None:
    """on_session_end hook: Persistiert Analyse-Ergebnisse in Honcho."""
    if not _analysis_session.active:
        return
    if not _analysis_session.tools_used:
        _analysis_session.reset()
        return

    try:
        summary = _build_analysis_summary(_analysis_session)

        try:
            from hermes_cli.plugins import invoke_hook
            invoke_hook(
                "post_llm_call",
                action="honcho_conclude",
                conclusion=(
                    f"analysis:{_analysis_session.intent}:"
                    f"{datetime.now().strftime('%Y-%m-%d')}: "
                    f"{summary[:200]}"
                ),
                metadata={
                    "tools_used": [t["name"] for t in _analysis_session.tools_used],
                    "files_analyzed": list(_analysis_session.files_analyzed),
                    "findings": _analysis_session.findings,
                    "duration_ms": int((time.monotonic() - _analysis_session.started_at) * 1000),
                    "intent": _analysis_session.intent,
                },
            )
        except Exception as e:
            logger.debug("honcho persist failed (expected if honcho not configured): %s", e)
            logger.info(
                "analysis session: %s | tools=%d | files=%d | findings=%s",
                _analysis_session.intent,
                len(_analysis_session.tools_used),
                len(_analysis_session.files_analyzed),
                _analysis_session.findings,
            )

    except Exception as e:
        logger.warning(
            "analysis-plugin: persist_analysis_session error: %s", e,
        )
    finally:
        _analysis_session.reset()
# ---------------------------------------------------------------------------
# Re-export from analysis_profiles for backward compatibility
# Tests and external code rely on these being accessible via analysis_core
# ---------------------------------------------------------------------------
from scout.analysis.analysis_profiles import (  # noqa: E402,F401 — re-export backward compat
    ANALYSIS_PROFILES,  # noqa: F401
    get_active_analysis_profile,  # noqa: F401
    get_profile_tools,  # noqa: F401
    inject_steering_hints,  # noqa: F401
    inject_subagent_steering,  # noqa: F401
    patch_delegate_task,  # noqa: F401
)
