"""analysis_tools — Re-Export Facade für analysis/tools/ Subpackage.

Alle Tool-Handler wurden in analysis/tools/ aufgeteilt.
Dieses Modul importiert alle Funktionen und exportiert TOOL_HANDLERS.
"""

from __future__ import annotations

from typing import Any

from .tools.arch_deadcode import (
    analysis_architecture_tool,
    analysis_deadcode_tool,
    analysis_dependency_risk_tool,
    analysis_risk_tool,
)
from .tools.base import (  # noqa: F401
    _try_create_bughunt_finding,
    _try_create_plan_follow_plan,
)
from .tools.diff_trend_watch import (
    analysis_diff_analysis_tool,
    analysis_diff_tool,
    analysis_trend_tool,
    analysis_watch_tool,
)
from .tools.duplicates import analysis_duplicates_tool
from .tools.framework_query_move import (
    analysis_code_move_tool,
    analysis_code_query_tool,
    analysis_framework_tool,
)
from .tools.graph_patterns import (
    analysis_graph_tool,
    analysis_pattern_discover_tool,
)
from .tools.graph_query import analysis_graph_query_tool
from .tools.inspect import analysis_inspect_tool
from .tools.migration import analysis_migration_tool
from .tools.perf_sec import (
    analysis_ask_tool,
    analysis_performance_tool,
    analysis_security_tool,
)
from .tools.report import analysis_report_tool
from .tools.review import analysis_review_tool
from .tools.schemas import (
    ANALYSIS_ARCHITECTURE_SCHEMA,
    ANALYSIS_ASK_SCHEMA,
    ANALYSIS_CODE_MOVE_SCHEMA,
    ANALYSIS_CODE_QUERY_SCHEMA,
    ANALYSIS_DEADCODE_SCHEMA,
    ANALYSIS_DEPENDENCY_RISK_SCHEMA,
    ANALYSIS_DIFF_ANALYSIS_SCHEMA,
    ANALYSIS_DIFF_SCHEMA,
    ANALYSIS_DUPLICATES_SCHEMA,
    ANALYSIS_FRAMEWORK_SCHEMA,
    ANALYSIS_GRAPH_QUERY_SCHEMA,
    ANALYSIS_GRAPH_SCHEMA,
    ANALYSIS_INSPECT_SCHEMA,
    ANALYSIS_MIGRATION_SCHEMA,
    ANALYSIS_PATTERN_DISCOVER_SCHEMA,
    ANALYSIS_PERFORMANCE_SCHEMA,
    ANALYSIS_REPORT_SCHEMA,
    ANALYSIS_REVIEW_SCHEMA,
    ANALYSIS_RISK_SCHEMA,
    ANALYSIS_SECURITY_SCHEMA,
    ANALYSIS_TEST_INSIGHT_SCHEMA,
    ANALYSIS_TIMELINE_SCHEMA,
    ANALYSIS_TREND_SCHEMA,
    ANALYSIS_UI_GAP_SCHEMA,
    ANALYSIS_WATCH_SCHEMA,
)
from .tools.test_insight import analysis_test_insight_tool
from .tools.timeline import analysis_timeline_tool

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
    "analysis_timeline": (ANALYSIS_TIMELINE_SCHEMA, analysis_timeline_tool),
    "analysis_duplicates": (ANALYSIS_DUPLICATES_SCHEMA, analysis_duplicates_tool),
    "analysis_dependency_risk": (ANALYSIS_DEPENDENCY_RISK_SCHEMA, analysis_dependency_risk_tool),
    "analysis_diff_analysis": (ANALYSIS_DIFF_ANALYSIS_SCHEMA, analysis_diff_analysis_tool),
    "analysis_risk": (ANALYSIS_RISK_SCHEMA, analysis_risk_tool),
    "analysis_review": (ANALYSIS_REVIEW_SCHEMA, analysis_review_tool),
    "analysis_graph_query": (ANALYSIS_GRAPH_QUERY_SCHEMA, analysis_graph_query_tool),
    "analysis_test_insight": (ANALYSIS_TEST_INSIGHT_SCHEMA, analysis_test_insight_tool),
    "analysis_migration": (ANALYSIS_MIGRATION_SCHEMA, analysis_migration_tool),
}

def _mermaid_from_dependency(data):
    """Generate a Mermaid graph from dependency data."""
    if isinstance(data, str):
        lines = []
        for line in data.strip().split("\n"):
            parts = line.split(" -> ")
            if len(parts) == 2:
                lines.append(f"    {parts[0].strip()} --> {parts[1].strip()}")
        return "mermaid\ngraph LR\n" + "\n".join(lines) if lines else "mermaid\ngraph LR\n    no_data[No dependency data]"
    if isinstance(data, dict):
        if not data:
            return "mermaid\nno_data[No dependency data]"
        nodes = []
        edges = data.get("edges", None)
        if edges is not None:
            for pair in edges:
                if len(pair) >= 2:
                    nodes.append(f"    {pair[0]} --> {pair[1]}")
        else:
            for key, value in data.items():
                if isinstance(value, list):
                    if value and isinstance(value[0], list):
                        for pair in value:
                            if len(pair) >= 2:
                                nodes.append(f"    {pair[0]} --> {pair[1]}")
                    else:
                        for item in value:
                            nodes.append(f"    {item}")
        return "mermaid\ngraph LR\n" + "\n".join(nodes) if nodes else "mermaid\n    no_data[No dependency data]"
    return "mermaid\n    no_data[No dependency data]"


def _mermaid_from_cycles(data):
    """Generate a Mermaid graph from cycle data."""
    cycles = data.get("cycles", []) if isinstance(data, dict) else []
    if not cycles:
        return "mermaid\n    no_cycles[No cycles detected]"
    lines = []
    for i, cycle in enumerate(cycles):
        if len(cycle) >= 2:
            lines.append(f"    subgraph Cycle_{i}[Cycle {i}]")
            lines.append(f"    style Cycle_{i} fill:#ffcccc")
            for j in range(len(cycle) - 1):
                lines.append(f"    {cycle[j]} --> {cycle[j+1]}")
            lines.append("    end")
    return "mermaid\ngraph LR\n" + "\n".join(lines) if lines else "mermaid\n    no_cycles[No cycles detected]"
