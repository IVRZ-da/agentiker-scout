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
    _call_tool_direct,
    _parallel_dispatch,
    _persist_analysis,
    _try_create_bughunt_finding,
    _try_create_plan_follow_plan,
    _validate_and_resolve_path,
    _validate_path,
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
    max_files = min(args.get("max_files", 500), 1000)
    timeout = min(args.get("timeout", 60), 300)

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
            unused = _call_tool_direct("code_unused_finder", path=path, kinds=["imports"], max_files=max_files, timeout=timeout)
            if unused:
                report["findings"]["unused_imports"] = unused
                if isinstance(unused, dict):
                    total_unused += len(unused.get("unused", []))
        except Exception as e:
            report["findings"]["unused_imports_error"] = str(e)

    if "functions" in kinds or "all" in kinds:
        try:
            unused_funcs = _call_tool_direct("code_unused_finder", path=path, kinds=["functions"], max_files=max_files, timeout=timeout)
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
# analysis_dependency_risk Tool
# ---------------------------------------------------------------------------


def analysis_dependency_risk_tool(args: dict, **kwargs) -> str:
    """Bewertet Abhängigkeitsrisiken einer Datei/eines Projekts.

    Kombiniert code_dependency_risk + code_complexity + code_hot_paths.
    """
    from scout._fmt import fmt_err, fmt_ok

    path = args.get("path", "")
    detail_level = args.get("detail_level", "summary")

    error = _validate_path(path)
    if error:
        return fmt_err(error)

    path_error, resolved_path = _validate_and_resolve_path(path)
    if path_error:
        return fmt_err(f"{path_error} (path: {path})")
    path = resolved_path

    report: dict[str, Any] = {
        "path": path,
        "risk_score": 0,
        "risk_level": "unknown",
        "components": {},
    }

    scores: list[float] = []

    # 1. Dependency Risk
    try:
        dep_risk = _call_tool("code_dependency_risk", path=path)
        if isinstance(dep_risk, dict):
            score = dep_risk.get("risk_score", dep_risk.get("score", 0))
            scores.append(float(score))
            report["components"]["dependency_risk"] = {
                "score": score,
                "level": dep_risk.get("risk_level", "unknown"),
            }
    except Exception as e:
        logger.debug("code_dependency_risk skipped: %s", e)

    # 2. Complexity
    try:
        compl = _call_tool("code_complexity", path=path, directory=True)
        if isinstance(compl, dict):
            avg = float(compl.get("average_complexity", compl.get("avg", 0)))
            max_c = float(compl.get("max_complexity", compl.get("max", 0)))
            normalized = min(max_c / 20.0, 10.0)
            scores.append(normalized)
            report["components"]["complexity"] = {
                "average": avg,
                "max": max_c,
                "score": round(normalized, 1),
            }
    except Exception as e:
        logger.debug("code_complexity skipped: %s", e)

    # 3. Hot Paths (wenn Verzeichnis)
    if os.path.isdir(path):
        try:
            hot = _call_tool("code_hot_paths", path=path, top_n=5)
            if isinstance(hot, dict):
                paths = hot.get("hot_paths", hot.get("paths", []))
                if isinstance(paths, list) and paths:
                    report["components"]["hot_paths"] = {
                        "count": len(paths),
                        "top": [
                            {"file": p.get("file", p.get("path", "")), "callers": p.get("callers", 0)}
                            for p in paths[:5]
                        ],
                    }
        except Exception as e:
            logger.debug("code_hot_paths skipped: %s", e)

    if scores:
        total = sum(scores) / len(scores)
        report["risk_score"] = round(total, 1)
        if total < 3:
            report["risk_level"] = "low"
        elif total < 6:
            report["risk_level"] = "medium"
        else:
            report["risk_level"] = "high"

    parts = [f"⚠️ Risk Score: {report['risk_score']}/10 ({report['risk_level']})"]
    for key, val in report["components"].items():
        if isinstance(val, dict):
            if "score" in val:
                parts.append(f"  • {key}: {val['score']}/10")
            if "count" in val:
                parts.append(f"  • {key}: {val['count']} Hotspots")
    report["summary"] = "\n".join(parts)

    if detail_level == "detailed":
        return fmt_ok(report)
    return fmt_ok({
        "path": path,
        "risk_score": report["risk_score"],
        "risk_level": report["risk_level"],
        "components": {k: v.get("score", v.get("count", "?")) for k, v in report["components"].items()},
        "summary": report["summary"],
    })


