"""framework_query_move.py — analysis_framework/query/move Tool-Handler.

Extracted from analysis_tools.py (Phase C) for modularity.
Enthält Framework-Detection, Code-Query und Code-Move Tools.
"""

from __future__ import annotations

from scout._fmt import fmt_err, fmt_ok

# ---------------------------------------------------------------------------
# analysis_framework Tool
# ---------------------------------------------------------------------------


def analysis_framework_tool(args: dict, **kwargs) -> str:
    """Handler für analysis_framework — Framework-Profil anzeigen."""

    path = args.get("path", "").strip()
    if not path:
        return fmt_err("path ist erforderlich")

    fast = args.get("fast", False)

    try:
        from scout.shared.framework_detector import (
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
