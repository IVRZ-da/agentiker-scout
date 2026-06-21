"""Konvertierte E2E → Unit-Tests für scout bug_hunt_* Tools.

Alle 14 ursprünglichen E2E-Tests aus test_e2e/test_e2e_bughunt.py (3 Tests)
und test_e2e/test_e2e_bughunt_more.py (11 Tests) sind bereits durch
existierende Unit-Tests in tests/test_bughunt/ abgedeckt:

  test_e2e_bughunt.py → test_tools_basic.py, test_tools_mgmt.py, test_z_custom_patterns.py
  ─ test_pattern_list          → TestBugHuntPattern.test_pattern_list_all (tools_mgmt)
  ─ test_pattern_save_and_get  → TestSaveCustomPattern.test_save_new (z_custom_patterns)
  ─ test_bughunt_start_and_close → TestWorkflow.test_full_workflow (tools_basic)

  test_e2e_bughunt_more.py → test_tools_basic.py, test_tools_advanced.py,
                              test_tools_mgmt.py, test_fix.py
  ─ test_list_empty            → TestBugHuntList.test_list_empty (tools_basic)
  ─ test_list_with_finding     → TestBugHuntList.test_list_with_findings (tools_basic)
  ─ test_report_json           → TestBugHuntReport.test_report_json_default (tools_advanced)
  ─ test_stats_basic           → TestBugHuntStats.test_stats_empty (tools_mgmt)
  ─ test_stats_with_findings   → TestBugHuntStats.test_stats_with_findings (tools_mgmt)
  ─ test_triage_finding        → TestBugHuntTriage.test_triage_single (tools_advanced)
  ─ test_verify_no_session     → TestBugHuntVerify.test_verify_no_session (tools_advanced)
  ─ test_verify_no_finding     → TestBugHuntVerify.test_verify_nonexistent_finding (tools_advanced)
  ─ test_fix_no_session        → TestBugHuntFixTool.test_fix_missing_session (fix)
  ─ test_history_no_session    → TestBugHuntHistory.test_history_empty (tools_mgmt)
  ─ test_export_no_session     → TestBugHuntExport.test_export_no_session (tools_mgmt)

Ein E2E-Edge-Case-Test (bug_hunt_finding mit leerem Titel) war nicht abgedeckt
und wurde hier als Unit-Test ergänzt (aus test_e2e/test_e2e_edge.py).
"""

import json
from pathlib import Path

import pytest


# ─── Fixtures (für künftige Tests bereit, wenn neue hinzukommen) ─────

@pytest.fixture
def tmp_project(tmp_path):
    """Create a sample project in tmp_path with source files."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "test.py").write_text("""
def hello():
    return "world"

class Calculator:
    def add(self, a, b):
        return a + b
""")
    (tmp_path / "src" / "test.ts").write_text("""
export function greet(name: string): string {
    return `Hello ${name}`;
}
""")
    return tmp_path


@pytest.fixture
def plugin_root():
    """Return the scout plugin root directory."""
    return Path(__file__).resolve().parent.parent.parent


# ─── Edge-Case Tests (aus test_e2e_edge.py) ──────────────────────────────


class TestBughuntFindingEdgeCases:
    """bug_hunt_finding mit leerem Titel sollte error geben."""

    def test_finding_empty_title(self, tmp_project):
        """bug_hunt_finding mit leerem Titel."""
        from scout.bughunt.bughunt_tools import bug_hunt_start, bug_hunt_finding, bug_hunt_close
        json.loads(bug_hunt_start({"project": str(tmp_project), "scope": "quick"}))
        r = json.loads(bug_hunt_finding({"title": ""}))
        assert r.get("status") == "error"
        json.loads(bug_hunt_close({}))
