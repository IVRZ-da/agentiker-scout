"""analysis_tools — Analyse-Tools (Phase C).

Tools:
  - analysis_inspect: Mehrstufige Code-Analyse (depth 1-5)
  - analysis_architecture: Architektur-Analyse mit cycle_detector + dependency_graph
  - analysis_deadcode: Dead-Code-Scan mit unused_finder
  - analysis_report: Report-Generierung + Honcho-Persistenz
  - analysis_performance: Performance-Bottleneck-Analyse
  - analysis_security: Security-Scan mit Error-Handler + Vulnerability-Patterns
  - analysis_ask: KI-gestützte Codebase-Fragen
  - analysis_diff: Vergleich zweier Analyse-Ergebnisse
  - analysis_trend: Trend-Analyse über Zeit
  - analysis_watch: Cron-basierte Code-Überwachung
  - analysis_graph: Mermaid-Diagramm aus Analyse-Report
  - analysis_ui_gap: UI Gap Analyse — erkennt UI-Layer, extrahiert Routen, identifiziert Coverage-Gaps

Importiert Basis-Funktionen aus tools/base.py und Schemas aus tools/schemas.py.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

from scout._fmt import fmt_err, fmt_ok

from .tools.base import (
    _call_tool,
    _clear_symbol_line_cache,
    _find_symbol_line,
    _parallel_dispatch,
    _persist_analysis,
    _validate_and_resolve_path,
    _validate_path,
)
from .tools.schemas import (
    ANALYSIS_ARCHITECTURE_SCHEMA,
    ANALYSIS_ASK_SCHEMA,
    ANALYSIS_DEADCODE_SCHEMA,
    ANALYSIS_DIFF_SCHEMA,
    ANALYSIS_GRAPH_SCHEMA,
    ANALYSIS_INSPECT_SCHEMA,
    ANALYSIS_PATTERN_DISCOVER_SCHEMA,
    ANALYSIS_PERFORMANCE_SCHEMA,
    ANALYSIS_REPORT_SCHEMA,
    ANALYSIS_SECURITY_SCHEMA,
    ANALYSIS_TREND_SCHEMA,
    ANALYSIS_UI_GAP_SCHEMA,
    ANALYSIS_WATCH_SCHEMA,
)
from .tools.ui_gap import analysis_ui_gap_tool

logger = logging.getLogger("analysis")


def _summarize_symbols(symbols_result: Any) -> list[dict]:
    """Extrahiert eine kompakte Symbol-Liste aus code_symbols-Output.

    Args:
        symbols_result: Rückgabe von _call_tool("code_symbols", ...)

    Returns:
        Liste von Dicts mit name/kind/line.
    """
    if not symbols_result:
        return []
    if isinstance(symbols_result, dict):
        raw = symbols_result.get("symbols", symbols_result)
    elif isinstance(symbols_result, list):
        raw = symbols_result
    else:
        return []
    result = []
    for sym in (raw or []):
        if isinstance(sym, dict) and "name" in sym:
            result.append({
                "name": sym.get("name", "?"),
                "kind": sym.get("kind", "?"),
                "line": sym.get("line", 0),
            })
    return result


def _summarize_diagnostics(diag_result: Any) -> dict:
    """Extrahiert eine kompakte Diagnostic-Übersicht aus code_diagnostics-Output.

    Args:
        diag_result: Rückgabe von _call_tool("code_diagnostics", ...)

    Returns:
        Dict mit counts und top_messages.
    """
    if not diag_result:
        return {"errors": 0, "warnings": 0, "info": 0, "top_messages": []}
    if isinstance(diag_result, dict):
        raw = diag_result.get("diagnostics", [])
        if isinstance(raw, dict):
            raw = [raw]
        elif not isinstance(raw, list):
            raw = []
        errors = diag_result.get("errors", 0)
        warnings = diag_result.get("warnings", 0)
        info = diag_result.get("info", 0)
        if not errors and not warnings and not info:
            errors = sum(1 for d in raw if d.get("severity") == 1) if raw else 0
            warnings = sum(1 for d in raw if d.get("severity") == 2) if raw else 0
            info = sum(1 for d in raw if d.get("severity") == 3) if raw else 0
    elif isinstance(diag_result, list):
        raw = diag_result
        errors = sum(1 for d in raw if d.get("severity") == 1)
        warnings = sum(1 for d in raw if d.get("severity") == 2)
        info = sum(1 for d in raw if d.get("severity") == 3)
    else:
        return {"errors": 0, "warnings": 0, "info": 0, "top_messages": []}

    # Top-Fehlermeldungen (max 3)
    top_messages = []
    for d in (raw or []):
        if isinstance(d, dict) and "message" in d:
            top_messages.append(d["message"][:120])
        if len(top_messages) >= 3:
            break

    return {
        "errors": errors,
        "warnings": warnings,
        "info": info,
        "top_messages": top_messages,
    }


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
    layer1 = {}
    try:
        symbols = _call_tool("code_symbols", path=path)
        if symbols and not isinstance(symbols, dict) or (isinstance(symbols, dict) and "error" not in symbols):
            layer1["symbols"] = _summarize_symbols(symbols)
    except Exception as e:
        layer1["symbol_error"] = str(e)

    try:
        overview = _call_tool("code_overview", path=path, depth=1)
        if overview:
            layer1["overview"] = overview
    except Exception as e:
        layer1["overview_error"] = str(e)

    try:
        diagnostics = _call_tool("code_diagnostics", path=path)
        if diagnostics:
            layer1["diagnostics"] = _summarize_diagnostics(diagnostics)
    except Exception as e:
        layer1["diagnostics_error"] = str(e)

    report["layers"]["1_basics"] = layer1
    report["summary"]["symbol_count"] = len(layer1.get("symbols", []))

    # Layer 2: Navigation
    if depth >= 2 and symbol:
        layer2 = {}
        try:
            capsule = _call_tool("code_capsule", path=path, line=_find_symbol_line(path, symbol))
            if capsule:
                layer2["capsule"] = capsule
        except Exception as e:
            layer2["capsule_error"] = str(e)

        try:
            callers = _call_tool("code_callers", path=path, line=_find_symbol_line(path, symbol), group_by_file=True)
            if callers:
                layer2["callers"] = len(json.dumps(callers)) if not isinstance(callers, int) else callers
        except Exception as e:
            layer2["callers_error"] = str(e)

        try:
            callees = _call_tool("code_callees", path=path, line=_find_symbol_line(path, symbol))
            if callees:
                layer2["callees"] = len(json.dumps(callees)) if not isinstance(callees, int) else callees
        except Exception as e:
            layer2["callees_error"] = str(e)

        report["layers"]["2_navigation"] = layer2

    # Layer 3: Hierarchien
    if depth >= 3 and symbol:
        layer3 = {}
        try:
            hierarchy = _call_tool("code_call_hierarchy", path=path, line=_find_symbol_line(path, symbol), max_depth=2)
            if hierarchy:
                layer3["call_hierarchy"] = hierarchy
        except Exception as e:
            layer3["call_hierarchy_error"] = str(e)

        try:
            highlight = _call_tool("code_highlight", path=path, line=_find_symbol_line(path, symbol))
            if highlight:
                layer3["highlight_count"] = len(json.dumps(highlight)) if not isinstance(highlight, int) else highlight
        except Exception as e:
            layer3["highlight_error"] = str(e)

        report["layers"]["3_hierarchy"] = layer3

    # Layer 4: Graphen + Zyklen (parallel dispatchen)
    if depth >= 4:
        layer4_calls = []
        if os.path.isdir(path):
            layer4_calls.append({"key": "cycles", "name": "code_cycle_detector", "kwargs": {"path": path}})
        layer4_calls.append({"key": "dependency_graph", "name": "code_dependency_graph", "kwargs": {"path": path, "format": "text"}})
        layer4_calls.append({"key": "hot_paths", "name": "code_hot_paths", "kwargs": {"path": path, "top_n": 5}})
        layer4 = _parallel_dispatch(layer4_calls)
        report["layers"]["4_graphs"] = layer4

    # Layer 5: Tiefenanalyse (parallel dispatchen)
    if depth >= 5:
        layer5_calls = []
        layer5_calls.append({"key": "unused", "name": "code_unused_finder", "kwargs": {"path": path}})
        if symbol:
            sym_line = _find_symbol_line(path, symbol)
            layer5_calls.append({"key": "complexity", "name": "code_complexity", "kwargs": {"path": path, "function": symbol}})
            layer5_calls.append({"key": "blast_radius", "name": "code_blast_radius", "kwargs": {"path": path, "line": sym_line}})
        layer5 = _parallel_dispatch(layer5_calls)
        report["layers"]["5_deep"] = layer5

    # Summary
    report["summary"]["layers_executed"] = depth
    report["summary"]["tools_called"] = 0
    for layer_data in report["layers"].values():
        if isinstance(layer_data, dict):
            report["summary"]["tools_called"] += sum(
                1 for k in layer_data.keys() if not k.endswith("_error")
            )

    # Persistieren
    if persist:
        try:
            _persist_analysis("code", report, {
                "path": path,
                "symbol": symbol or None,
                "depth": depth,
                "tools_called": report["summary"]["tools_called"],
                "symbol_count": report["summary"]["symbol_count"],
            })
        except Exception as e:
            logger.info("analysis persist skipped — Honcho not available: %s", e)

    # plan_follow Plan erstellen (lose Kopplung via Registry)
    _try_create_plan_follow_plan("analysis_inspect", path)

    return fmt_ok(report)


# ---------------------------------------------------------------------------
# analysis_report Tool
# ---------------------------------------------------------------------------

def analysis_report_tool(args: dict, **kwargs) -> str:
    """Generiert einen strukturierten Analyse-Report und persistiert in Honcho."""
    scope = args.get("scope", "")
    findings = args.get("findings", {})
    recommendations = args.get("recommendations", [])
    persist = args.get("persist", True)

    report = {
        "tool": "analysis_report",
        "scope": scope,
        "findings": findings,
        "recommendations": recommendations,
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "finding_count": len(findings),
            "recommendation_count": len(recommendations),
        },
    }

    if persist:
        try:
            _persist_analysis("report", report, {
                "scope": scope,
                "findings": findings,
                "recommendations": recommendations,
            })
        except Exception as e:
            logger.info("analysis persist skipped — Honcho not available: %s", e)

    return fmt_ok(report)


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
        from .tools.base import _run_shared_pattern_scans
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
            from .tools.base import _run_shared_pattern_scans
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



# ---------------------------------------------------------------------------
# analysis_diff Tool
# ---------------------------------------------------------------------------

# ANALYSIS_DIFF_SCHEMA imported from tools/schemas.py


def _diff_value(key: str, val_a: Any, val_b: Any) -> Dict[str, Any]:
    """Vergleicht zwei Werte und gibt einen Diff-Eintrag zurück."""
    if val_a == val_b:
        return {"status": "unchanged", "key": key, "value": val_a}
    return {
        "status": "changed",
        "key": key,
        "before": val_a,
        "after": val_b,
    }


def _diff_dicts(dict_a: Dict, dict_b: Dict, prefix: str = "") -> List[Dict[str, Any]]:
    """Vergleicht zwei Dictionaries rekursiv."""
    changes = []
    all_keys = set(dict_a.keys()) | set(dict_b.keys())

    for key in sorted(all_keys):
        full_key = f"{prefix}.{key}" if prefix else key
        va = dict_a.get(key)
        vb = dict_b.get(key)

        if key not in dict_a:
            changes.append({"status": "added", "key": full_key, "value": vb})
        elif key not in dict_b:
            changes.append({"status": "removed", "key": full_key, "value": va})
        elif isinstance(va, dict) and isinstance(vb, dict):
            changes.extend(_diff_dicts(va, vb, full_key))
        elif va != vb:
            changes.append(_diff_value(full_key, va, vb))

    return changes


def analysis_diff_tool(args: dict, **kwargs) -> str:
    """Vergleicht zwei Analyse-Ergebnisse und zeigt Unterschiede."""
    report_a = args.get("report_a", {})
    report_b = args.get("report_b", {})
    scope = args.get("scope", "")
    fmt = args.get("format", "text")

    if not report_a or not report_b:
        return fmt_err("Both report_a and report_b are required")

    diff_result: Dict[str, Any] = {
        "tool": "analysis_diff",
        "scope": scope or f"{report_a.get('tool', '?')} vs {report_b.get('tool', '?')}",
        "format": fmt,
        "changes": [],
        "summary": {},
    }

    # Top-Level Eigenschaften vergleichen
    for key in ("tool", "path", "depth", "symbol"):
        if key in report_a or key in report_b:
            diff_result["changes"].append(_diff_value(
                key,
                report_a.get(key),
                report_b.get(key),
            ))

    # Summary vergleichen
    summary_a = report_a.get("summary", {})
    summary_b = report_b.get("summary", {})
    if summary_a or summary_b:
        diff_result["changes"].extend(_diff_dicts(
            summary_a, summary_b, "summary"
        ))

    # Findings vergleichen (für architecure/deadcode)
    findings_a = report_a.get("findings", {}) or report_a.get("sections", {})
    findings_b = report_b.get("findings", {}) or report_b.get("sections", {})
    if findings_a or findings_b:
        diff_result["changes"].extend(_diff_dicts(
            findings_a, findings_b, "findings"
        ))

    # Layers vergleichen (für inspect)
    layers_a = report_a.get("layers", {})
    layers_b = report_b.get("layers", {})
    if layers_a or layers_b:
        diff_result["changes"].extend(_diff_dicts(
            layers_a, layers_b, "layers"
        ))

    # Alle anderen Top-Level Keys vergleichen (added/removed)
    compared_keys = {"tool", "path", "depth", "symbol", "summary", "findings", "sections", "layers"}
    other_keys = set(report_a.keys()) | set(report_b.keys())
    other_keys -= compared_keys
    if other_keys:
        other_a = {k: report_a.get(k) for k in other_keys if k in report_a}
        other_b = {k: report_b.get(k) for k in other_keys if k in report_b}
        diff_result["changes"].extend(_diff_dicts(other_a, other_b, ""))

    # Summary bauen
    changed = [c for c in diff_result["changes"] if c["status"] == "changed"]
    added = [c for c in diff_result["changes"] if c["status"] == "added"]
    removed = [c for c in diff_result["changes"] if c["status"] == "removed"]
    diff_result["summary"] = {
        "total_differences": len(diff_result["changes"]),
        "changed": len(changed),
        "added": len(added),
        "removed": len(removed),
        "unchanged": len([c for c in diff_result["changes"] if c["status"] == "unchanged"]),
    }

    # Persistieren (via Log, kein Honcho — das sind temporäre Vergleiche)
    logger.info(
        "analysis diff: %s | %d differences (%d changed, %d added, %d removed)",
        diff_result["scope"],
        diff_result["summary"]["total_differences"],
        diff_result["summary"]["changed"],
        diff_result["summary"]["added"],
        diff_result["summary"]["removed"],
    )

    return fmt_ok(diff_result)


# ---------------------------------------------------------------------------
# analysis_trend Tool
# ---------------------------------------------------------------------------

# ANALYSIS_TREND_SCHEMA imported from tools/schemas.py


def analysis_trend_tool(args: dict, **kwargs) -> str:
    """Trend-Analyse über Honcho-Historie."""
    scope = args.get("scope", "")
    intent = args.get("intent", "")
    days = min(args.get("days", 30), 365)

    report: Dict[str, Any] = {
        "tool": "analysis_trend",
        "scope": scope or "all",
        "intent": intent or "all",
        "days": days,
        "trends": {},
        "summary": {},
    }

    # Honcho nach Analyse-Historie durchsuchen
    try:
        from tools.registry import registry

        query_parts = ["analysis"]
        if intent:
            query_parts.append(f"intent={intent}")
        if scope:
            query_parts.append(scope)

        result = registry.dispatch("honcho_search", {
            "query": " ".join(query_parts),
            "max_tokens": 2000,
        })

        if result:
            text = str(result)
            report["raw_history"] = text[:500]
        else:
            report["warning"] = "No analysis history found in Honcho"

    except Exception as e:
        report["warning"] = f"Honcho query failed: {e}"

    report["summary"] = {
        "history_available": "raw_history" in report,
        "note": "Full trend analysis requires multiple analysis_inspect/deadcode runs over time.",
    }

    return fmt_ok(report)


# ---------------------------------------------------------------------------
# analysis_watch Tool
# ---------------------------------------------------------------------------

# ANALYSIS_WATCH_SCHEMA imported from tools/schemas.py


def analysis_watch_tool(args: dict, **kwargs) -> str:
    """Erstellt oder verwaltet Analyse-Cron-Jobs."""
    path = args.get("path", "")
    frequency = args.get("frequency", "daily")
    depth = min(args.get("depth", 2), 5)
    action = args.get("action", "create")
    name = args.get("name", "")

    # Path-Validierung
    path_error, resolved_path = _validate_and_resolve_path(path)
    if path_error:
        return fmt_err(f"{path_error} (path: {path})")
    if not os.path.exists(resolved_path):
        return fmt_err(f"Path not found: {resolved_path}")

    if action == "list":
        return fmt_ok({
            "tool": "analysis_watch",
            "action": "list",
            "note": "Use `hermes cron list` to see active analysis watches.",
        })

    if action == "remove":
        if not name:
            return fmt_err("name is required for remove action")
        return fmt_ok({
            "tool": "analysis_watch",
            "action": "remove",
            "name": name,
            "note": f"Use `hermes cron remove {name}` to stop the watch.",
        })

    # Map frequency to cron schedule
    schedule_map = {
        "hourly": "0 * * * *",
        "daily": "0 6 * * *",
        "weekly": "0 6 * * 1",
    }
    schedule = schedule_map.get(frequency, frequency)

    # Generate watch name
    watch_name = name or f"analysis-watch-{os.path.basename(path)}"

    watch_plan = {
        "tool": "analysis_watch",
        "action": "create",
        "name": watch_name,
        "path": resolved_path,
        "frequency": frequency,
        "schedule": schedule,
        "depth": depth,
        "status": "planned",
        "setup_instructions": (
            f"To create this watch, run:\n"
            f"  hermes cron create --name '{watch_name}' "
            f"--schedule '{schedule}' "
            f"--prompt 'Run analysis_inspect on {resolved_path} at depth {depth} "
            f"and report any significant changes.'"
        ),
    }

    return fmt_ok(watch_plan)


# ---------------------------------------------------------------------------
# analysis_graph Tool
# ---------------------------------------------------------------------------

# ANALYSIS_GRAPH_SCHEMA imported from tools/schemas.py


def _mermaid_from_dependency(data: Any) -> str:
    """Generiert einen Mermaid-Flowchart aus Dependency-Daten."""
    lines = ["```mermaid", "flowchart LR"]

    if isinstance(data, dict):
        # Versuche Graph-Einträge zu extrahieren
        for key, value in data.items():
            if isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, (list, tuple)):
                        a, b = item[0], item[-1]
                        lines.append(f"  {a} --> {b}")
                    elif isinstance(item, str):
                        lines.append(f"  {item}")
    elif isinstance(data, str):
        # Plain text — Graph-of-Things format
        for line in data.strip().split("\n"):
            line = line.strip()
            if "->" in line:
                parts = line.split("->")
                a = parts[0].strip().replace(" ", "_")
                b = parts[-1].strip().replace(" ", "_")
                lines.append(f"  {a} --> {b}")

    lines.append("```")
    return "\n".join(lines) if len(lines) > 3 else "```mermaid\nflowchart LR\n  no_data[No dependency data to graph]\n```"


def _mermaid_from_cycles(data: Any) -> str:
    """Generiert Mermaid-Diagramm aus Cycle-Daten."""
    lines = ["```mermaid", "flowchart LR"]

    if isinstance(data, dict):
        cycles = data.get("cycles", data.get("data", []))
        if isinstance(cycles, list):
            for i, cycle in enumerate(cycles[:5]):
                if isinstance(cycle, (list, tuple)) and len(cycle) >= 2:
                    style = f"style C{i} fill:#ffcccc,stroke:#ff0000"
                    cycle_label = f"subgraph C{i} [Cycle {i+1}]"
                    lines.append(cycle_label)
                    for j in range(len(cycle) - 1):
                        lines.append(f"  {cycle[j]}_{i} --> {cycle[j+1]}_{i}")
                    lines.append(f"  {cycle[-1]}_{i} --> {cycle[0]}_{i}")
                    lines.append("end")
                    lines.append(style)

    lines.append("```")
    return "\n".join(lines) if len(lines) > 3 else "```mermaid\nflowchart LR\n  no_cycles[No cycles detected]\n```"


def analysis_graph_tool(args: dict, **kwargs) -> str:
    """Generiert ein Mermaid-Diagramm aus Analyse-Ergebnissen."""
    report = args.get("report", {})
    graph_type = args.get("type", "dependency")

    if not report:
        return fmt_err("report is required")

    result: Dict[str, Any] = {
        "tool": "analysis_graph",
        "type": graph_type,
        "report_tool": report.get("tool", "unknown"),
        "graph": "",
    }

    # Beste Daten aus dem Report extrahieren
    sections = report.get("sections", report.get("layers", report.get("findings", report)))

    if graph_type == "dependency":
        dep_data = (
            sections.get("dependency_graph") or
            sections.get("4_graphs", {}).get("dependency_graph") or
            report.get("dependency_graph") or
            {}
        )
        result["graph"] = _mermaid_from_dependency(dep_data)
        result["note"] = "Mermaid flowchart of module dependencies."

    elif graph_type == "cycles":
        cycle_data = (
            sections.get("cycles") or
            sections.get("4_graphs", {}).get("cycles") or
            report.get("cycles") or
            {}
        )
        result["graph"] = _mermaid_from_cycles(cycle_data)
        result["note"] = "Mermaid diagram showing circular dependencies."

    elif graph_type == "summary":
        summary = report.get("summary", {})
        lines = ["```mermaid", "flowchart LR"]
        for key, value in summary.items():
            if isinstance(value, (int, float, str)):
                lines.append(f"  {key}({key}: {value})")
        lines.append("```")
        result["graph"] = "\n".join(lines)
        result["note"] = "Mermaid overview of analysis summary."

    return fmt_ok(result)


# ---------------------------------------------------------------------------
# analysis_pattern_discover Tool (P4)
# ---------------------------------------------------------------------------


def analysis_pattern_discover_tool(args: dict, **kwargs) -> str:
    """Discover unregistered code patterns that look like bugs."""
    from scout._fmt import fmt_err, fmt_ok

    path = args.get("path", "")
    scan_language = args.get("scan_language", "")
    min_frequency = args.get("min_frequency", 3)

    error = _validate_path(path)
    if error:
        return fmt_err(error)

    path_error, resolved_path = _validate_and_resolve_path(path)
    if path_error:
        return fmt_err(f"{path_error} (path: {path})")
    path = resolved_path

    report: Dict[str, Any] = {
        "path": path,
        "candidates": [],
        "summary": {"patterns_scanned": 0, "patterns_found": 0, "gaps_found": 0},
    }

    try:
        # 1. Vorhandene Shared Patterns laden
        from scout.shared.patterns import get_patterns_for_analysis
        existing = get_patterns_for_analysis()
        existing_queries = set()
        for p in existing:
            query = p.get("scan_query", "")
            if query:
                existing_queries.add(query.lower())

        report["summary"]["patterns_scanned"] = len(existing)

        # 2. Statistische Analyse: Häufige Code-Muster erkennen
        candidates = []

        # 2a. Python: try/except Blöcke ohne passende Patterns
        if not scan_language or scan_language == "python":
            _discover_python_patterns(path, candidates, existing_queries, min_frequency)

        # 2b. TypeScript/JavaScript: Häufige Debug/Logging Muster
        if not scan_language or scan_language in ("typescript", "javascript"):
            _discover_ts_patterns(path, candidates, existing_queries, min_frequency)

        # 2c. Go: Häufige Fehlerbehandlungs-Muster
        if not scan_language or scan_language == "go":
            _discover_go_patterns(path, candidates, existing_queries, min_frequency)

        # 3. Confidence-Scores berechnen und sortieren
        for c in candidates:
            score = 0.5
            # Höhere Frequenz = höhere Confidence
            if c.get("frequency", 0) > 10:
                score += 0.3
            elif c.get("frequency", 0) > 5:
                score += 0.15
            # Mit Beschreibung = höhere Confidence
            if c.get("description"):
                score += 0.1
            # Fix-Vorschlag = höhere Confidence
            if c.get("suggested_fix"):
                score += 0.1
            c["confidence"] = round(min(score, 1.0), 2)

        candidates.sort(key=lambda c: c.get("confidence", 0), reverse=True)

        # 4. Limit auf Top-10
        report["candidates"] = candidates[:10]
        report["summary"]["gaps_found"] = len(candidates)
        report["summary"]["patterns_found"] = len(
            [c for c in candidates if c.get("confidence", 0) > 0.6]
        )

    except Exception as e:
        logger.warning("pattern discovery error: %s", e)
        report["summary"]["error"] = str(e)

    return fmt_ok(report)


# ---------------------------------------------------------------------------
# Pattern Discovery Helfer
# ---------------------------------------------------------------------------


def _discover_python_patterns(
    path: str,
    candidates: list,
    existing_queries: set,
    min_frequency: int,
) -> None:
    """Findet ungedeckte Python-spezifische Patterns."""
    import subprocess

    # Silent catch (except: pass) — prüfen ob schon gedeckt
    q1 = "except.*?:\\s*pass"
    if q1 not in existing_queries:
        try:
            r = subprocess.run(
                ["grep", "-rn", q1, path, "--include=*.py"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                count = len(r.stdout.strip().split("\n"))
                if count >= min_frequency:
                    candidates.append({
                        "suggested_name": "Silent Catch (Python)",
                        "category": "code-quality",
                        "severity": "P2",
                        "scan_type": "grep",
                        "scan_query": q1,
                        "scan_file_glob": "**/*.py",
                        "scan_language": "python",
                        "frequency": count,
                        "description": "Leeres except: pass ohne Logging. Fehler werden verschluckt.",
                        "suggested_fix": "Im except-Block mindestens logger.warning() verwenden.",
                    })
        except Exception:
            pass

    # Mutable Default Args
    q2 = r"def \w+\([^)]*=\{\s*\}|def \w+\([^)]*=\[\s*\]"
    if q2 not in existing_queries:
        try:
            r = subprocess.run(
                ["grep", "-rn", "-E", q2, path, "--include=*.py"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                count = len(r.stdout.strip().split("\n"))
                if count >= min_frequency:
                    candidates.append({
                        "suggested_name": "Mutable Default Arguments",
                        "category": "code-quality",
                        "severity": "P2",
                        "scan_type": "grep",
                        "scan_query": q2,
                        "scan_file_glob": "**/*.py",
                        "scan_language": "python",
                        "frequency": count,
                        "description": "Mutable Default Args (list/dict) werden zwischen Aufrufen geteilt.",
                        "suggested_fix": "Default auf None setzen und im Body initialisieren.",
                    })
        except Exception:
            pass


def _discover_ts_patterns(
    path: str,
    candidates: list,
    existing_queries: set,
    min_frequency: int,
) -> None:
    """Findet ungedeckte TypeScript/JavaScript Patterns."""
    import subprocess
    ts_glob = "--include=*.ts"
    tsx_glob = "--include=*.tsx"

    # console.log ohne passende Patterns prüfen
    q1 = r"console\.(log|warn|error)\("
    if q1 not in existing_queries:
        try:
            r = subprocess.run(
                ["grep", "-rn", "-E", q1, path, ts_glob, tsx_glob, "--include=*.js", "--include=*.jsx"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                count = len(r.stdout.strip().split("\n"))
                if count >= min_frequency:
                    candidates.append({
                        "suggested_name": "Console Log",
                        "category": "code-quality",
                        "severity": "P3",
                        "scan_type": "grep",
                        "scan_query": q1,
                        "scan_file_glob": "**/*.{ts,tsx,js,jsx}",
                        "scan_language": "typescript",
                        "frequency": count,
                        "description": "console.log/warn/error in Produktionscode — Debug-Überreste.",
                        "suggested_fix": "Durch logger.debug() ersetzen oder entfernen.",
                    })
        except Exception:
            pass

    # any statt unknown
    q2 = r":\s*any\b"
    if q2 not in existing_queries:
        try:
            r = subprocess.run(
                ["grep", "-rn", "-E", q2, path, ts_glob, tsx_glob],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                count = len(r.stdout.strip().split("\n"))
                if count >= min_frequency:
                    candidates.append({
                        "suggested_name": "TypeScript 'any' statt 'unknown'",
                        "category": "typescript",
                        "severity": "P3",
                        "scan_type": "grep",
                        "scan_query": q2,
                        "scan_file_glob": "**/*.{ts,tsx}",
                        "scan_language": "typescript",
                        "frequency": count,
                        "description": ": any deaktiviert Type Checking. unknown ist type-safe.",
                        "suggested_fix": ": any durch : unknown ersetzen und Typ-Guards nutzen.",
                    })
        except Exception:
            pass

    # force-dynamic in Next.js
    q3 = r"export\s+(const\s+)?dynamic\s*=\s*['\"]force"
    if q3 not in existing_queries:
        try:
            r = subprocess.run(
                ["grep", "-rn", "-E", q3, path, ts_glob, tsx_glob],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                count = len(r.stdout.strip().split("\n"))
                if count >= min_frequency:
                    candidates.append({
                        "suggested_name": "force-dynamic Export",
                        "category": "code-quality",
                        "severity": "P3",
                        "scan_type": "grep",
                        "scan_query": q3,
                        "scan_file_glob": "**/*.{ts,tsx}",
                        "scan_language": "typescript",
                        "frequency": count,
                        "description": "force-dynamic deaktiviert Caching. Nur nutzen wenn nötig.",
                        "suggested_fix": "Auf 'auto' setzen oder Route Segment Config prüfen.",
                    })
        except Exception:
            pass


def _discover_go_patterns(
    path: str,
    candidates: list,
    existing_queries: set,
    min_frequency: int,
) -> None:
    """Findet ungedeckte Go Patterns."""
    import subprocess

    q1 = r"if err\s*!=\s*nil\s*\{\s*$"
    if q1 not in existing_queries:
        try:
            r = subprocess.run(
                ["grep", "-rn", "-E", q1, path, "--include=*.go"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                count = len(r.stdout.strip().split("\n"))
                if count >= min_frequency:
                    candidates.append({
                        "suggested_name": "Error ohne Handling",
                        "category": "code-quality",
                        "severity": "P2",
                        "scan_type": "grep",
                        "scan_query": q1,
                        "scan_file_glob": "**/*.go",
                        "scan_language": "go",
                        "frequency": count,
                        "description": "if err != nil { } — Error wird ignoriert (leerer Block).",
                        "suggested_fix": "Error immer loggen oder returned werden.",
                    })
        except Exception:
            pass


# ---------------------------------------------------------------------------
# ─── analysis_framework Tool ─────────────────────────────────────────

ANALYSIS_FRAMEWORK_SCHEMA = {
    "name": "analysis_framework",
    "description": "Zeigt das Framework-Profil eines Projekts an. Erkennt automatisch "
                   "Technologie-Stack (Medusa, Next.js, React, Go, Docker, etc.) "
                   "mit Confidence-Scoring und Evidence-Tracking.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absoluter Pfad zum Projekt-Root.",
            },
            "fast": {
                "type": "boolean",
                "description": "Wenn True, nur High-Confidence-Marker scannen (schneller).",
                "default": False,
            },
        },
        "required": ["path"],
    },
}


def analysis_framework_tool(args: dict, **kwargs) -> str:
    """Handler für analysis_framework — Framework-Profil anzeigen."""
    from scout._fmt import fmt_err, fmt_ok

    path = args.get("path", "").strip()
    if not path:
        return fmt_err("path ist erforderlich")

    fast = args.get("fast", False)

    try:
        from shared.framework_detector import (
            FrameworkDetector,
            format_profile_summary,
        )
        detector = FrameworkDetector(path)
        profile = detector.detect_fast() if fast else detector.detect()
        profile_dict = profile.to_dict()
        summary = format_profile_summary(profile_dict)

        return fmt_ok({
            "path": path,
            "profile": profile_dict,
            "summary": summary,
            "instruction": (
                f"Framework-Profil für {path}:\n{summary}"
            ),
        })
    except ValueError as e:
        return fmt_err(str(e))
    except Exception as e:
        return fmt_err(f"Framework-Analyse fehlgeschlagen: {e}")


# ─── Schema-Registry (für __init__.py)
# ---------------------------------------------------------------------------

TOOL_HANDLERS = {
    "analysis_inspect": (ANALYSIS_INSPECT_SCHEMA, analysis_inspect_tool),
    "analysis_report": (ANALYSIS_REPORT_SCHEMA, analysis_report_tool),
    "analysis_architecture": (ANALYSIS_ARCHITECTURE_SCHEMA, analysis_architecture_tool),
    "analysis_deadcode": (ANALYSIS_DEADCODE_SCHEMA, analysis_deadcode_tool),
    "analysis_performance": (ANALYSIS_PERFORMANCE_SCHEMA, analysis_performance_tool),
    "analysis_security": (ANALYSIS_SECURITY_SCHEMA, analysis_security_tool),
    "analysis_ask": (ANALYSIS_ASK_SCHEMA, analysis_ask_tool),
    "analysis_diff": (ANALYSIS_DIFF_SCHEMA, analysis_diff_tool),
    "analysis_trend": (ANALYSIS_TREND_SCHEMA, analysis_trend_tool),
    "analysis_watch": (ANALYSIS_WATCH_SCHEMA, analysis_watch_tool),
    "analysis_graph": (ANALYSIS_GRAPH_SCHEMA, analysis_graph_tool),
    "analysis_ui_gap": (ANALYSIS_UI_GAP_SCHEMA, analysis_ui_gap_tool),
    "analysis_pattern_discover": (ANALYSIS_PATTERN_DISCOVER_SCHEMA, analysis_pattern_discover_tool),
    "analysis_framework": (ANALYSIS_FRAMEWORK_SCHEMA, analysis_framework_tool),
}


def _try_create_plan_follow_plan(tool_name: str, path: str) -> dict | None:
    """
    Erzeugt einen Plan im plan_follow Plugin via Registry (lose Kopplung).

    Aufruf in analysis_inspect/architecture/deadcode Tools vor dem return.
    Schlägt silent fehl wenn plan_follow nicht geladen ist.
    """
    try:
        from tools.registry import registry

        entry = registry.get_entry("plan_create")
        if entry is None:
            return None  # plan_follow nicht geladen

        handler = getattr(entry, "handler", None)
        if not callable(handler):
            return None

        goal = f"Analyse: {tool_name} ({path})"
        result = handler({
            "goal": goal,
            "template": "analysis",
        })

        if isinstance(result, str):
            parsed = json.loads(result)
            return parsed if isinstance(parsed, dict) else None
        return result
    except ImportError:
        return None
    except Exception as e:
        logger.info("plan_follow integration skipped: %s", e)
        return None



def _try_create_bughunt_finding(severity: str, title: str, details: dict) -> dict | None:
    """Erzeugt ein Bug-Hunt Finding via Registry (lose Kopplung).

    Aufruf in analysis_deadcode/architecture wenn Findings existieren.
    Schlägt silent fehl wenn bughunt nicht geladen ist.
    """
    try:
        from tools.registry import registry
        entry = registry.get_entry("bug_hunt_finding")
        if entry is None:
            return None
        handler = getattr(entry, "handler", None)
        if not callable(handler):
            return None
        result = handler({
            "title": title,
            "severity": severity,
            "details": details,
        })
        if isinstance(result, str):
            parsed = json.loads(result)
            return parsed if isinstance(parsed, dict) else None
        return result
    except ImportError:
        return None
    except Exception as e:
        logger.info("bughunt integration skipped: %s", e)
        return None
