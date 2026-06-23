"""Tests für analysis_risk — Multi-Faktor Risk Assessment.
"""
from __future__ import annotations

from scout.analysis.tools.arch_deadcode import analysis_risk_tool


def _parse(raw: str) -> dict:
    import json
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"status": "error", "raw": raw}


class TestAnalysisRisk:
    def test_requires_path(self):
        result = analysis_risk_tool({})
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_with_invalid_path(self):
        result = analysis_risk_tool({"path": "/nonexistent"})
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_output_structure(self):
        result = analysis_risk_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        assert "risk_score" in parsed
        assert "risk_level" in parsed
        assert "components" in parsed
        assert "summary" in parsed

    def test_risk_score_range(self):
        result = analysis_risk_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        parsed = _parse(result)
        score = parsed.get("risk_score", -1)
        assert 0 <= score <= 10, f"Risk score {score} nicht im Bereich 0-10"

    def test_risk_levels(self):
        result = analysis_risk_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        parsed = _parse(result)
        assert parsed.get("risk_level", "") in ("low", "medium", "high", "unknown")

    def test_single_category(self):
        result = analysis_risk_tool({
            "path": "/home/jo/.hermes/plugins/scout",
            "categories": ["complexity"],
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        components = parsed.get("components", {})
        assert "complexity" in components or not components

    def test_output_size(self):
        result = analysis_risk_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        assert len(result) < 3000, f"Output zu lang: {len(result)}"
