"""Tests für analysis_dependency_risk.
"""
from __future__ import annotations

from scout.analysis.tools.arch_deadcode import analysis_dependency_risk_tool


def _parse(raw: str) -> dict:
    import json
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"status": "error", "raw": raw}


class TestAnalysisDependencyRisk:
    def test_requires_path(self):
        result = analysis_dependency_risk_tool({})
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_output_structure(self):
        result = analysis_dependency_risk_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        assert "risk_score" in parsed
        assert "risk_level" in parsed
        assert "summary" in parsed

    def test_risk_score_range(self):
        result = analysis_dependency_risk_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        parsed = _parse(result)
        score = parsed.get("risk_score", -1)
        assert 0 <= score <= 10, f"Risk score {score} nicht im Bereich 0-10"

    def test_risk_level_valid(self):
        result = analysis_dependency_risk_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        parsed = _parse(result)
        level = parsed.get("risk_level", "")
        assert level in ("low", "medium", "high", "unknown")

    def test_detailed_mode(self):
        result = analysis_dependency_risk_tool({
            "path": "/home/jo/.hermes/plugins/scout",
            "detail_level": "detailed",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        assert "components" in parsed

    def test_output_size(self):
        result = analysis_dependency_risk_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        assert len(result) < 2000, f"Output zu lang: {len(result)}"

    def test_invalid_path_traversal(self):
        result = analysis_dependency_risk_tool({
            "path": "../../etc/passwd",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_file_path(self):
        """Auch einzelne Dateien sollten funktionieren."""
        result = analysis_dependency_risk_tool({
            "path": "/home/jo/.hermes/plugins/scout/analysis/tools/arch_deadcode.py",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
