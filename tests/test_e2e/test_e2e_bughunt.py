"""E2E tests for scout bug_hunt_* tools (Patterns + Scans).

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


class TestBughuntPatternE2E:
    """Bug-Hunt Pattern tests."""

    def test_pattern_list(self):
        """bug_hunt_pattern(list) sollte Patterns zurückgeben."""
        from scout.bughunt.bughunt_tools import bug_hunt_pattern
        result = json.loads(bug_hunt_pattern({"action": "list"}))
        assert result.get("status") != "error"
        assert "patterns" in result

    def test_pattern_save_and_get(self, tmp_path):
        """Custom Pattern speichern und abrufen."""
        from scout.bughunt.bughunt_tools import bug_hunt_pattern
        save_result = json.loads(bug_hunt_pattern({
            "action": "save",
            "pattern_id": "E2E_TEST_PATTERN",
            "name": "E2E Test Pattern",
            "description": "Pattern created during E2E test",
            "scan_type": "grep",
            "scan_query": "test_pattern",
            "scan_file_glob": "**/*.py",
        }))
        assert save_result.get("status") != "error"


class TestBughuntScanE2E:
    """Scan-Runner Tests."""

    def test_bughunt_start_and_close(self, scout_plugin_dir):
        """bug_hunt_start + bug_hunt_close."""
        from scout.bughunt.bughunt_tools import bug_hunt_start, bug_hunt_close
        start = json.loads(bug_hunt_start({"project": scout_plugin_dir, "scope": "quick"}))
        assert start.get("status") != "error"
        # Get session_id from start result
        session_id = start.get("session_id") or start.get("data", {}).get("session_id", "")
        assert session_id, f"Keine session_id in start result: {start}"

        close = json.loads(bug_hunt_close({"session_id": session_id}))
        assert close.get("status") != "error", f"Close failed: {close}"
