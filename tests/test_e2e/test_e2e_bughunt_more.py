"""E2E tests for scout bug_hunt_* tools — export, fix, history, list, report, stats, triage, verify.

Requires E2E_TEST=1.
Alle Tools brauchen eine aktive Session (session_id).
"""

import json
import os
import sys

import pytest

_plugin_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _plugin_root not in sys.path:
    sys.path.insert(0, os.path.dirname(_plugin_root))

pytestmark = pytest.mark.run_e2e


def _start_session(scout_plugin_dir):
    """Start session, return session_id."""
    from scout.bughunt.bughunt_tools import bug_hunt_start
    s = json.loads(bug_hunt_start({"project": scout_plugin_dir, "scope": "quick"}))
    return s.get("session_id") or s.get("data", {}).get("session_id", "")


def _close_session(sid):
    """Close session."""
    from scout.bughunt.bughunt_tools import bug_hunt_close
    json.loads(bug_hunt_close({"session_id": sid}))


class TestBughuntListE2E:
    """bug_hunt_list."""

    def test_list_empty(self, scout_plugin_dir):
        sid = _start_session(scout_plugin_dir)
        from scout.bughunt.bughunt_tools import bug_hunt_list
        r = json.loads(bug_hunt_list({"session_id": sid}))
        assert r.get("status") != "error"
        _close_session(sid)

    def test_list_with_finding(self, scout_plugin_dir):
        sid = _start_session(scout_plugin_dir)
        from scout.bughunt.bughunt_tools import bug_hunt_finding, bug_hunt_list
        json.loads(bug_hunt_finding({"session_id": sid, "title": "List test", "severity": "P2"}))
        r = json.loads(bug_hunt_list({"session_id": sid}))
        assert r.get("status") != "error"
        _close_session(sid)


class TestBughuntReportE2E:
    """bug_hunt_report."""

    def test_report_json(self, scout_plugin_dir):
        sid = _start_session(scout_plugin_dir)
        from scout.bughunt.bughunt_tools import bug_hunt_finding, bug_hunt_report
        json.loads(bug_hunt_finding({"session_id": sid, "title": "Report test", "severity": "P1"}))
        r = json.loads(bug_hunt_report({"session_id": sid, "format": "json"}))
        assert r.get("status") != "error"
        _close_session(sid)


class TestBughuntStatsE2E:
    """bug_hunt_stats."""

    def test_stats_basic(self, scout_plugin_dir):
        sid = _start_session(scout_plugin_dir)
        from scout.bughunt.bughunt_tools import bug_hunt_stats
        r = json.loads(bug_hunt_stats({"session_id": sid}))
        assert r.get("status") != "error"
        _close_session(sid)

    def test_stats_with_findings(self, scout_plugin_dir):
        sid = _start_session(scout_plugin_dir)
        from scout.bughunt.bughunt_tools import bug_hunt_finding, bug_hunt_stats
        json.loads(bug_hunt_finding({"session_id": sid, "title": "P0 test", "severity": "P0"}))
        json.loads(bug_hunt_finding({"session_id": sid, "title": "P2 test", "severity": "P2"}))
        r = json.loads(bug_hunt_stats({"session_id": sid}))
        assert r.get("status") != "error"
        _close_session(sid)


class TestBughuntTriageE2E:
    """bug_hunt_triage."""

    def test_triage_finding(self, scout_plugin_dir):
        sid = _start_session(scout_plugin_dir)
        from scout.bughunt.bughunt_tools import bug_hunt_finding, bug_hunt_triage
        f = json.loads(bug_hunt_finding({"session_id": sid, "title": "Triage test", "severity": "P2"}))
        fid = f.get("finding_id") or f.get("data", {}).get("finding_id", "")
        r = json.loads(bug_hunt_triage({"session_id": sid, "finding_ids": [fid], "severity": "P1"}))
        assert r.get("status") != "error"
        _close_session(sid)


class TestBughuntVerifyE2E:
    """bug_hunt_verify."""

    def test_verify_no_session(self):
        from scout.bughunt.bughunt_tools import bug_hunt_verify
        r = json.loads(bug_hunt_verify({}))
        assert r.get("status") == "error"

    def test_verify_no_finding(self, scout_plugin_dir):
        sid = _start_session(scout_plugin_dir)
        from scout.bughunt.bughunt_tools import bug_hunt_verify
        r = json.loads(bug_hunt_verify({"session_id": sid, "finding_id": "nonexistent"}))
        assert r.get("status") == "error"
        _close_session(sid)


class TestBughuntFixE2E:
    """bug_hunt_fix."""

    def test_fix_no_session(self):
        from scout.bughunt.bughunt_tools import bug_hunt_fix
        r = json.loads(bug_hunt_fix({}))
        assert r.get("status") == "error"


class TestBughuntHistoryE2E:
    """bug_hunt_history."""

    def test_history_no_session(self):
        from scout.bughunt.bughunt_tools import bug_hunt_history
        r = json.loads(bug_hunt_history({}))
        assert r.get("status") != "error"


class TestBughuntExportE2E:
    """bug_hunt_export."""

    def test_export_no_session(self):
        from scout.bughunt.bughunt_tools import bug_hunt_export
        r = json.loads(bug_hunt_export({}))
        assert r.get("status") == "error"
