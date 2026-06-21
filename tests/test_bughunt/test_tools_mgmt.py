"""Test: Management Tools — bug_hunt_export, bug_hunt_history, bug_hunt_pattern, bug_hunt_stats."""

import json
from unittest.mock import MagicMock

import pytest

from scout.bughunt.bughunt_tools import (
    bug_hunt_export, bug_hunt_history, bug_hunt_pattern, bug_hunt_stats,
)


def _mock_core(monkeypatch):
    from bughunt_core import BugHuntSession, Finding
    sessions = {}

    def mock_save_session(s):
        sessions[s.session_id] = s.to_dict()
        return s.session_id

    def mock_load_session(sid):
        if sid in sessions:
            return BugHuntSession.from_dict(sessions[sid])
        return None

    def mock_list_sessions():
        return [v for v in sessions.values()]

    monkeypatch.setattr("bughunt_core.save_session", mock_save_session)
    monkeypatch.setattr("bughunt_core.load_session", mock_load_session)
    monkeypatch.setattr("bughunt_core.list_sessions", mock_list_sessions)
    monkeypatch.setattr("bughunt_core.BugHuntSession", BugHuntSession)
    monkeypatch.setattr("bughunt_core.Finding", Finding)
    return sessions


def _ok(data):
    return json.loads(data) if isinstance(data, str) else data


# ======================================================================
# bug_hunt_export Tests
# ======================================================================

class TestBugHuntExport:
    def test_export_json(self, monkeypatch):
        s = _mock_core(monkeypatch)
        from bughunt_core import BugHuntSession
        sess = BugHuntSession(project="/test")
        s[sess.session_id] = sess.to_dict()
        result = _ok(bug_hunt_export({"session_id": sess.session_id}))
        assert result["status"] == "ok"
        assert result["format"] == "json"
        assert "content" in result
        data = json.loads(result["content"])
        assert data["project"] == "/test"

    def test_export_markdown(self, monkeypatch):
        s = _mock_core(monkeypatch)
        from bughunt_core import BugHuntSession
        sess = BugHuntSession(project="/test")
        s[sess.session_id] = sess.to_dict()
        result = _ok(bug_hunt_export({
            "session_id": sess.session_id, "format": "markdown"
        }))
        assert result["format"] == "markdown"
        assert "# Bug-Hunt Report" in result["content"]

    def test_export_no_session(self, monkeypatch):
        _mock_core(monkeypatch)
        result = _ok(bug_hunt_export({}))
        assert result["status"] == "error"

    def test_export_nonexistent(self, monkeypatch):
        _mock_core(monkeypatch)
        result = _ok(bug_hunt_export({"session_id": "x"}))
        assert result["status"] == "error"


# ======================================================================
# bug_hunt_history Tests
# ======================================================================

class TestBugHuntHistory:
    def test_history_by_id(self, monkeypatch):
        s = _mock_core(monkeypatch)
        from bughunt_core import BugHuntSession
        sess = BugHuntSession(project="/test")
        s[sess.session_id] = sess.to_dict()
        result = _ok(bug_hunt_history({"session_id": sess.session_id}))
        assert result["status"] == "ok"
        assert result["session"]["project"] == "/test"

    def test_history_list(self, monkeypatch):
        s = _mock_core(monkeypatch)
        from bughunt_core import BugHuntSession
        s1 = BugHuntSession(project="/a")
        s2 = BugHuntSession(project="/b")
        s[s1.session_id] = s1.to_dict()
        s[s2.session_id] = s2.to_dict()
        result = _ok(bug_hunt_history({}))
        assert result["count"] >= 2

    def test_history_nonexistent(self, monkeypatch):
        _mock_core(monkeypatch)
        result = _ok(bug_hunt_history({"session_id": "x"}))
        assert result["status"] == "error"

    def test_history_empty(self, monkeypatch):
        _mock_core(monkeypatch)
        result = _ok(bug_hunt_history({}))
        assert result["count"] == 0


# ======================================================================
# bug_hunt_pattern Tests
# ======================================================================

class TestBugHuntPattern:
    def test_pattern_list_all(self, monkeypatch):
        _mock_core(monkeypatch)
        import bughunt_core as core
        core.init_patterns()
        result = _ok(bug_hunt_pattern({"action": "list"}))
        assert result["count"] >= 20

    def test_pattern_list_categories(self, monkeypatch):
        _mock_core(monkeypatch)
        import bughunt_core as core
        core.init_patterns()
        result = _ok(bug_hunt_pattern({"action": "list_categories"}))
        assert result["count"] == 8

    def test_pattern_detail(self, monkeypatch):
        _mock_core(monkeypatch)
        import bughunt_core as core
        core.init_patterns()
        result = _ok(bug_hunt_pattern({"action": "detail", "pattern_id": "S001"}))
        assert result["status"] == "ok"
        assert result["pattern"]["name"] is not None
        assert result["pattern"]["category"] == "security"

    def test_pattern_detail_nonexistent(self, monkeypatch):
        _mock_core(monkeypatch)
        import bughunt_core as core
        core.init_patterns()
        result = _ok(bug_hunt_pattern({"action": "detail", "pattern_id": "X999"}))
        assert result["status"] == "error"

    def test_pattern_list_by_category(self, monkeypatch):
        _mock_core(monkeypatch)
        import bughunt_core as core
        core.init_patterns()
        result = _ok(bug_hunt_pattern({"category": "security"}))
        assert result["count"] == 12


# ======================================================================
# bug_hunt_stats Tests
# ======================================================================

class TestBugHuntStats:
    def test_stats_empty(self, monkeypatch):
        s = _mock_core(monkeypatch)
        from bughunt_core import BugHuntSession
        sess = BugHuntSession(project="/test")
        s[sess.session_id] = sess.to_dict()
        result = _ok(bug_hunt_stats({"session_id": sess.session_id}))
        assert result["total"] == 0
        assert result["project"] == "/test"

    def test_stats_with_findings(self, monkeypatch):
        s = _mock_core(monkeypatch)
        from bughunt_core import BugHuntSession, Finding
        sess = BugHuntSession(project="/test")
        sess.add_finding(Finding(title="P0a", severity="P0"))
        sess.add_finding(Finding(title="P0b", severity="P0"))
        sess.add_finding(Finding(title="P1", severity="P1"))
        s[sess.session_id] = sess.to_dict()
        result = _ok(bug_hunt_stats({"session_id": sess.session_id}))
        assert result["total"] == 3
        assert result["by_severity"]["P0"] == 2
        assert result["by_severity"]["P1"] == 1

    def test_stats_no_session(self, monkeypatch):
        _mock_core(monkeypatch)
        result = _ok(bug_hunt_stats({}))
        assert result["status"] == "error"

    def test_stats_top_files(self, monkeypatch):
        s = _mock_core(monkeypatch)
        from bughunt_core import BugHuntSession, Finding
        sess = BugHuntSession(project="/test")
        for i in range(5):
            sess.add_finding(Finding(title=f"B{i}", file=f"src/file{i}.ts"))
        s[sess.session_id] = sess.to_dict()
        result = _ok(bug_hunt_stats({"session_id": sess.session_id}))
        assert len(result["top_files"]) == 5
