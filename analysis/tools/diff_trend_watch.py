"""diff_trend_watch.py — analysis_diff/trend/watch Tool-Handler.

Extracted from analysis_tools.py (Phase C) for modularity.
Enthält Diff-Vergleichs-, Trend-Analyse- und Watch-Tools.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from scout._fmt import fmt_err, fmt_ok

from .base import _validate_and_resolve_path

logger = logging.getLogger("analysis")


# ---------------------------------------------------------------------------
# analysis_diff Tool
# ---------------------------------------------------------------------------


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
# analysis_diff_analysis Tool
# ---------------------------------------------------------------------------


def analysis_diff_analysis_tool(args: dict, **kwargs) -> str:
    """Git-Diff mit Impact-Analyse zwischen zwei Refs.

    Nutzt code_diff_analysis + code_impact + code_git_diff_file.
    """
    from .base import _call_tool

    path = args.get("path", "")
    base = args.get("base", "main")
    head = args.get("head", "HEAD")
    max_files = min(args.get("max_files", 5), 20)

    path_error, resolved_path = _validate_and_resolve_path(path)
    if path_error:
        return fmt_err(f"{path_error} (path: {path})")
    path = resolved_path

    if not os.path.isdir(path):
        return fmt_err(f"Not a directory: {path}")

    result: dict[str, Any] = {
        "path": path,
        "base": base,
        "head": head,
        "sections": {},
    }

    # 1. code_diff_analysis
    try:
        diff = _call_tool("code_diff_analysis", path=path, base=base, head=head, max_files=max_files)
        if diff and isinstance(diff, dict):
            result["sections"]["diff_overview"] = {
                k: diff.get(k) for k in
                ("changed_files", "insertions", "deletions", "changed_functions")
                if k in diff
            }
            # Changed functions + complexity delta
            funcs = diff.get("changed_functions", diff.get("functions", []))
            if isinstance(funcs, list):
                result["sections"]["changed_functions"] = [
                    {"name": f.get("name", "?"), "complexity_delta": f.get("complexity_delta", 0)}
                    for f in funcs[:max_files]
                ]
    except Exception as e:
        logger.debug("code_diff_analysis skipped: %s", e)

    # 2. Uncommitted diff
    try:
        dirty = _call_tool("code_git_diff_file", path=path)
        if dirty and isinstance(dirty, dict):
            result["sections"]["uncommitted"] = {
                "files_changed": dirty.get("changed_files", dirty.get("summary", {}).get("files", 0)),
                "diff_present": bool(dirty.get("diff", "")),
            }
    except Exception as e:
        logger.debug("code_git_diff_file skipped: %s", e)

    parts = [f"📊 Diff-Analyse: {base} → {head}"]
    overview = result.get("sections", {}).get("diff_overview", {})
    if overview:
        parts.append(f"  {overview.get('changed_files', '?')} Dateien geändert")
        parts.append(f"  +{overview.get('insertions', 0)} -{overview.get('deletions', 0)} Zeilen")
    funcs = result.get("sections", {}).get("changed_functions", [])
    if funcs:
        parts.append(f"  {len(funcs)} Funktionen geändert")
    result["summary"] = "\n".join(parts)

    return fmt_ok(result)
