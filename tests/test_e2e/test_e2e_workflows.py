"""E2E workflow tests for scout — multiple tools in sequence.

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


class TestCrossDomainE2E:
    """Cross-domain workflows (analysis → bughunt → research)."""

    def test_inspect_then_bughunt(self, scout_plugin_dir):
        """Erst analysis_inspect, dann bug_hunt_scan auf selbe Datei."""
        from scout.analysis.analysis_tools import analysis_inspect_tool
        from scout.bughunt.bughunt_tools import bug_hunt_scan, bug_hunt_start

        # Step 1: Analyse
        target = os.path.join(scout_plugin_dir, "_fmt.py")
        inspect_result = json.loads(analysis_inspect_tool({"path": target, "depth": 1}))
        assert inspect_result.get("status") != "error"

        # Step 2: Bug-Hunt starten
        session_result = json.loads(bug_hunt_start({"project": scout_plugin_dir, "scope": "quick"}))
        assert session_result.get("status") != "error"

    def test_security_then_report(self, scout_plugin_dir):
        """analysis_security → analysis_report."""
        from scout.analysis.analysis_tools import analysis_security_tool, analysis_report_tool

        # Security scan
        sec_result = json.loads(analysis_security_tool({"path": scout_plugin_dir, "kinds": ["errors"]}))
        assert sec_result.get("status") != "error"

        # Report
        report_result = json.loads(analysis_report_tool({
            "scope": "test-e2e",
            "findings": {"test": "value"},
        }))
        assert report_result.get("status") != "error"
