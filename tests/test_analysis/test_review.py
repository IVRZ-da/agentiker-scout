"""Tests für analysis_review_tool."""
from __future__ import annotations

from scout.analysis.tools.review import analysis_review_tool


def _parse(raw: str) -> dict:
    import json
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"status": "error", "raw": raw}


class TestAnalysisReview:
    def test_requires_path(self):
        result = analysis_review_tool({})
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_output_structure(self):
        result = analysis_review_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        assert "path" in parsed
        assert "base" in parsed
        assert "head" in parsed
        assert "sections" in parsed
        assert "summary" in parsed

    def test_output_size(self):
        result = analysis_review_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        assert len(result) < 3000, f"Output zu lang: {len(result)}"

    def test_invalid_path_traversal(self):
        result = analysis_review_tool({
            "path": "../../etc/passwd",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_with_custom_refs(self):
        result = analysis_review_tool({
            "path": "/home/jo/.hermes/plugins/scout",
            "base": "main",
            "head": "HEAD",
            "max_files": 5,
        })
        parsed = _parse(result)
        assert parsed.get("status") == "ok"
        assert parsed.get("base") == "main"
        assert parsed.get("head") == "HEAD"
