"""E2E tests for scout research_* tools.

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


class TestResearchBasicE2E:
    """Research start → save → search → delete lifecycle."""

    def test_research_lifecycle(self, tmp_path):
        """Kompletter Research-Lifecycle ohne Firecrawl."""
        from scout.research.tools.crud import research_start, research_save, research_delete

        # Start
        start = json.loads(research_start({"query": "E2E Test Research", "depth": 1}))
        assert start.get("status") != "error"
        rid = start.get("research_id") or start.get("data", {}).get("research_id", "")

        # Save
        save = json.loads(research_save({
            "research_id": rid,
            "summary": "E2E test complete",
            "findings": [{"finding": "Test finding", "sources": ["https://test.com"]}],
            "sources": [{"url": "https://test.com", "title": "Test Source"}],
            "status": "completed",
        }))
        assert save.get("status") != "error"

        # Delete
        delete = json.loads(research_delete({"research_id": rid}))
        assert delete.get("status") != "error"

    def test_research_search_empty(self, tmp_path):
        """research_search ohne Daten."""
        from scout.research.tools.search import research_search
        result = json.loads(research_search({"query": "nonexistent"}))
        assert result.get("status") != "error"

    def test_research_status(self, tmp_path):
        """research_status ohne aktive Research."""
        from scout.research.tools.search import research_status
        result = json.loads(research_status({"research_id": "", "show_orphans": True}))
        assert result.get("status") != "error"
