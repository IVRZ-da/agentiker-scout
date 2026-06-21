"""Test: Advanced Tool Handler — bug_hunt_scan, bug_hunt_triage, bug_hunt_verify, bug_hunt_report."""

import json
from unittest.mock import MagicMock

import pytest

from scout.bughunt.bughunt_tools import (
    bug_hunt_scan, bug_hunt_triage, bug_hunt_verify, bug_hunt_report,
)


def _mock_core(monkeypatch, tmp_path):
    """Mock bughunt_core for handler tests — includes patterns."""
    from scout.bughunt.bughunt_core import BugHuntSession, Finding
    from scout.bughunt.bughunt_patterns import BugPattern

    sessions = {}

    def mock_save_session(session):
        sessions[session.session_id] = session.to_dict()
        return session.session_id

    def mock_load_session(sid):
        if sid in sessions:
            return BugHuntSession.from_dict(sessions[sid])
        return None

    def mock_list_sessions():
        return list(sessions.values())

    mock_tracker = MagicMock()
    mock_tracker.is_active.return_value = False
    mock_tracker.start = MagicMock()
    mock_tracker.reset = MagicMock()
    mock_tracker.track_file = MagicMock()

    def mock_get_tracker():
        return mock_tracker

    # Pattern mocks
    _patterns = {}

    def mock_get_pattern(pid):
        return _patterns.get(pid)

    def mock_get_patterns_by_category(cat):
        return [p for p in _patterns.values() if p.category == cat]

    def mock_list_categories():
        cats = set(p.category for p in _patterns.values())
        return [{"category": c, "count": sum(1 for p in _patterns.values() if p.category == c)}
                for c in sorted(cats)]

    # Register mocks
    monkeypatch.setattr("scout.bughunt.bughunt_core.save_session", mock_save_session)
    monkeypatch.setattr("scout.bughunt.bughunt_core.load_session", mock_load_session)
    monkeypatch.setattr("scout.bughunt.bughunt_core.list_sessions", mock_list_sessions)
    monkeypatch.setattr("scout.bughunt.bughunt_core.get_tracker", mock_get_tracker)
    monkeypatch.setattr("scout.bughunt.bughunt_core.get_pattern", mock_get_pattern)
    monkeypatch.setattr("scout.bughunt.bughunt_core.PATTERNS_BY_ID", _patterns)
    monkeypatch.setattr("scout.bughunt.bughunt_core.PATTERNS_BY_CATEGORY", {})
    monkeypatch.setattr("scout.bughunt.bughunt_core.get_patterns_by_category", mock_get_patterns_by_category)
    monkeypatch.setattr("scout.bughunt.bughunt_core.list_categories", mock_list_categories)
    monkeypatch.setattr("scout.bughunt.bughunt_core.BugHuntSession", BugHuntSession)
    monkeypatch.setattr("scout.bughunt.bughunt_core.Finding", Finding)

    return sessions, _patterns, mock_tracker


def _add_pattern(patterns, pid, name, category="security", severity="P0",
                 scan_type="code_search", scan_query="test", scan_file_glob="**/*.ts"):
    """Add a pattern to the mock pattern dict."""
    from scout.bughunt.bughunt_patterns import BugPattern
    p = BugPattern(pattern_id=pid, name=name, category=category,
                   severity=severity, scan_type=scan_type,
                   scan_query=scan_query, scan_file_glob=scan_file_glob)
    patterns[pid] = p
    return p


def _ok(data):
    if isinstance(data, str):
        return json.loads(data)
    return data


# ======================================================================
# bug_hunt_scan Tests
# ======================================================================

