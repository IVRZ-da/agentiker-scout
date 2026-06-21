"""E2E tests for scout shared pattern pipeline.

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


class TestSharedPatternsE2E:
    """Shared Pattern Repository CRUD."""

    def test_pattern_save_and_retrieve(self):
        """Pattern speichern und via get_patterns_for_analysis abrufen."""
        from scout.shared.patterns import save_pattern, get_pattern, get_patterns_for_analysis, delete_pattern

        pid = save_pattern({
            "name": "E2E Test Pattern",
            "description": "Created during E2E test",
            "category": "code-quality",
            "severity": "P2",
            "scan_type": "grep",
            "scan_query": "test.*pattern",
            "scan_file_glob": "**/*.py",
            "scan_language": "python",
        })
        assert pid is not None

        retrieved = get_pattern(pid)
        assert retrieved is not None
        assert retrieved.get("name") == "E2E Test Pattern"

        delete_pattern(pid)
        assert get_pattern(pid) is None

    def test_analysis_pattern_discover(self, scout_plugin_dir):
        """analysis_pattern_discover auf scout-selbst sollte laufen."""
        from scout.analysis.analysis_tools import analysis_pattern_discover_tool
        result = json.loads(analysis_pattern_discover_tool({"path": scout_plugin_dir, "min_frequency": 10}))
        assert result.get("status") != "error"

    def test_research_patterns_list(self):
        """Research-Patterns auflisten."""
        from scout.shared.patterns_research import list_research_patterns
        patterns = list_research_patterns()
        assert len(patterns) >= 4
        categories = {p["category"] for p in patterns}
        assert "regulatory" in categories
