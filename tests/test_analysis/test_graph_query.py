"""Tests für analysis_graph_query_tool."""
from __future__ import annotations

from scout.analysis.tools.graph_query import analysis_graph_query_tool


def _parse(raw: str) -> dict:
    import json
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"status": "error", "raw": raw}


class TestAnalysisGraphQuery:
    def test_requires_path(self):
        result = analysis_graph_query_tool({})
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_output_structure(self):
        result = analysis_graph_query_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        assert "path" in parsed
        assert "query" in parsed
        assert "result" in parsed
        assert "summary" in parsed

    def test_output_size(self):
        result = analysis_graph_query_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        assert len(result) < 3000, f"Output zu lang: {len(result)}"

    def test_invalid_path_traversal(self):
        result = analysis_graph_query_tool({
            "path": "../../etc/passwd",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_with_query_type(self):
        result = analysis_graph_query_tool({
            "path": "/home/jo/.hermes/plugins/scout",
            "query": "summary",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        assert parsed.get("query") == "summary"
