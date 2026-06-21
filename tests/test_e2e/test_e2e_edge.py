"""E2E edge case tests for scout — error handling, empty inputs, nonexistent paths.

Requires E2E_TEST=1 environment variable.
"""

import json
import os
import sys

import pytest

_plugin_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.dirname(_plugin_root) not in sys.path:
    sys.path.insert(0, os.path.dirname(_plugin_root))

pytestmark = pytest.mark.run_e2e


class TestEdgeCasesE2E:
    """Edge cases: empty paths, nonexistent files, invalid args."""

    def test_inspect_empty_path(self):
        from scout.analysis.analysis_tools import analysis_inspect_tool
        r = json.loads(analysis_inspect_tool({"path": "", "depth": 1}))
        assert r.get("status") == "error"

    def test_inspect_nonexistent(self):
        from scout.analysis.analysis_tools import analysis_inspect_tool
        r = json.loads(analysis_inspect_tool({"path": "/nonexistent/path", "depth": 1}))
        assert r.get("status") == "error"

    def test_deadcode_empty_path(self):
        from scout.analysis.analysis_tools import analysis_deadcode_tool
        r = json.loads(analysis_deadcode_tool({"path": "", "kinds": ["all"]}))
        assert r.get("status") == "error"

    def test_architecture_empty_path(self):
        from scout.analysis.analysis_tools import analysis_architecture_tool
        r = json.loads(analysis_architecture_tool({"path": "", "format": "text"}))
        assert r.get("status") == "error"

    def test_bughunt_finding_empty_title(self, scout_plugin_dir):
        from scout.bughunt.bughunt_tools import bug_hunt_start, bug_hunt_finding, bug_hunt_close
        json.loads(bug_hunt_start({"project": scout_plugin_dir, "scope": "quick"}))
        r = json.loads(bug_hunt_finding({"title": ""}))
        assert r.get("status") == "error"
        json.loads(bug_hunt_close({}))

    def test_research_start_empty_query(self, tmp_path):
        from scout.research.tools.crud import research_start
        r = json.loads(research_start({"query": ""}))
        assert r.get("status") == "error"
