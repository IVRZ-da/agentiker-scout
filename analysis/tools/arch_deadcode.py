"""Architecture and Dead Code Analysis Tools.

Extracted from analysis_tools.py monolith.

Tools:
  - analysis_architecture_tool: Architektur-Analyse mit cycle_detector + dependency_graph
  - analysis_deadcode_tool: Dead-Code-Scan mit unused_finder

Importiert Basis-Funktionen aus tools/base.py und Schemas aus tools/schemas.py.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from scout._fmt import fmt_err, fmt_ok

from .base import (
    _call_tool,
    _parallel_dispatch,
    _persist_analysis,
    _try_create_bughunt_finding,
    _try_create_plan_follow_plan,
    _validate_and_resolve_path,
)

logger = logging.getLogger("analysis")


# ---------------------------------------------------------------------------
# analysis_architecture Tool
# ---------------------------------------------------------------------------


def analysis_architecture_tool(args: dict, **kwargs) -> str:
    """Architektur-Analyse mit cycle_detector + dependency_graph."""
    path = args.get("path", "")
    fmt = args.get("format", "text")
    depth = min(args.get("depth", 2), 3)

    # Path-Validierung
    path_error, resolved_path = _validate_and_resolve_path(path)
    if path_error:
        return fmt_err(f"{path_error} (path: {path})")
    path = resolved_path

    if not path or not os.path.isdir(path):
        return fmt_err(f"Directory not found: {path}")

    report: Dict[str, Any] = {
        "tool": "analysis_architecture",
        "path": path,
        "format": fmt,
        "depth": depth,
        "sections": {},
        "summary": {},
    }

    # Alle Sections parallel dispatchen
    arch_calls = [
        {"key": "workspace", "name": "code_workspace_summary", "kwargs": {"path": path}},
        {"key": "dependency_graph", "name": "code_dependency_graph", "kwargs": {"path": path, "format": fmt}},
        {"key": "hot_paths", "name": "code_hot_paths", "kwargs": {"path": path, "top_n": 10}},
    ]
    if depth >= 2:
        arch_calls.append({"key": "cycles", "name": "code_cycle_detector", "kwargs": {"path": path}})
    if depth >= 3:
        arch_calls.append({"key": "unused_code", "name": "code_unused_finder", "kwargs": {"path": path}})

    report["sections"] = _parallel_dispatch(arch_calls)

    report["summary"]["sections_completed"] = len([s for s in report["sections"].keys() if not s.endswith("_error")])

    # Persistieren
    try:
        _persist_analysis("architecture", report, {
            "path": path,
            "depth": depth,
            "sections": report["summary"]["sections_completed"],
        })
    except Exception as e:
        logger.info("analysis persist skipped — Honcho not available: %s", e)

    # plan_follow Plan erstellen (lose Kopplung via Registry)
    _try_create_plan_follow_plan("analysis_architecture", path)

    # Bug-Hunt Finding bei Architecture-Zyklen (lose Kopplung)
    cycles_section = report.get("sections", {}).get("cycles", {})
    cycles_count = 0
    if isinstance(cycles_section, dict):
        cycles_list = cycles_section.get("cycles", cycles_section.get("data", []))
        if isinstance(cycles_list, list):
            cycles_count = len(cycles_list)
    if cycles_count > 0:
        _try_create_bughunt_finding(
            severity="high",
            title=f"Architektur-Zyklen: {cycles_count} zirkuläre Abhängigkeiten in {path}",
            details={"tool": "analysis_architecture", "path": path, "cycles": cycles_count},
        )

    return fmt_ok(report)


# ---------------------------------------------------------------------------
# analysis_deadcode Tool
# ---------------------------------------------------------------------------


def analysis_deadcode_tool(args: dict, **kwargs) -> str:
    """Dead-Code-Analyse mit unused_finder + search_by_error + impact."""
    path = args.get("path", "")
    kinds = args.get("kinds", ["all"])
    persist = args.get("persist", True)

    # Path-Validierung
    path_error, resolved_path = _validate_and_resolve_path(path)
    if path_error:
        return fmt_err(f"{path_error} (path: {path})")
    path = resolved_path

    if not path or not os.path.exists(path):
        return fmt_err(f"Path not found: {path}")

    report: Dict[str, Any] = {
        "tool": "analysis_deadcode",
        "path": path,
        "kinds": kinds,
        "findings": {},
        "summary": {},
    }

    total_unused = 0

    # 1. Unused Finder
    if "imports" in kinds or "all" in kinds:
        try:
            unused = _call_tool("code_unused_finder", path=path, kinds=["imports"])
            if unused:
                report["findings"]["unused_imports"] = unused
                if isinstance(unused, dict):
                    total_unused += len(unused.get("unused", []))
        except Exception as e:
            report["findings"]["unused_imports_error"] = str(e)

    if "functions" in kinds or "all" in kinds:
        try:
            unused_funcs = _call_tool("code_unused_finder", path=path, kinds=["functions"])
            if unused_funcs:
                report["findings"]["unused_functions"] = unused_funcs
                if isinstance(unused_funcs, dict):
                    total_unused += len(unused_funcs.get("unused", []))
        except Exception as e:
            report["findings"]["unused_functions_error"] = str(e)

    # 2. Orphaned Error Handler
    if "errors" in kinds or "all" in kinds:
        try:
            errors = _call_tool("code_search_by_error", path=path)
            if errors:
                report["findings"]["orphaned_errors"] = errors
        except Exception as e:
            report["findings"]["orphaned_errors_error"] = str(e)

    # Shared Pattern Scans (P3) — Code-Quality Patterns
    try:
        from .base import _run_shared_pattern_scans
        shared = _run_shared_pattern_scans(
            path=path,
            kinds=["code-quality"],
        )
        if shared.get("pattern_matches"):
            report["findings"]["shared_patterns"] = shared["pattern_matches"]
            report["summary"]["shared_patterns_count"] = len(shared["pattern_matches"])
            report["summary"]["patterns_scanned"] = shared["patterns_scanned"]
    except Exception as e:
        logger.debug("shared pattern scan skipped: %s", e)

    # 3. Code Duplicates
    if "all" in kinds or "code-quality" in kinds:
        try:
            duplicates = _call_tool("code_duplicates", path=path, min_lines=5, top_n=10)
            if duplicates:
                report["findings"]["duplicates"] = duplicates
        except Exception as e:
            report["findings"]["duplicates_error"] = str(e)

    report["summary"]["total_unused"] = total_unused

    if persist:
        try:
            _persist_analysis("deadcode", report, {
                "path": path,
                "total_unused": total_unused,
            })
        except Exception as e:
            logger.info("analysis persist skipped — Honcho not available: %s", e)

    # plan_follow Plan erstellen (lose Kopplung via Registry)
    _try_create_plan_follow_plan("analysis_deadcode", path)

    # Bug-Hunt Finding bei Dead-Code-Fund (lose Kopplung)
    if total_unused > 0:
        _try_create_bughunt_finding(
            severity="medium",
            title=f"Dead Code: {total_unused} ungenutzte Elemente in {path}",
            details={"tool": "analysis_deadcode", "path": path, "total_unused": total_unused},
        )

    return fmt_ok(report)


# ---------------------------------------------------------------------------
