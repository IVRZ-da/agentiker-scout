"""Performance, Security and Ask Analysis Tools.

Extracted from analysis_tools.py monolith.

Tools:
  - analysis_performance_tool: Performance-Bottleneck-Analyse
  - analysis_security_tool: Security-Scan mit Error-Handler + Vulnerability-Patterns
  - analysis_ask_tool: KI-gestützte Codebase-Fragen

Importiert Basis-Funktionen aus tools/base.py und Schemas aus tools/schemas.py.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from .base import (
    _call_tool,
    _parallel_dispatch,
    _validate_and_resolve_path,
    _validate_path,
)

logger = logging.getLogger("analysis")


# ---------------------------------------------------------------------------
# analysis_performance Tool
# ---------------------------------------------------------------------------


def analysis_performance_tool(args: dict, **kwargs) -> str:
    """Performance-Bottleneck-Analyse."""
    from scout._fmt import fmt_err, fmt_ok

    path = args.get("path", "")
    args.get("persist", True)

    error = _validate_path(path)
    if error:
        return fmt_err(error)

    path_error, resolved_path = _validate_and_resolve_path(path)
    if path_error:
        return fmt_err(f"{path_error} (path: {path})")
    path = resolved_path

    report: Dict[str, Any] = {"path": path, "sections": {}, "summary": {}}

    try:
        perf_calls = [
            {"key": "complexity", "name": "code_complexity", "kwargs": {"path": path}},
            {"key": "hot_paths", "name": "code_hot_paths", "kwargs": {"path": path, "top_n": 10}},
            {"key": "metrics", "name": "code_metrics", "kwargs": {"path": path}},
        ]
        if os.path.isfile(path):
            perf_calls.append({
                "key": "inlay_hints",
                "name": "code_inlay_hints",
                "kwargs": {"path": path},
            })

        report["sections"] = _parallel_dispatch(perf_calls)

        hotspots = []
        complexity_data = report["sections"].get("complexity", {})
        if isinstance(complexity_data, dict):
            rank = complexity_data.get("rank", "")
            score = complexity_data.get("complexity", 0)
            has_rank = rank and rank in ("D", "E")
            has_score = isinstance(score, (int, float)) and score > 15
            if has_rank or has_score:
                hotspots.append(f"Hotspot: complexity={score} (rank={rank})")

        hot_paths = report["sections"].get("hot_paths", {})
        if isinstance(hot_paths, dict):
            top = hot_paths.get("hot_paths", []) or hot_paths.get("paths", [])
            if isinstance(top, list) and top:
                report["findings"] = {"hot_path_count": len(top), "hotspots": hotspots}

        report["summary"]["sections_completed"] = len([
            s for s in report["sections"].keys() if not s.endswith("_error")
        ])
    except Exception as e:
        logger.warning("performance analysis error: %s", e)
        report["summary"]["error"] = str(e)

    return fmt_ok(report)


# ---------------------------------------------------------------------------
# analysis_security Tool
# ---------------------------------------------------------------------------


def analysis_security_tool(args: dict, **kwargs) -> str:
    """Security-Analyse: Orphaned Error Handler + Vulnerability Patterns."""
    from scout._fmt import fmt_err, fmt_ok

    path = args.get("path", "")
    kinds = args.get("kinds", ["all"])
    args.get("persist", True)

    error = _validate_path(path)
    if error:
        return fmt_err(error)

    path_error, resolved_path = _validate_and_resolve_path(path)
    if path_error:
        return fmt_err(f"{path_error} (path: {path})")
    path = resolved_path

    report: Dict[str, Any] = {
        "path": path,
        "findings": {},
        "summary": {"errors_scanned": 0, "vulnerabilities_found": 0},
    }

    try:
        if "errors" in kinds or "all" in kinds:
            err_result = _call_tool("code_search_by_error", path=path)
            if err_result:
                if isinstance(err_result, dict) and err_result.get("errors"):
                    report["findings"]["orphaned_errors"] = err_result["errors"]
                    report["summary"]["errors_scanned"] = len(err_result["errors"])
                else:
                    report["findings"]["orphaned_errors"] = err_result

        if "vulnerabilities" in kinds or "all" in kinds:
            try:
                from tools.registry import registry
                sev_result = registry.dispatch("code_search_by_error", {
                    "path": path,
                    "error": "Vulnerability",
                })
                if sev_result:
                    if isinstance(sev_result, str):
                        sev_result = json.loads(sev_result)
                    report["findings"]["security_patterns"] = sev_result
            except Exception as e:
                logger.info("security pattern scan skipped: %s", e)

        # Shared Pattern Scans (P3)
        try:
            from .base import _run_shared_pattern_scans
            shared = _run_shared_pattern_scans(
                path=path,
                kinds=["security"],
            )
            if shared.get("pattern_matches"):
                report["findings"]["shared_patterns"] = shared["pattern_matches"]
                report["summary"]["shared_patterns_count"] = len(shared["pattern_matches"])
                report["summary"]["patterns_scanned"] = shared["patterns_scanned"]
        except Exception as e:
            logger.debug("shared pattern scan skipped: %s", e)

        report["summary"]["vulnerabilities_found"] = len(
            report["findings"].get("orphaned_errors", [])
        ) + len(report["findings"].get("security_patterns", []))
    except Exception as e:
        logger.warning("security analysis error: %s", e)
        report["summary"]["error"] = str(e)

    return fmt_ok(report)


# ---------------------------------------------------------------------------
# analysis_ask Tool
# ---------------------------------------------------------------------------


def analysis_ask_tool(args: dict, **kwargs) -> str:
    """KI-gestützte Analyse-Frage."""
    from scout._fmt import fmt_err, fmt_ok

    question = args.get("question", "")
    path = args.get("path", "")

    if not question.strip():
        return fmt_err("question is required")

    result: Dict[str, Any] = {
        "question": question[:200],
        "context": {},
        "findings": [],
    }

    if path:
        error = _validate_path(path)
        if not error:
            path_error, path_resolved = _validate_and_resolve_path(path)
            if not path_error:
                try:
                    ctx_calls = [
                        {"key": "symbols", "name": "code_symbols", "kwargs": {"path": path_resolved}},
                        {"key": "diagnostics", "name": "code_diagnostics", "kwargs": {"path": path_resolved}},
                    ]
                    result["context"] = _parallel_dispatch(ctx_calls)
                except Exception as e:
                    logger.warning("analysis_ask context collection error: %s", e)

    try:
        from tools.registry import registry
        honcho = registry.dispatch("honcho_search", {
            "query": question[:200],
            "max_tokens": 400,
        })
        if honcho:
            if isinstance(honcho, str):
                result["honcho_context"] = honcho[:500]
            else:
                result["honcho_context"] = str(honcho)[:500]
    except Exception:
        logger.warning("analysis_ask honcho_search failed", exc_info=True)

    result["summary"] = (
        f"Question: {question[:100]}... "
        f"Context sources: {len(result.get('context', {}))} files + Honcho memory"
    )

    return fmt_ok(result)
