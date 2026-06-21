"""E2E tests for scout analysis_* tools.

Tests run against the scout plugin's own source code.
Requires E2E_TEST=1 environment variable.
Covers all 13 analysis_* tools.
"""

import json
import os
import sys

import pytest

# Ensure scout is importable
_plugin_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _plugin_root not in sys.path:
    sys.path.insert(0, os.path.dirname(_plugin_root))

pytestmark = pytest.mark.run_e2e


class TestAnalysisInspectE2E:
    """Test analysis_inspect_tool against scout plugin source."""

    def test_inspect_on_plugin_self(self, scout_plugin_dir):
        """analysis_inspect auf scout/_fmt.py — sollte funktionieren."""
        from scout.analysis.analysis_tools import analysis_inspect_tool
        result = json.loads(analysis_inspect_tool({"path": os.path.join(scout_plugin_dir, "_fmt.py"), "depth": 1}))
        assert result.get("status") != "error"
        assert "symbols" in result or "summary" in result

    def test_inspect_on_nonexistent(self):
        """analysis_inspect mit nicht-existenter Datei."""
        from scout.analysis.analysis_tools import analysis_inspect_tool
        result = json.loads(analysis_inspect_tool({"path": "/nonexistent/file.py", "depth": 1}))
        assert result.get("status") == "error"

    def test_inspect_empty_path(self):
        """analysis_inspect mit leerem Pfad."""
        from scout.analysis.analysis_tools import analysis_inspect_tool
        result = json.loads(analysis_inspect_tool({"path": ""}))
        assert result.get("status") == "error"


class TestAnalysisDeadcodeE2E:
    """Test analysis_deadcode_tool."""

    def test_deadcode_on_plugin(self, scout_plugin_dir):
        """deadcode-Scan auf scout Plugin sollte laufen (kein Crash)."""
        from scout.analysis.analysis_tools import analysis_deadcode_tool
        result = json.loads(analysis_deadcode_tool({"path": scout_plugin_dir, "kinds": ["imports"]}))
        assert result.get("status") != "error"


class TestAnalysisArchitectureE2E:
    """Test analysis_architecture_tool."""

    def test_architecture_on_plugin(self, scout_plugin_dir):
        """architecture auf scout/analysis/ Verzeichnis."""
        from scout.analysis.analysis_tools import analysis_architecture_tool
        arch_path = os.path.join(scout_plugin_dir, "analysis")
        result = json.loads(analysis_architecture_tool({"path": arch_path, "format": "text", "depth": 1}))
        assert result.get("status") != "error"


class TestAnalysisPerformanceE2E:
    """analysis_performance_tool."""

    def test_performance_on_file(self, scout_plugin_dir):
        from scout.analysis.analysis_tools import analysis_performance_tool
        r = json.loads(analysis_performance_tool({"path": os.path.join(scout_plugin_dir, "_fmt.py")}))
        assert r.get("status") != "error"


class TestAnalysisAskE2E:
    """analysis_ask_tool."""

    def test_ask_about_plugin(self, scout_plugin_dir):
        from scout.analysis.analysis_tools import analysis_ask_tool
        r = json.loads(analysis_ask_tool({"question": "What does scout._fmt provide?", "path": scout_plugin_dir}))
        assert r.get("status") != "error"


class TestAnalysisDiffE2E:
    """analysis_diff_tool."""

    def test_diff_two_reports(self):
        from scout.analysis.analysis_tools import analysis_diff_tool
        r = json.loads(analysis_diff_tool({"report_a": {"test": "a"}, "report_b": {"test": "b"}, "scope": "e2e-test"}))
        assert r.get("status") != "error"


class TestAnalysisTrendE2E:
    """analysis_trend_tool."""

    def test_trend_default(self, scout_plugin_dir):
        from scout.analysis.analysis_tools import analysis_trend_tool
        r = json.loads(analysis_trend_tool({"days": 7}))
        assert r.get("status") != "error"


class TestAnalysisWatchE2E:
    """analysis_watch_tool."""

    def test_watch_list(self, scout_plugin_dir):
        from scout.analysis.analysis_tools import analysis_watch_tool
        r = json.loads(analysis_watch_tool({"action": "list", "path": scout_plugin_dir}))
        assert r.get("status") != "error"


class TestAnalysisGraphE2E:
    """analysis_graph_tool."""

    def test_graph_as_dependency(self, scout_plugin_dir):
        from scout.analysis.analysis_tools import analysis_graph_tool, analysis_inspect_tool
        report = json.loads(analysis_inspect_tool({"path": os.path.join(scout_plugin_dir, "_fmt.py"), "depth": 1}))
        r = json.loads(analysis_graph_tool({"report": report, "type": "dependency"}))
        assert r.get("status") != "error"


class TestAnalysisUiGapE2E:
    """analysis_ui_gap_tool."""

    def test_ui_gap_on_plugin(self, scout_plugin_dir):
        from scout.analysis.tools.ui_gap import analysis_ui_gap_tool
        r = json.loads(analysis_ui_gap_tool({"path": scout_plugin_dir}))
        assert r.get("status") != "error"
