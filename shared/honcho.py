"""Shared Honcho persistence — single on_session_end for all 3 domains.

Vereinheitlicht die Honcho-Persistenz aus analysis (on_session_end),
bughunt (on_session_end + auto-pattern-deduction) und deep-research (on_session_end).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("scout.honcho")


def _get_honcho_tool(tool_name: str) -> Any:
    """Lazy import honcho tool via registry dispatch."""
    try:
        from tools.registry import registry
        return registry.get_entry(tool_name)
    except Exception:
        return None


def _get_analysis_session() -> dict | None:
    """Get active analysis session if any."""
    try:
        from scout.analysis.analysis_session import _active_session
        if _active_session:
            return {
                "intent": getattr(_active_session, "intent", "unknown"),
                "findings_count": len(getattr(_active_session, "findings", [])),
            }
    except Exception:
        logger.debug("scout.honcho: no active analysis session")
    return None


def _get_bughunt_session() -> dict | None:
    """Get active bug-hunt session if any."""
    try:
        from scout.bughunt.bughunt_core import get_active_session
        session = get_active_session()
        if session:
            return {
                "findings_count": len(session.get("findings", [])),
                "severity": session.get("severity", "unknown"),
            }
    except Exception:
        logger.debug("scout.honcho: no active bug-hunt session")
    return None


def _get_research_session() -> dict | None:
    """Get active research session if any."""
    try:
        from scout.research.research_core import get_active_research
        research = get_active_research()
        if research:
            return {
                "query": research.get("query", ""),
                "sources_count": len(research.get("sources", [])),
            }
    except Exception:
        logger.debug("scout.honcho: no active research session")
    return None


def _persist_analysis_summary() -> None:
    """Persist analysis session findings to Honcho (replaces analysis on_session_end)."""
    session = _get_analysis_session()
    if not session:
        return

    entry = _get_honcho_tool("honcho_conclude")
    if not entry:
        logger.debug("scout.honcho: honcho_conclude nicht verfügbar")
        return

    try:
        entry.handler({
            "peer": "analysis",
            "conclusion": json.dumps({
                "type": "analysis",
                "intent": session["intent"],
                "findings_count": session["findings_count"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }),
        })
    except Exception as e:
        logger.debug("scout.honcho: analysis persist failed: %s", e)


def _persist_bughunt_summary() -> None:
    """Persist bug-hunt session to Honcho + trigger auto-pattern-deduction."""
    session = _get_bughunt_session()
    if not session:
        return

    entry = _get_honcho_tool("honcho_conclude")
    if not entry:
        return

    try:
        entry.handler({
            "peer": "bughunt",
            "conclusion": json.dumps({
                "type": "bughunt",
                "findings_count": session["findings_count"],
                "severity": session["severity"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }),
        })
    except Exception as e:
        logger.debug("scout.honcho: bughunt persist failed: %s", e)

    # Auto-pattern-deduction (bisher in bughunt_hooks.on_session_end)
    try:
        from scout.bughunt.bughunt_hooks import _auto_deduce_patterns
        _auto_deduce_patterns()
    except Exception as e:
        logger.debug("scout.honcho: pattern deduction failed: %s", e)


def _persist_research_summary() -> None:
    """Persist research session to Honcho (replaces deep-research on_session_end)."""
    session = _get_research_session()
    if not session:
        return

    entry = _get_honcho_tool("honcho_conclude")
    if not entry:
        return

    try:
        entry.handler({
            "peer": "research",
            "conclusion": json.dumps({
                "type": "deep_research",
                "query": session["query"],
                "sources_count": session["sources_count"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }),
        })
    except Exception as e:
        logger.debug("scout.honcho: research persist failed: %s", e)


def on_post_tool_call(**kwargs: Any) -> None:
    """Shared post_tool_call — tracks tool calls for active sessions.

    Leichtgewichtig: nur bei aktivem Intent wird getrackt.
    Replaces 3 separate post_tool_call hooks (analysis, bughunt, deep-research).
    """
    tool_name = kwargs.get("tool_name", "")
    if not tool_name:
        return

    # Nur tracken wenn relevant für eine Domain
    domain_prefixes = {
        "analysis_": "analysis",
        "bug_hunt_": "bughunt",
        "research_": "research",
        "code_": "analysis",
        "firecrawl_": "research",
    }

    matched = None
    for prefix, domain in domain_prefixes.items():
        if tool_name.startswith(prefix):
            matched = domain
            break

    if not matched:
        return

    logger.debug("scout: tracked %s → %s", tool_name, matched)
    # TODO: Optional in future — track findings/timing per domain


def on_session_end(**kwargs: Any) -> None:
    """Shared on_session_end — persists all active sessions to Honcho.

    Replaces 3 separate on_session_end hooks (analysis, bughunt, deep-research).
    Fires all 3 persist functions — nur aktive Sessions machen was.
    """
    _persist_analysis_summary()
    _persist_bughunt_summary()
    _persist_research_summary()
    logger.debug("scout: on_session_end completed")
