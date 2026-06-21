"""Tests for bug_hunt_fix — Auto-Fix Prompt Generator.

Nutzt das _mock_core Pattern aus test_tools_basic.py für Tool-Integration-Tests.
"""
import json
from unittest.mock import MagicMock

import pytest


# ═══════════════════════════════════════════════════════════════════════
# build_fix_prompt (reine Logik, kein Mock nötig)
# ═══════════════════════════════════════════════════════════════════════

class TestBuildFixPrompt:
    """build_fix_prompt — generiert Subagent-Prompt."""

    def test_basic_finding(self):
        from scout.bughunt.bughunt_fix import build_fix_prompt
        finding = {
            "title": "execSync in stt.ts",
            "file": "src/modules/stt.ts",
            "line": 78,
            "severity": "P0",
            "evidence": 'execSync(`ffmpeg -i "${inputFile}" ...`)',
            "description": "Shell-Injection möglich",
            "pattern_id": "S001",
            "suggested_fix": "execFile mit param-Array verwenden",
        }
        prompt = build_fix_prompt(finding)
        assert isinstance(prompt, str)
        assert "execSync in stt.ts" in prompt
        assert "src/modules/stt.ts" in prompt
        assert "execFile" in prompt

    def test_with_pattern(self):
        from scout.bughunt.bughunt_fix import build_fix_prompt
        finding = {
            "title": "Silent Catch", "file": "src/api/auth.ts", "line": 42,
            "severity": "P1", "evidence": "catch {}",
            "description": "Fehler wird geschluckt", "pattern_id": "C001",
            "suggested_fix": "",
        }
        pattern = {
            "pattern_id": "C001", "name": "Silent Catch",
            "fix_description": "catch (err) { logger.error(err) } hinzufügen",
            "scan_type": "code_search", "scan_query": "catch\\s*\\{\\s*\\}",
            "scan_file_glob": "**/*.ts",
        }
        prompt = build_fix_prompt(finding, pattern)
        assert "logger.error" in prompt
        assert "src/api/auth.ts" in prompt

    def test_with_suggested_fix(self):
        from scout.bughunt.bughunt_fix import build_fix_prompt
        finding = {
            "title": "N+1 Query", "file": "src/lib/data.ts", "line": 15,
            "severity": "P1", "evidence": "N+1", "description": "N+1 Query Pattern",
            "pattern_id": "C003",
            "suggested_fix": "Promise.all(ids.map(id => db.find(id))) verwenden",
        }
        prompt = build_fix_prompt(finding)
        assert "Promise.all" in prompt

    def test_python_file_verify(self):
        from scout.bughunt.bughunt_fix import build_fix_prompt
        finding = {"title": "print", "file": "src/module.py", "line": 10,
                   "severity": "P2", "evidence": "print", "description": "Test",
                   "pattern_id": "C007", "suggested_fix": "logger.info"}
        prompt = build_fix_prompt(finding)
        assert "python3" in prompt

    def test_ts_file_verify(self):
        from scout.bughunt.bughunt_fix import build_fix_prompt
        finding = {"title": "Bug", "file": "src/app.ts", "line": 5,
                   "severity": "P2", "evidence": "x", "description": "Test",
                   "pattern_id": "T001", "suggested_fix": "Fix"}
        prompt = build_fix_prompt(finding)
        assert "tsc" in prompt or "npx" in prompt

    def test_no_pattern(self):
        from scout.bughunt.bughunt_fix import build_fix_prompt
        finding = {"title": "Manual Bug", "file": "src/file.ts", "line": 1,
                   "severity": "P3", "evidence": "x", "description": "Kein Pattern",
                   "pattern_id": "", "suggested_fix": "Bitte manuell prüfen"}
        prompt = build_fix_prompt(finding)
        assert "Bitte manuell prüfen" in prompt


# ═══════════════════════════════════════════════════════════════════════
# Helper: Mock-Setup (wie test_tools_basic._mock_core)
# ═══════════════════════════════════════════════════════════════════════

