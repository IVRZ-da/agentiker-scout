"""analysis_graph_query Tool — Knowledge Graph Abfragen.

Nutzt code_index + code_graph_query.
"""
from __future__ import annotations

import logging
from typing import Any

from scout._fmt import fmt_err, fmt_ok

from .base import _call_tool, _validate_and_resolve_path

logger = logging.getLogger("analysis")


def analysis_graph_query_tool(args: dict, **kwargs) -> str:
    """Durchsucht den Knowledge Graph eines Projekts."""
    path = args.get("path", "")
    query_type = args.get("query", "summary")
    symbol = args.get("symbol", "")
    top_n = min(args.get("top_n", 10), 50)
    force_reindex = args.get("force_reindex", False)

    path_error, resolved_path = _validate_and_resolve_path(path)
    if path_error:
        return fmt_err(f"{path_error} (path: {path})")
    path = resolved_path

    result: dict[str, Any] = {
        "path": path,
        "query": query_type,
        "symbol": symbol or None,
        "result": {},
    }

    # 1. Index bauen (falls nötig)
    try:
        idx = _call_tool("code_index", path=path, force_rescan=force_reindex)
        if idx and isinstance(idx, dict):
            result["index_info"] = {
                "files_indexed": idx.get("files", idx.get("files_indexed", idx.get("count", 0))),
            }
    except Exception as e:
        logger.debug("code_index skipped: %s", e)

    # 2. Query ausführen
    try:
        query_kwargs = {"path": path, "query": query_type}
        if query_type in ("callers", "callees") and symbol:
            query_kwargs["symbol"] = symbol
        query_kwargs["top_n"] = top_n

        qr = _call_tool("code_graph_query", **query_kwargs)
        if qr:
            result["result"] = qr if isinstance(qr, dict) else {"data": str(qr)[:500]}
    except Exception as e:
        logger.warning("code_graph_query failed: %s", e)
        return fmt_err(f"Graph query failed: {e}")

    parts = [f"🕸️ Knowledge Graph: {query_type}"]
    idx_info = result.get("index_info", {})
    if idx_info:
        parts.append(f"  Indizierte Dateien: {idx_info.get('files_indexed', '?')}")
    res = result.get("result", {})
    if isinstance(res, dict):
        data = res.get("data", res.get("results", res.get("paths", [])))
        if isinstance(data, list):
            parts.append(f"  Ergebnisse: {len(data)} Treffer")
    result["summary"] = "\n".join(parts)

    return fmt_ok(result)
