"""Tests für analysis_diff_analysis.
"""
from __future__ import annotations

from scout.analysis.tools.diff_trend_watch import analysis_diff_analysis_tool


def _parse(raw: str) -> dict:
    import json
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"status": "error", "raw": raw}


class TestAnalysisDiffAnalysis:
    def test_requires_path(self):
        result = analysis_diff_analysis_tool({})
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_with_invalid_path(self):
        result = analysis_diff_analysis_tool({"path": "/nonexistent"})
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_output_structure(self):
        result = analysis_diff_analysis_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        assert "sections" in parsed
        assert "summary" in parsed

    def test_custom_refs(self):
        result = analysis_diff_analysis_tool({
            "path": "/home/jo/.hermes/plugins/scout",
            "base": "HEAD~3",
            "head": "HEAD",
            "max_files": 3,
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"

    def test_output_size(self):
        result = analysis_diff_analysis_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        assert len(result) < 3000, f"Output zu lang: {len(result)}"