def _mock_core(monkeypatch, tmp_path):
    """Mock bughunt_core für bug_hunt_fix Tool-Tests."""
    from scout.bughunt.bughunt_core import BugHuntSession, Finding

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

    monkeypatch.setattr("scout.bughunt.bughunt_core.save_session", mock_save_session)
    monkeypatch.setattr("scout.bughunt.bughunt_core.load_session", mock_load_session)
    monkeypatch.setattr("scout.bughunt.bughunt_core.list_sessions", mock_list_sessions)
    monkeypatch.setattr("scout.bughunt.bughunt_core.get_tracker", lambda: mock_tracker)
    monkeypatch.setattr("scout.bughunt.bughunt_core.BugHuntSession", BugHuntSession)
    monkeypatch.setattr("scout.bughunt.bughunt_core.Finding", Finding)


def _ok(data):
    """Parse handler response JSON."""
    if isinstance(data, str):
        return json.loads(data)
    return data


# ═══════════════════════════════════════════════════════════════════════
# bug_hunt_fix Tool-Integration
# ═══════════════════════════════════════════════════════════════════════

class TestBugHuntFixTool:
    """Tool-Integration: bug_hunt_fix über die Tool-Schnittstelle."""

    def test_fix_generates_prompt(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_tools import bug_hunt_fix
        from scout.bughunt.bughunt_core import BugHuntSession, Finding

        s = BugHuntSession(project="/test")
        f = Finding(title="execSync", severity="P0", pattern_id="S001",
                     file="src/stt.ts", line=78,
                     evidence='execSync(`ffmpeg ...`)',
                     suggested_fix="execFile verwenden")
        fid = s.add_finding(f)
        from scout.bughunt.bughunt_core import save_session
        save_session(s)

        result = _ok(bug_hunt_fix({
            "session_id": s.session_id,
            "finding_id": fid,
        }))
        assert result["status"] == "ok"
        assert result["finding_id"] == fid
        assert "fix_prompt" in result
        assert "execFile" in result["fix_prompt"]

    def test_fix_missing_session(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_tools import bug_hunt_fix
        result = _ok(bug_hunt_fix({"session_id": "", "finding_id": "x"}))
        assert result["status"] == "error"

    def test_fix_missing_finding(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_tools import bug_hunt_fix
        from scout.bughunt.bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        result = _ok(bug_hunt_fix({"session_id": s.session_id, "finding_id": ""}))
        assert result["status"] == "error"

    def test_fix_nonexistent_finding(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_tools import bug_hunt_fix
        from scout.bughunt.bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        result = _ok(bug_hunt_fix({
            "session_id": s.session_id,
            "finding_id": "nonexistent",
        }))
        assert result["status"] == "error"

    def test_fix_with_override(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        from scout.bughunt.bughunt_tools import bug_hunt_fix
        from scout.bughunt.bughunt_core import BugHuntSession, Finding, save_session

        s = BugHuntSession(project="/test")
        f = Finding(title="Silent Catch", severity="P1",
                     file="src/api.ts", line=42, evidence="catch {}",
                     suggested_fix="Alte Fix-Anweisung")
        fid = s.add_finding(f)
        save_session(s)

        result = _ok(bug_hunt_fix({
            "session_id": s.session_id,
            "finding_id": fid,
            "fix_instruction": "NEUE Fix-Anweisung: toast.error() hinzufügen",
        }))
        assert result["status"] == "ok"
        assert "NEUE Fix-Anweisung" in result["fix_prompt"]
        assert "Alte Fix-Anweisung" not in result["fix_prompt"]

    def test_fix_with_pattern(self, monkeypatch, tmp_path):
        """Finding mit Pattern-ID → Pattern-Details im Prompt."""
        _mock_core(monkeypatch, tmp_path)
        import scout.bughunt.bughunt_core as core
        core.init_patterns()

        from scout.bughunt.bughunt_tools import bug_hunt_fix
        from scout.bughunt.bughunt_core import BugHuntSession, Finding, save_session

        s = BugHuntSession(project="/test")
        f = Finding(title="execSync", severity="P0", pattern_id="S001",
                     file="src/stt.ts", line=78, evidence='execSync(`...`)')
        fid = s.add_finding(f)
        save_session(s)

        result = _ok(bug_hunt_fix({
            "session_id": s.session_id,
            "finding_id": fid,
        }))
        assert result["status"] == "ok"
        assert "fix_prompt" in result
        assert len(result["fix_prompt"]) > 100