class TestBugHuntScan:
    """bug_hunt_scan: Automatische Scans mit Pattern-Library."""

    def test_scan_by_pattern_ids(self, monkeypatch, tmp_path):
        sessions, patterns, _ = _mock_core(monkeypatch, tmp_path)
        _add_pattern(patterns, "S001", "execSync")
        _add_pattern(patterns, "C001", "Silent Catch", category="code-quality")
        # Session anlegen
        from scout.bughunt.bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        sessions[s.session_id] = s.to_dict()

        result = _ok(bug_hunt_scan({
            "session_id": s.session_id,
            "patterns": ["S001", "C001"],
        }))
        assert result["status"] == "ok"
        assert len(result["patterns_resolved"]) == 2
        assert "S001" in result["patterns_resolved"]
        assert "C001" in result["patterns_resolved"]

    def test_scan_by_category(self, monkeypatch, tmp_path):
        sessions, patterns, _ = _mock_core(monkeypatch, tmp_path)
        _add_pattern(patterns, "S001", "execSync", category="security")
        _add_pattern(patterns, "S002", "Secrets", category="security")
        from scout.bughunt.bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        sessions[s.session_id] = s.to_dict()

        result = _ok(bug_hunt_scan({
            "session_id": s.session_id,
            "patterns": ["security"],
        }))
        assert result["status"] == "ok"
        assert len(result["patterns_resolved"]) == 2

    def test_scan_mixed_ids_and_categories(self, monkeypatch, tmp_path):
        sessions, patterns, _ = _mock_core(monkeypatch, tmp_path)
        _add_pattern(patterns, "S001", "execSync", category="security")
        _add_pattern(patterns, "C001", "Catch", category="code-quality")
        from scout.bughunt.bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        sessions[s.session_id] = s.to_dict()

        result = _ok(bug_hunt_scan({
            "session_id": s.session_id,
            "patterns": ["S001", "code-quality"],
        }))
        assert result["status"] == "ok"
        assert len(result["patterns_resolved"]) == 2

    def test_scan_no_session(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        result = _ok(bug_hunt_scan({"patterns": ["S001"]}))
        assert result["status"] == "error"

    def test_scan_no_patterns(self, monkeypatch, tmp_path):
        sessions, patterns, _ = _mock_core(monkeypatch, tmp_path)
        _add_pattern(patterns, "S001", "execSync")
        from scout.bughunt.bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        sessions[s.session_id] = s.to_dict()
        result = _ok(bug_hunt_scan({
            "session_id": s.session_id, "patterns": []
        }))
        assert result["status"] == "error"

    def test_scan_invalid_pattern(self, monkeypatch, tmp_path):
        sessions, patterns, _ = _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        sessions[s.session_id] = s.to_dict()
        result = _ok(bug_hunt_scan({
            "session_id": s.session_id,
            "patterns": ["X999"],
        }))
        assert result["status"] == "error"

    def test_scan_nonexistent_session(self, monkeypatch, tmp_path):
        sessions, patterns, _ = _mock_core(monkeypatch, tmp_path)
        _add_pattern(patterns, "S001", "execSync")
        result = _ok(bug_hunt_scan({
            "session_id": "nonexistent",
            "patterns": ["S001"],
        }))
        assert result["status"] == "error"

    def test_scan_increments_count(self, monkeypatch, tmp_path):
        sessions, patterns, _ = _mock_core(monkeypatch, tmp_path)
        _add_pattern(patterns, "S001", "execSync")
        from scout.bughunt.bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        sessions[s.session_id] = s.to_dict()
        result = _ok(bug_hunt_scan({
            "session_id": s.session_id,
            "patterns": ["S001"],
        }))
        assert result["status"] == "ok"
        # scan_count sollte inkrementiert sein
        loaded = BugHuntSession.from_dict(sessions[s.session_id])
        assert loaded.scan_count == 1

    def test_scan_includes_instruction(self, monkeypatch, tmp_path):
        sessions, patterns, _ = _mock_core(monkeypatch, tmp_path)
        _add_pattern(patterns, "S001", "execSync",
                     scan_type="code_search", scan_query="execSync")
        from scout.bughunt.bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        sessions[s.session_id] = s.to_dict()
        result = _ok(bug_hunt_scan({
            "session_id": s.session_id,
            "patterns": ["S001"],
        }))
        assert "instruction" in result
        # code_search-Patterns landen in manual_scan_instructions
        assert "manual_scan_instructions" in result
        assert any("execSync" in instr for instr in result["manual_scan_instructions"])

    def test_scan_generates_grep_instruction(self, monkeypatch, tmp_path):
        sessions, patterns, _ = _mock_core(monkeypatch, tmp_path)
        _add_pattern(patterns, "S002", "Secrets",
                     scan_type="grep", scan_query="secret", scan_file_glob="**/*.ts")
        from scout.bughunt.bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        sessions[s.session_id] = s.to_dict()
        result = _ok(bug_hunt_scan({
            "session_id": s.session_id,
            "patterns": ["S002"],
        }))
        # grep-Patterns werden automatisch ausgeführt (Zeilen in auto_findings/manual)
        assert "instruction" in result
        assert "auto_findings" in result or "manual_scan_instructions" in result


# ======================================================================
# bug_hunt_triage Tests
# ======================================================================

class TestBugHuntTriage:
    """bug_hunt_triage: Findings priorisieren."""

    def test_triage_single(self, monkeypatch, tmp_path):
        sessions, _, _ = _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_core import BugHuntSession, Finding
        s = BugHuntSession(project="/test")
        fid = s.add_finding(Finding(title="Bug", severity="P0"))
        sessions[s.session_id] = s.to_dict()

        result = _ok(bug_hunt_triage({
            "session_id": s.session_id,
            "finding_ids": [fid],
            "severity": "P1",
            "status": "triaged",
        }))
        assert result["status"] == "ok"
        assert result["updated"] == 1

    def test_triage_multiple(self, monkeypatch, tmp_path):
        sessions, _, _ = _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_core import BugHuntSession, Finding
        s = BugHuntSession(project="/test")
        f1 = s.add_finding(Finding(title="A", severity="P0"))
        f2 = s.add_finding(Finding(title="B", severity="P2"))
        sessions[s.session_id] = s.to_dict()

        result = _ok(bug_hunt_triage({
            "session_id": s.session_id,
            "finding_ids": [f1, f2],
            "severity": "P1",
        }))
        assert result["updated"] == 2

    def test_triage_no_session(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        result = _ok(bug_hunt_triage({"finding_ids": ["x"]}))
        assert result["status"] == "error"

    def test_triage_no_ids(self, monkeypatch, tmp_path):
        sessions, _, _ = _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        sessions[s.session_id] = s.to_dict()
        result = _ok(bug_hunt_triage({"session_id": s.session_id}))
        assert result["status"] == "error"

    def test_triage_invalid_severity(self, monkeypatch, tmp_path):
        sessions, _, _ = _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        sessions[s.session_id] = s.to_dict()
        result = _ok(bug_hunt_triage({
            "session_id": s.session_id,
            "finding_ids": ["x"],
            "severity": "P5",
        }))
        assert result["status"] == "error"

    def test_triage_invalid_status(self, monkeypatch, tmp_path):
        sessions, _, _ = _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        sessions[s.session_id] = s.to_dict()
        result = _ok(bug_hunt_triage({
            "session_id": s.session_id,
            "finding_ids": ["x"],
            "status": "invalid",
        }))
        assert result["status"] == "error"

    def test_triage_no_updates(self, monkeypatch, tmp_path):
        sessions, _, _ = _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        sessions[s.session_id] = s.to_dict()
        result = _ok(bug_hunt_triage({
            "session_id": s.session_id,
            "finding_ids": ["x"],
        }))
        assert result["status"] == "error"

    def test_triage_notes(self, monkeypatch, tmp_path):
        sessions, _, _ = _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_core import BugHuntSession, Finding
        s = BugHuntSession(project="/test")
        fid = s.add_finding(Finding(title="Bug"))
        sessions[s.session_id] = s.to_dict()
        result = _ok(bug_hunt_triage({
            "session_id": s.session_id,
            "finding_ids": [fid],
            "notes": "This is a false positive",
            "status": "false_positive",
        }))
        assert result["updated"] == 1


# ======================================================================
# bug_hunt_verify Tests
# ======================================================================

class TestBugHuntVerify:
    """bug_hunt_verify: Fix-Verifikation."""

    def test_verify_with_pattern(self, monkeypatch, tmp_path):
        sessions, patterns, _ = _mock_core(monkeypatch, tmp_path)
        _add_pattern(patterns, "S001", "execSync",
                     scan_query="execSync", scan_file_glob="**/*.ts")
        from scout.bughunt.bughunt_core import BugHuntSession, Finding
        s = BugHuntSession(project="/test")
        fid = s.add_finding(Finding(title="execSync in stt.ts", file="src/stt.ts",
                                     line=78, pattern_id="S001"))
        sessions[s.session_id] = s.to_dict()

        result = _ok(bug_hunt_verify({
            "session_id": s.session_id,
            "finding_id": fid,
        }))
        assert result["status"] == "ok"
        assert "instruction" in result

    def test_verify_no_pattern(self, monkeypatch, tmp_path):
        sessions, _, _ = _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_core import BugHuntSession, Finding
        s = BugHuntSession(project="/test")
        fid = s.add_finding(Finding(title="Manual finding", file="x.ts"))
        sessions[s.session_id] = s.to_dict()

        result = _ok(bug_hunt_verify({
            "session_id": s.session_id,
            "finding_id": fid,
        }))
        assert result["status"] == "ok"
        assert "read_file" in result["instruction"]

    def test_verify_no_session(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        result = _ok(bug_hunt_verify({"finding_id": "x"}))
        assert result["status"] == "error"

    def test_verify_no_finding_id(self, monkeypatch, tmp_path):
        sessions, _, _ = _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        sessions[s.session_id] = s.to_dict()
        result = _ok(bug_hunt_verify({"session_id": s.session_id}))
        assert result["status"] == "error"

    def test_verify_nonexistent_finding(self, monkeypatch, tmp_path):
        sessions, _, _ = _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        sessions[s.session_id] = s.to_dict()
        result = _ok(bug_hunt_verify({
            "session_id": s.session_id,
            "finding_id": "nonexistent",
        }))
        assert result["status"] == "error"

    def test_verify_finding_details_in_response(self, monkeypatch, tmp_path):
        sessions, _, _ = _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_core import BugHuntSession, Finding
        s = BugHuntSession(project="/test")
        fid = s.add_finding(Finding(title="Test Bug", file="src/test.ts"))
        sessions[s.session_id] = s.to_dict()

        result = _ok(bug_hunt_verify({
            "session_id": s.session_id,
            "finding_id": fid,
        }))
        assert result["finding"]["title"] == "Test Bug"
        assert result["finding"]["file"] == "src/test.ts"


# ======================================================================
# bug_hunt_report Tests
# ======================================================================

class TestBugHuntReport:
    """bug_hunt_report: Strukturierte Reports."""

    def test_report_json_default(self, monkeypatch, tmp_path):
        sessions, _, _ = _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test", scope="comprehensive")
        sessions[s.session_id] = s.to_dict()
        result = _ok(bug_hunt_report({"session_id": s.session_id}))
        assert result["status"] == "open"
        assert result["format"] == "json"
        assert "findings" in result
        assert result["project"] == "/test"

    def test_report_markdown(self, monkeypatch, tmp_path):
        sessions, _, _ = _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_core import BugHuntSession, Finding
        s = BugHuntSession(project="/test")
        s.add_finding(Finding(title="Bug A", severity="P0"))
        sessions[s.session_id] = s.to_dict()
        result = _ok(bug_hunt_report({
            "session_id": s.session_id,
            "format": "markdown",
        }))
        assert result["format"] == "markdown"
        assert "# Bug-Hunt Report" in result["report"]
        assert "Bug A" in result["report"]

    def test_report_empty_session(self, monkeypatch, tmp_path):
        sessions, _, _ = _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        sessions[s.session_id] = s.to_dict()
        result = _ok(bug_hunt_report({"session_id": s.session_id}))
        assert result["total_findings"] == 0
        assert result["counts_by_severity"]["P0"] == 0

    def test_report_no_session(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        result = _ok(bug_hunt_report({}))
        assert result["status"] == "error"

    def test_report_count_by_severity(self, monkeypatch, tmp_path):
        sessions, _, _ = _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_core import BugHuntSession, Finding
        s = BugHuntSession(project="/test")
        s.add_finding(Finding(title="P0a", severity="P0"))
        s.add_finding(Finding(title="P0b", severity="P0"))
        s.add_finding(Finding(title="P1", severity="P1"))
        sessions[s.session_id] = s.to_dict()
        result = _ok(bug_hunt_report({"session_id": s.session_id}))
        assert result["counts_by_severity"]["P0"] == 2
        assert result["counts_by_severity"]["P1"] == 1


# ======================================================================
# Integration: Scan → Finding → Triage → Report
# ======================================================================

class TestAdvancedWorkflow:
    """Integration über Scan, Triage, Verify, Report."""

    def test_scan_to_report_workflow(self, monkeypatch, tmp_path):
        sessions, patterns, _ = _mock_core(monkeypatch, tmp_path)
        _add_pattern(patterns, "S001", "execSync")
        _add_pattern(patterns, "C001", "Catch", category="code-quality")
        from scout.bughunt.bughunt_core import BugHuntSession, Finding
        s = BugHuntSession(project="/myapp", scope="quick")
        f1 = s.add_finding(Finding(title="execSync", severity="P0",
                                    pattern_id="S001", file="src/stt.ts"))
        f2 = s.add_finding(Finding(title="Silent Catch", severity="P1",
                                    pattern_id="C001", file="src/api.ts"))
        sessions[s.session_id] = s.to_dict()
        sid = s.session_id

        # 1. Scan (simuliert)
        scan_res = _ok(bug_hunt_scan({
            "session_id": sid,
            "patterns": ["S001", "C001"],
        }))
        assert scan_res["status"] == "ok"
        assert len(scan_res["patterns_resolved"]) == 2

        # 2. Triage
        triage_res = _ok(bug_hunt_triage({
            "session_id": sid,
            "finding_ids": [f1],
            "severity": "P1",
        }))
        assert triage_res["updated"] == 1

        # 3. Verify
        verify_res = _ok(bug_hunt_verify({
            "session_id": sid,
            "finding_id": f1,
        }))
        assert verify_res["status"] == "ok"

        # 4. Report
        report_res = _ok(bug_hunt_report({
            "session_id": sid,
            "format": "json",
        }))
        assert report_res["total_findings"] == 2
        assert report_res["counts_by_severity"]["P1"] >= 1
