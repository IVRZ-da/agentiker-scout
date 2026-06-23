"""Tests für analysis_duplicates.
"""
from __future__ import annotations

from scout.analysis.tools.duplicates import analysis_duplicates_tool


def _parse(raw: str) -> dict:
    import json
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"status": "error", "raw": raw}


class TestAnalysisDuplicates:
    def test_requires_path(self):
        result = analysis_duplicates_tool({})
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_output_structure(self):
        result = analysis_duplicates_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        assert "summary" in parsed
        assert "path" in parsed

    def test_custom_params(self):
        result = analysis_duplicates_tool({
            "path": "/home/jo/.hermes/plugins/scout",
            "min_lines": 3,
            "similarity_threshold": 0.9,
            "top_n": 5,
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"

    def test_output_size(self):
        result = analysis_duplicates_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        assert len(result) < 3000, f"Output zu lang: {len(result)}"

    def test_invalid_path_traversal(self):
        result = analysis_duplicates_tool({
            "path": "../../etc/passwd",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_output_has_findings_key(self):
        result = analysis_duplicates_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        parsed = _parse(result)
        assert "findings" in parsed
