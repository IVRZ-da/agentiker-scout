"""analysis_tools — Re-Export Facade für analysis/tools/ Subpackage.

Alle Tool-Handler wurden in analysis/tools/ aufgeteilt.
Dieses Modul importiert alle Funktionen und exportiert TOOL_HANDLERS.
"""

from __future__ import annotations

from typing import Any

from .tools.arch_deadcode import (
    analysis_architecture_tool,
    analysis_deadcode_tool,
)
from .tools.base import (  # noqa: F401
    _try_create_bughunt_finding,
    _try_create_plan_follow_plan,
)
from .tools.diff_trend_watch import (
    analysis_diff_tool,
    analysis_trend_tool,
    analysis_watch_tool,
)
from .tools.framework_query_move import (
    analysis_code_move_tool,
    analysis_code_query_tool,
    analysis_framework_tool,
)
from .tools.graph_patterns import (
    _mermaid_from_cycles,
    _mermaid_from_dependency,
    analysis_graph_tool,
    analysis_pattern_discover_tool,
)
from .tools.inspect import analysis_inspect_tool
from .tools.perf_sec import (
    analysis_ask_tool,
    analysis_performance_tool,
    analysis_security_tool,
)
from .tools.report import analysis_report_tool
from .tools.schemas import (
    ANALYSIS_ARCHITECTURE_SCHEMA,
    ANALYSIS_ASK_SCHEMA,
    ANALYSIS_CODE_MOVE_SCHEMA,
    ANALYSIS_CODE_QUERY_SCHEMA,
    ANALYSIS_DEADCODE_SCHEMA,
    ANALYSIS_DIFF_SCHEMA,
    ANALYSIS_FRAMEWORK_SCHEMA,
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

# ======================================================================
# Cross-Tool Utilities (importiert aus tools/base.py)
# ======================================================================
# _try_create_plan_follow_plan und _try_create_bughunt_finding
# wurden in analysis/tools/base.py zentralisiert und werden
# oben per Re-Export importiert.
# ======================================================================
# ======================================================================
# TOOL_HANDLERS — Registrierung aller 16 Analyse-Tools
# ======================================================================
# analysis_ui_gap und analysis_pattern_discover sind noch im monolith —
# werden in Phase 2 ebenfalls migriert.
from .tools.ui_gap import analysis_ui_gap_tool  # noqa: E402, F811

TOOL_HANDLERS: dict[str, tuple[dict, Any]] = {
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
    "analysis_code_query": (ANALYSIS_CODE_QUERY_SCHEMA, analysis_code_query_tool),
    "analysis_code_move": (ANALYSIS_CODE_MOVE_SCHEMA, analysis_code_move_tool),
}
