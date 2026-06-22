"""Report-Tool für strukturierte Analyse-Reports.

Extrahiert aus analysis_tools.py:
  - analysis_report_tool: Report-Generierung + Honcho-Persistenz
"""

from __future__ import annotations

import logging
from datetime import datetime

from scout._fmt import fmt_ok

from .base import _persist_analysis

logger = logging.getLogger("analysis")


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
