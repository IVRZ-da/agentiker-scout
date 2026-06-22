"""Inspect-Tool für mehrstufige Code-Analyse.

Extrahiert aus analysis_tools.py:
  - analysis_inspect_tool: Mehrstufige Code-Analyse (depth 1-5)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from scout._fmt import fmt_err, fmt_ok

from ..tools.base import _try_create_plan_follow_plan
from .base import (
    _call_tool,
    _clear_symbol_line_cache,
    _find_symbol_line,
    _persist_analysis,
    _summarize_diagnostics,
    _summarize_symbols,
    _validate_and_resolve_path,
)

logger = logging.getLogger("analysis")


def analysis_inspect_tool(args: dict, **kwargs) -> str:
    """Mehrstufige Code-Analyse.

    Führt depth-abhängig verschiedene code-intel Tools aus und
    aggregiert die Ergebnisse in einem strukturierten Report.
    """
    path = args.get("path", "")
    symbol = args.get("symbol", "")
    depth = min(args.get("depth", 2), 5)
    persist = args.get("persist", True)

    # Cache für die Analyse leeren (gilt nur für diesen Durchlauf)
    _clear_symbol_line_cache()

    # Path-Validierung
    path_error, resolved_path = _validate_and_resolve_path(path)
    if path_error:
        return fmt_err(f"{path_error} (path: {path})")
    path = resolved_path

    if not os.path.exists(path):
        return fmt_err(f"Path not found: {path}")

    report: Dict[str, Any] = {
        "tool": "analysis_inspect",
        "path": path,
        "symbol": symbol or None,
        "depth": depth,
        "layers": {},
        "summary": {},
    }

    # Layer 1: Basis-Informationen (immer)
    try:
        sym_result = _call_tool("code_symbols", path=path, kind="all", max_results=200)
        layer1 = {"symbols": _summarize_symbols(sym_result), "count": 0}
        if isinstance(layer1["symbols"], list):
            layer1["count"] = len(layer1["symbols"])
        report["layers"]["1_symbols"] = layer1
    except Exception as e:
        report["layers"]["1_symbols"] = {"error": str(e)}

    if depth >= 1:
        try:
            diag_result = _call_tool("code_diagnostics", path=path)
            report["layers"]["2_diagnostics"] = _summarize_diagnostics(diag_result)
        except Exception as e:
            report["layers"]["2_diagnostics"] = {"error": str(e)}

    if depth >= 2:
        try:
            overview = _call_tool("code_overview", path=path, depth=1)
            report["layers"]["3_overview"] = overview if isinstance(overview, dict) else {"raw": overview}
        except Exception as e:
            report["layers"]["3_overview"] = {"error": str(e)}

        if symbol:
            report["layers"]["4_capsule"] = _build_capsule_layer(path, symbol)

    if depth >= 3:
        report["layers"]["5_call_hierarchy"] = _build_call_hierarchy_layer(path, symbol)

    if depth >= 4:
        report["layers"]["6_deadcode"] = _build_deadcode_layer(path)

    if depth >= 5:
        report["layers"]["7_complexity"] = _build_complexity_layer(path)

    report["summary"] = _build_summary(report["layers"])
    report["instruction"] = _build_report_instruction(report, path)

    if persist:
        _persist_analysis("analysis_inspect", args, report)

    # Optional: plan_follow Plan für tiefe Analysen
    if depth >= 4:
        _try_create_plan_follow_plan("analysis_inspect", path)

    return fmt_ok(report)


# ─── Helper: Capsule Layer ────────────────────────────────────────────


def _build_capsule_layer(path: str, symbol: str) -> dict:
    """Baut Layer 4: Symbol-Capsule mit Definition + Referenzen."""
    try:
        return {
            "definition": _call_tool("code_definition", path=path, symbol=symbol),
            "references_count": _call_tool("code_references", path=path, symbol=symbol, max_results=0),
        }
    except Exception as e:
        return {"error": str(e)}


# ─── Helper: Call Hierarchy Layer ─────────────────────────────────────


def _build_call_hierarchy_layer(path: str, symbol: str) -> dict:
    """Baut Layer 5: Call-Hierarchie."""
    try:
        if not symbol:
            return {"note": "symbol required for call hierarchy"}
        line = _find_symbol_line(path, symbol)
        if not line:
            return {"note": "symbol not found"}
        callees = _call_tool("code_callees", path=path, line=line)
        callers = _call_tool("code_callers", path=path, line=line)
        return {
            "callees": callees,
            "callers": callers,
        }
    except Exception as e:
        return {"error": str(e)}


# ─── Helper: Deadcode Layer ──────────────────────────────────────────


def _build_deadcode_layer(path: str) -> dict:
    """Baut Layer 6: Dead-Code-Analyse."""
    try:
        unused_imports = _call_tool("code_unused_finder", path=path, kinds=["imports"])
        unused_funcs = _call_tool("code_unused_finder", path=path, kinds=["functions"])
        return {
            "unused_imports": unused_imports,
            "unused_functions": unused_funcs,
        }
    except Exception as e:
        return {"error": str(e)}


# ─── Helper: Complexity Layer ──────────────────────────────────────────


def _build_complexity_layer(path: str) -> dict:
    """Baut Layer 7: Complexity-Analyse."""
    try:
        complexity = _call_tool("code_complexity", path=path, directory=True)
        metrics = _call_tool("code_metrics", path=path)
        return {
            "complexity": complexity,
            "metrics": metrics,
        }
    except Exception as e:
        return {"error": str(e)}


# ─── Helper: Summary ──────────────────────────────────────────────────


def _build_summary(layers: dict) -> dict:
    """Baut eine Zusammenfassung aus allen geladenen Layern."""
    summary = {}
    if "1_symbols" in layers and "count" in layers["1_symbols"]:
        summary["symbols"] = layers["1_symbols"]["count"]
    if "2_diagnostics" in layers:
        diag = layers["2_diagnostics"]
        summary["diagnostics"] = {
            "errors": diag.get("errors", 0),
            "warnings": diag.get("warnings", 0),
        }
    return summary


def _build_report_instruction(report: dict, path: str) -> str:
    """Baut die lesbare Instruction-Zeile aus dem Report."""
    s = report.get("summary", {})
    lines = [f"Analyse von {path} (Depth {report.get('depth', '?')})"]
    if "symbols" in s:
        lines.append(f"  {s['symbols']} Symbole gefunden")
    if "diagnostics" in s:
        d = s["diagnostics"]
        lines.append(f"  {d['errors']} Errors, {d['warnings']} Warnings")
    return "\n".join(lines)
