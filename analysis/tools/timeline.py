"""analysis_timeline Tool — Symbol/Projekt-Evolution über Git-History.

Composite aus code_timeline + code_git_log_symbol + code_diff_analysis.
"""
from __future__ import annotations

import logging
from typing import Any

from scout._fmt import fmt_err, fmt_ok

from .base import _call_tool, _validate_and_resolve_path, _validate_path

logger = logging.getLogger("analysis")


def analysis_timeline_tool(args: dict, **kwargs) -> str:
    """Zeitliche Entwicklung eines Symbols oder Projekts."""
    path = args.get("path", "")
    symbol = args.get("symbol", "")
    max_commits = min(args.get("max_commits", 10), 50)

    error = _validate_path(path)
    if error:
        return fmt_err(error)

    path_error, resolved_path = _validate_and_resolve_path(path)
    if path_error:
        return fmt_err(f"{path_error} (path: {path})")
    path = resolved_path

    result: dict[str, Any] = {
        "path": path,
        "symbol": symbol or None,
        "max_commits": max_commits,
        "sections": {},
    }

    # 1. code_diff_analysis — Änderungen zwischen letzten 2 Ref-Commits
    try:
        diff = _call_tool("code_diff_analysis", path=path, base="HEAD~5", head="HEAD", max_files=10)
        if diff and isinstance(diff, dict):
            # Nur relevante Metriken extrahieren, kein Full-Dump
            changed_files = diff.get("changed_files", diff.get("summary", {}).get("changed_files", 0))
            insertions = diff.get("insertions", diff.get("summary", {}).get("insertions", 0))
            deletions = diff.get("deletions", diff.get("summary", {}).get("deletions", 0))
            result["sections"]["recent_diff"] = {
                "changed_files": changed_files,
                "insertions": insertions,
                "deletions": deletions,
            }
    except Exception as e:
        logger.debug("code_diff_analysis skipped: %s", e)

    # 2. Symbol-Timeline (wenn symbol angegeben)
    if symbol:
        try:
            sym_line = 1
            syms = _call_tool("code_symbols", path=path, pattern=symbol)
            if isinstance(syms, dict):
                for s in syms.get("symbols", []):
                    if s.get("name") == symbol:
                        sym_line = s.get("line", 1)
                        break

            timeline = _call_tool("code_timeline", path=path, line=sym_line, max_commits=max_commits)
            if timeline:
                if isinstance(timeline, dict):
                    commits = timeline.get("commits", timeline.get("data", []))
                    if isinstance(commits, list):
                        result["sections"]["symbol_timeline"] = {
                            "symbol": symbol,
                            "total_commits": len(commits),
                            "commits": [
                                {
                                    "date": c.get("date", c.get("timestamp", "")),
                                    "author": c.get("author", ""),
                                    "message": c.get("message", "")[:80],
                                }
                                for c in commits[:max_commits]
                            ],
                        }
        except Exception as e:
            logger.debug("code_timeline skipped: %s", e)

    # 3. Git Log für Symbol (wenn angegeben)
    if symbol:
        try:
            git_log = _call_tool("code_git_log_symbol", path=path, line=1, max_count=max_commits)
            if git_log:
                result["sections"]["git_log"] = (
                    git_log if isinstance(git_log, dict) else {"raw": str(git_log)[:500]}
                )
        except Exception as e:
            logger.debug("code_git_log_symbol skipped: %s", e)

    # Summary bauen
    parts = [f"📅 Timeline für {path}"]
    if symbol:
        parts.append(f"  Symbol: {symbol}")
    if "recent_diff" in result["sections"]:
        d = result["sections"]["recent_diff"]
        parts.append(f"  Letzte Änderungen: +{d['insertions']} -{d['deletions']} ({d['changed_files']} Dateien)")
    if "symbol_timeline" in result["sections"]:
        parts.append(f"  Symbol-History: {result['sections']['symbol_timeline']['total_commits']} Commits")

    result["summary"] = "\n".join(parts)

    return fmt_ok(result)
