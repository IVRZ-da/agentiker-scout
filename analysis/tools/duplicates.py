"""analysis_duplicates Tool — AST-basierte Duplikat-Erkennung.

Wrapper für code_duplicates mit zusätzlicher Zusammenfassung.
"""
from __future__ import annotations

import logging
from typing import Any

from scout._fmt import fmt_err, fmt_ok

from .base import _call_tool, _validate_and_resolve_path, _validate_path

logger = logging.getLogger("analysis")


def analysis_duplicates_tool(args: dict, **kwargs) -> str:
    """Findet duplizierte/ähnliche Code-Blöcke."""
    path = args.get("path", "")
    min_lines = max(args.get("min_lines", 5), 3)
    similarity = min(max(args.get("similarity_threshold", 0.8), 0.5), 1.0)
    top_n = min(args.get("top_n", 10), 50)

    error = _validate_path(path)
    if error:
        return fmt_err(error)

    path_error, resolved_path = _validate_and_resolve_path(path)
    if path_error:
        return fmt_err(f"{path_error} (path: {path})")
    path = resolved_path

    result: dict[str, Any] = {
        "path": path,
        "min_lines": min_lines,
        "similarity_threshold": similarity,
        "findings": [],
    }

    try:
        dup = _call_tool(
            "code_duplicates",
            path=path,
            min_lines=min_lines,
            similarity_threshold=similarity,
            top_n=top_n,
        )
        if dup:
            if isinstance(dup, dict):
                blocks = dup.get("duplicates", dup.get("data", dup.get("blocks", [])))
                if isinstance(blocks, list):
                    result["findings"] = [
                        {
                            "file": b.get("file", b.get("path", "?")),
                            "lines": b.get("lines", b.get("line_range", "")),
                            "similarity": b.get("similarity", b.get("score", 0)),
                            "content_preview": (b.get("content", "") or b.get("code", ""))[:120],
                        }
                        for b in blocks[:top_n]
                    ]
    except Exception as e:
        logger.warning("code_duplicates failed: %s", e)
        return fmt_err(f"Duplicate scan failed: {e}")

    parts = [
        f"🔍 Duplikat-Scan für {path}",
        f"  Gefunden: {len(result['findings'])} Duplikat-Gruppen",
    ]
    if result["findings"]:
        parts.append("  Top-Funde:")
        for f in result["findings"][:5]:
            preview = f.get("content_preview", "")[:60]
            parts.append(f"    • {f['file']}:{f['lines']} (Ähnlichkeit: {f['similarity']:.0%})")
            if preview:
                parts.append(f"      └ {preview}")

    result["summary"] = "\n".join(parts)
    return fmt_ok(result)
