"""tools — Subpackage für Analyse-Tool-Helfer.

Exportiert Basis-Funktionen für die Tool-Handler.
"""

from .base import (
    _validate_path,
    _validate_and_resolve_path,
    _call_tool,
    _parallel_dispatch,
    _clear_symbol_line_cache,
    _find_symbol_line,
    _persist_analysis,
)
from .ui_discovery import discover_uis
from .mapping import build_coverage_matrix, format_coverage_report
from .schemas import (
    ANALYSIS_INSPECT_SCHEMA,
    ANALYSIS_REPORT_SCHEMA,
    ANALYSIS_ARCHITECTURE_SCHEMA,
    ANALYSIS_DEADCODE_SCHEMA,
    ANALYSIS_PERFORMANCE_SCHEMA,
    ANALYSIS_SECURITY_SCHEMA,
    ANALYSIS_ASK_SCHEMA,
    ANALYSIS_DIFF_SCHEMA,
    ANALYSIS_TREND_SCHEMA,
    ANALYSIS_WATCH_SCHEMA,
    ANALYSIS_GRAPH_SCHEMA,
    ANALYSIS_UI_GAP_SCHEMA,
)

# analysis_ui_gap_tool wird nicht direkt von tools.* exportiert,
# da ui_gap.py relative imports (from .._fmt) verwendet, die nur
# im analysis.tools Subpackage-Kontext funktionieren.
# Der Import erfolgt direkt in analysis_tools.py.

__all__ = [
    "_validate_path",
    "_validate_and_resolve_path",
    "_call_tool",
    "_parallel_dispatch",
    "_clear_symbol_line_cache",
    "_find_symbol_line",
    "_persist_analysis",
    "discover_uis",
    "build_coverage_matrix",
    "format_coverage_report",
]
