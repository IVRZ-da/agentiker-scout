"""framework_query_move.py — analysis_framework/query/move Tool-Handler.

Extracted from analysis_tools.py (Phase C) for modularity.
Enthält Framework-Detection, Code-Query und Code-Move Tools.
"""

from __future__ import annotations

from scout._fmt import fmt_err, fmt_ok

from .base import _call_tool, _validate_and_resolve_path, _validate_path

# ---------------------------------------------------------------------------
# analysis_framework Tool
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# analysis_code_query Tool
# ---------------------------------------------------------------------------


def analysis_code_query_tool(args: dict, **kwargs) -> str:
    """Wrapper für code_query: Smart Query Router für Code-Intelligence.

    Delegiert an _call_tool("code_query", ...) mit Intent-Erkennung.
    """
    path = args.get("path", "")
    intent = args.get("intent", "")
    line = args.get("line", 0)
    language = args.get("language", "")

    error = _validate_path(path)
    if error:
        return fmt_err(error)

    path_error, resolved_path = _validate_and_resolve_path(path)
    if path_error:
        return fmt_err(f"{path_error} (path: {path})")

    result = _call_tool("code_query", intent=intent, path=resolved_path, line=line, language=language)
    return fmt_ok(result) if isinstance(result, dict) else result


# ---------------------------------------------------------------------------
# analysis_code_move Tool
# ---------------------------------------------------------------------------


def analysis_code_move_tool(args: dict, **kwargs) -> str:
    """Wrapper für code_move: Verschiebt ein Symbol zwischen Dateien.

    Delegiert an _call_tool("code_move", ...) mit Source/Target-Pfaden.
    """
    source = args.get("source", "")
    symbol = args.get("symbol", "")
    target = args.get("target", "")
    dry_run = args.get("dry_run", True)

    if not source or not symbol or not target:
        return fmt_err("source, symbol, and target are required")

    for p in (source, target):
        error = _validate_path(p)
        if error:
            return fmt_err(f"{error} (path: {p})")

    result = _call_tool(
        "code_move",
        source=source,
        symbol=symbol,
        target=target,
        dry_run=dry_run,
    )
    return fmt_ok(result) if isinstance(result, dict) else result
