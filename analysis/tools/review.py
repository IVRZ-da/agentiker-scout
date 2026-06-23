"""analysis_review Tool — Automated Code Review.

Composite aus code_review_assistant + code_security_scan + code_diff_analysis.
"""
from __future__ import annotations

import logging
from typing import Any

from scout._fmt import fmt_err, fmt_ok

from .base import _parallel_dispatch, _validate_and_resolve_path

logger = logging.getLogger("analysis")


def analysis_review_tool(args: dict, **kwargs) -> str:
    """Vollständiger Code-Review zwischen zwei Git-Refs."""
    path = args.get("path", "")
    base = args.get("base", "main")
    head = args.get("head", "HEAD")
    max_files = min(args.get("max_files", 10), 30)
    include_security = args.get("include_security", True)

    path_error, resolved_path = _validate_and_resolve_path(path)
    if path_error:
        return fmt_err(f"{path_error} (path: {path})")
    path = resolved_path

    result: dict[str, Any] = {
        "path": path,
        "base": base,
        "head": head,
        "sections": {},
    }

    # Parallel: code_review_assistant + code_diff_analysis
    review_calls = [
        {"key": "review_assistant", "name": "code_review_assistant",
         "kwargs": {"path": path, "base": base, "head": head, "max_files": max_files}},
        {"key": "diff_analysis", "name": "code_diff_analysis",
         "kwargs": {"path": path, "base": base, "head": head, "max_files": max_files}},
    ]
    if include_security:
        review_calls.append({
            "key": "security_scan", "name": "code_security_scan",
            "kwargs": {"path": path, "severity": "all"},
        })

    ctx = _parallel_dispatch(review_calls)

    # Nur relevante Metriken extrahieren
    diff_data = ctx.get("diff_analysis", {})
    if isinstance(diff_data, dict):
        result["sections"]["diff_overview"] = {
            "changed_files": diff_data.get("changed_files",
                           diff_data.get("summary", {}).get("changed_files", 0)),
            "insertions": diff_data.get("insertions",
                          diff_data.get("summary", {}).get("insertions", 0)),
            "deletions": diff_data.get("deletions",
                         diff_data.get("summary", {}).get("deletions", 0)),
        }

    sec_data = ctx.get("security_scan", {})
    if isinstance(sec_data, dict):
        findings = sec_data.get("findings", [])
        result["sections"]["security"] = {
            "total_findings": len(findings) if isinstance(findings, list) else 0,
        }

    review_data = ctx.get("review_assistant", {})
    if isinstance(review_data, dict):
        result["sections"]["review_summary"] = review_data.get("summary", str(review_data)[:500])

    parts = [f"🔍 Code-Review: {base} → {head}"]
    overview = result.get("sections", {}).get("diff_overview", {})
    if overview:
        parts.append(f"  {overview.get('changed_files', '?')} Dateien | "
                     f"+{overview.get('insertions', 0)} -{overview.get('deletions', 0)}")
    sec = result.get("sections", {}).get("security", {})
    if sec:
        parts.append(f"  Security: {sec.get('total_findings', 0)} Findings")
    result["summary"] = "\n".join(parts)

    return fmt_ok(result)
