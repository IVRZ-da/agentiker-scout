"""Tests für analysis_timeline.
"""
from __future__ import annotations

from scout.analysis.tools.timeline import analysis_timeline_tool


def _parse(raw: str) -> dict:
    import json
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"status": "error", "raw": raw}


class TestAnalysisTimeline:
    def test_requires_path(self):
        result = analysis_timeline_tool({})
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_output_structure(self):
        result = analysis_timeline_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        assert "path" in parsed
        assert "sections" in parsed
        assert "summary" in parsed

    def test_with_symbol(self):
        result = analysis_timeline_tool({
            "path": "/home/jo/.hermes/plugins/scout/analysis/tools/timeline.py",
            "symbol": "analysis_timeline_tool",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        assert "sections" in parsed

    def test_output_size(self):
        result = analysis_timeline_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        assert len(result) < 3000, f"Output zu lang: {len(result)}"

    def test_max_commits_param(self):
        result = analysis_timeline_tool({
            "path": "/home/jo/.hermes/plugins/scout",
            "max_commits": 5,
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"

    def test_invalid_path_traversal(self):
        result = analysis_timeline_tool({
            "path": "../../etc/passwd",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "error"
