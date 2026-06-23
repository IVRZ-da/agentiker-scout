"""Tests für analysis_test_insight_tool."""
from __future__ import annotations

from scout.analysis.tools.test_insight import analysis_test_insight_tool


def _parse(raw: str) -> dict:
    import json
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"status": "error", "raw": raw}


class TestAnalysisTestInsight:
    def test_requires_path(self):
        result = analysis_test_insight_tool({})
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_output_structure(self):
        result = analysis_test_insight_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        assert "path" in parsed
        assert "symbol" in parsed
        assert "tests_found" in parsed
        assert "generated_scaffolds" in parsed
        assert "summary" in parsed

    def test_output_size(self):
        result = analysis_test_insight_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        assert len(result) < 3000, f"Output zu lang: {len(result)}"

    def test_invalid_path_traversal(self):
        result = analysis_test_insight_tool({
            "path": "../../etc/passwd",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_with_symbol(self):
        result = analysis_test_insight_tool({
            "path": "/home/jo/.hermes/plugins/scout",
            "symbol": "analysis_test_insight_tool",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        assert parsed.get("symbol") == "analysis_test_insight_tool"