# ---------------------------------------------------------------------------
# analysis_risk Tool — Multi-Faktor Risk Assessment
# ---------------------------------------------------------------------------


def analysis_risk_tool(args: dict, **kwargs) -> str:
    """Multi-Faktor Risk Assessment für ein Projekt.

    Kombiniert dependency_risk + complexity + deadcode + security + hotspots + duplicates.
    """
    from scout._fmt import fmt_err, fmt_ok

    path = args.get("path", "")
    categories = args.get("categories", [])

    path_error, resolved_path = _validate_and_resolve_path(path)
    if path_error:
        return fmt_err(f"{path_error} (path: {path})")
    path = resolved_path

    if not os.path.isdir(path):
        return fmt_err(f"Not a directory: {path}")

    include_all = not categories
    result: dict[str, Any] = {
        "path": path,
        "risk_score": 0,
        "risk_level": "unknown",
        "components": {},
    }
    scores: list[float] = []

    # Definition der Risiko-Checks (data-driven — ersetzt 6 Repeat-Blöcke)
    risk_checks = [
        ("dependencies", "code_dependency_risk", {},
         lambda r: float(r.get("risk_score", r.get("score", 0))),
         lambda r, s: {"score": s, "level": r.get("risk_level", "")}),
        ("complexity", "code_complexity", {"directory": True},
         lambda r: min(float(r.get("max_complexity", r.get("max", 0))) / 20.0, 10.0),
         lambda r, s: {"score": round(s, 1), "max": r.get("max_complexity", r.get("max", 0))}),
        ("deadcode", "code_unused_finder", {"kinds": ["all"], "max_files": 200, "timeout": 30},
         lambda r: min(len(r.get("unused", r.get("data", [])) if isinstance(r.get("unused", r.get("data", [])), list) else []), 10),
         lambda r, s: {"unused_count": len(r.get("unused", r.get("data", [])) if isinstance(r.get("unused", r.get("data", [])), list) else []), "score": s}),
        ("security", "code_security_scan", {"severity": "HIGH"},
         lambda r: min(len(r.get("findings", []) if isinstance(r.get("findings", []), list) else []) * 2, 10),
         lambda r, s: {"findings": len(r.get("findings", []) if isinstance(r.get("findings", []), list) else []), "score": s}),
        ("hotspots", "code_hot_paths", {"top_n": 5},
         lambda r: min(len(r.get("hot_paths", r.get("paths", [])) if isinstance(r.get("hot_paths", r.get("paths", [])), list) else []) * 2, 10),
         lambda r, s: {"count": len(r.get("hot_paths", r.get("paths", [])) if isinstance(r.get("hot_paths", r.get("paths", [])), list) else []), "score": s}),
        ("duplicates", "code_duplicates", {"min_lines": 5, "top_n": 10},
         lambda r: min(len(r.get("duplicates", r.get("data", [])) if isinstance(r.get("duplicates", r.get("data", [])), list) else []), 10),
         lambda r, s: {"count": len(r.get("duplicates", r.get("data", [])) if isinstance(r.get("duplicates", r.get("data", [])), list) else []), "score": s}),
    ]

    for name, tool_name, extra_kwargs, score_fn, component_fn in risk_checks:
        if not (include_all or name in categories):
            continue
        try:
            r = _call_tool(tool_name, path=path, **extra_kwargs)
            if isinstance(r, dict):
                s = float(score_fn(r))
                scores.append(s)
                result["components"][name] = component_fn(r, s)
        except Exception as e:
            logger.debug("%s skipped: %s", name, e)

    # Gesamt-Score
    if scores:
        total = sum(scores) / len(scores)
        result["risk_score"] = round(total, 1)
        if total < 3:
            result["risk_level"] = "low"
        elif total < 6:
            result["risk_level"] = "medium"
        else:
            result["risk_level"] = "high"

    parts = [f"⚠️ Multi-Faktor Risk Score: {result['risk_score']}/10 ({result['risk_level']})"]
    for key, val in result["components"].items():
        if isinstance(val, dict):
            s = val.get("score", "?")
            parts.append(f"  • {key}: {s}/10")
    result["summary"] = "\n".join(parts)

    return fmt_ok(result)
