"""tools/schemas.py — Tool-Schemas geladen aus schemas_data.json.

Alle OpenAPI-ähnlichen Schemas für analysis_* Tools.
Die Daten wurden aus dieser Datei nach schemas_data.json extrahiert
(früher ~770 Zeilen, jetzt ~15 Zeilen + 25 KB JSON).
"""

import json
from pathlib import Path
from typing import Any

_SCHEMAS: dict[str, Any] = {}
_json_path = Path(__file__).resolve().parent / "schemas_data.json"
if _json_path.exists():
    try:
        _SCHEMAS = json.loads(_json_path.read_text(encoding="utf-8"))
    except Exception:
        pass

# ── Module-Level-Re-Export ──────────────────────────────────────
# Alle 25 Schemas werden auf Modulebene bereitgestellt, damit
# 'from .tools.schemas import ANALYSIS_*_SCHEMA' weiterhin funktioniert.

ANALYSIS_INSPECT_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_INSPECT_SCHEMA", {})
ANALYSIS_REPORT_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_REPORT_SCHEMA", {})
ANALYSIS_ARCHITECTURE_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_ARCHITECTURE_SCHEMA", {})
ANALYSIS_DEADCODE_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_DEADCODE_SCHEMA", {})
ANALYSIS_PERFORMANCE_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_PERFORMANCE_SCHEMA", {})
ANALYSIS_SECURITY_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_SECURITY_SCHEMA", {})
ANALYSIS_ASK_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_ASK_SCHEMA", {})
ANALYSIS_DIFF_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_DIFF_SCHEMA", {})
ANALYSIS_TREND_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_TREND_SCHEMA", {})
ANALYSIS_WATCH_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_WATCH_SCHEMA", {})
ANALYSIS_GRAPH_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_GRAPH_SCHEMA", {})
ANALYSIS_PATTERN_DISCOVER_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_PATTERN_DISCOVER_SCHEMA", {})
ANALYSIS_UI_GAP_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_UI_GAP_SCHEMA", {})
ANALYSIS_FRAMEWORK_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_FRAMEWORK_SCHEMA", {})
ANALYSIS_CODE_QUERY_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_CODE_QUERY_SCHEMA", {})
ANALYSIS_CODE_MOVE_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_CODE_MOVE_SCHEMA", {})
ANALYSIS_TIMELINE_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_TIMELINE_SCHEMA", {})
ANALYSIS_DUPLICATES_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_DUPLICATES_SCHEMA", {})
ANALYSIS_DEPENDENCY_RISK_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_DEPENDENCY_RISK_SCHEMA", {})
ANALYSIS_DIFF_ANALYSIS_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_DIFF_ANALYSIS_SCHEMA", {})
ANALYSIS_RISK_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_RISK_SCHEMA", {})
ANALYSIS_REVIEW_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_REVIEW_SCHEMA", {})
ANALYSIS_GRAPH_QUERY_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_GRAPH_QUERY_SCHEMA", {})
ANALYSIS_TEST_INSIGHT_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_TEST_INSIGHT_SCHEMA", {})
ANALYSIS_MIGRATION_SCHEMA: dict = _SCHEMAS.get("ANALYSIS_MIGRATION_SCHEMA", {})
