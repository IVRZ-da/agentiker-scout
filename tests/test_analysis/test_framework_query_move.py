"""Tests für analysis/tools/framework_query_move.py — 3 Tool-Handler."""

from __future__ import annotations

import json
from pathlib import Path

from scout.analysis.tools.framework_query_move import (
    analysis_framework_tool,
)


class TestAnalysisFrameworkTool:
    def test_missing_path(self):
        result = analysis_framework_tool({"path": ""})
        data = json.loads(result)
        assert data["status"] == "error"
        assert "path" in data.get("message", "")

    def test_nonexistent_path(self):
        """Handler sollte ValueError abfangen."""
        result = analysis_framework_tool({"path": "/nonexistent/path/xyz"})
        data = json.loads(result)
        assert data["status"] == "error"

    def test_with_tmp_path(self, tmp_path: Path):
        """Funktioniert mit einem echten Verzeichnis."""
        (tmp_path / "main.py").write_text("print('hello')\n")
        result = analysis_framework_tool({"path": str(tmp_path), "fast": True})
        data = json.loads(result)
        assert data["status"] == "ok"
        assert "profile" in data
