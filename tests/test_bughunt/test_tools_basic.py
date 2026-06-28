"""Test: Basic Tool Handler — bug_hunt_start, bug_hunt_finding, bug_hunt_list, bug_hunt_close."""

import json
from pathlib import Path
from unittest.mock import MagicMock

# Modul für Handler-Import
from scout.bughunt.bughunt_tools import (
    bug_hunt_close,
    bug_hunt_finding,
    bug_hunt_list,
    bug_hunt_start,
)

# ======================================================================
# Helper: Mock-Setup für Handler-Tests
# ======================================================================

def _mock_core(monkeypatch, tmp_path):
    """Mock bughunt_core Funktionen für Handler-Tests.

    Patched bughunt.bughunt_core (Package-Import), damit die Tool-Handler
    via _get_core() die gemockte Instanz finden.
    """
    from scout.bughunt.bughunt_core import BugHuntSession, Finding

    # Session-Verwaltung
    sessions = {}

    def mock_save_session(session):
        sessions[session.session_id] = session.to_dict()
        return session.session_id

    def mock_load_session(sid):
        if sid in sessions:
            s = BugHuntSession.from_dict(sessions[sid])
            return s
        return None

    def mock_list_sessions():
        return [v for v in sessions.values()]

    mock_tracker = MagicMock()
    mock_tracker.is_active.return_value = False
    mock_tracker.start = MagicMock()
    mock_tracker.reset = MagicMock()
    mock_tracker.track_file = MagicMock()

    def mock_get_tracker():
        return mock_tracker

    monkeypatch.setattr("bughunt.bughunt_core.save_session", mock_save_session)
    monkeypatch.setattr("bughunt.bughunt_core.load_session", mock_load_session)
    monkeypatch.setattr("bughunt.bughunt_core.list_sessions", mock_list_sessions)
    monkeypatch.setattr("bughunt.bughunt_core.get_tracker", mock_get_tracker)
    monkeypatch.setattr("bughunt.bughunt_core.BugHuntSession", BugHuntSession)
    monkeypatch.setattr("bughunt.bughunt_core.Finding", Finding)
    monkeypatch.setattr("bughunt.bughunt_core.FINDING_CATEGORIES",
                        ["security", "code-quality", "typescript", "react-next",
                         "admin-ui", "performance", "testing", "dependency", "database", "other"])

    return mock_tracker


def _ok(data):
    """Parse a handler response."""
    if isinstance(data, str):
        return json.loads(data)
    return data


# ======================================================================
# bug_hunt_start Tests
# ======================================================================

class TestBugHuntStart:
    """bug_hunt_start: Session erstellen."""

    def test_start_minimal(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        result = _ok(bug_hunt_start({"project": "/test/project"}))
        assert result["session_id"] is not None
        assert result["project"] == "/test/project"
        assert result["scope"] == "quick"
        assert result["status"] == "open"
        assert len(result["session_id"]) == 12

    def test_start_all_params(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        result = _ok(bug_hunt_start({
            "project": "/myapp",
            "scope": "comprehensive",
            "focus_areas": ["security", "performance"],
        }))
        assert result["session_id"] is not None
        assert result["project"] == "/myapp"
        assert result["scope"] == "comprehensive"
        assert result["focus_areas"] == ["security", "performance"]
        assert "instruction" in result

    def test_start_missing_project(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        result = _ok(bug_hunt_start({"scope": "quick"}))
        assert result["status"] == "error"
        assert "project" in result["error"].lower()

    def test_start_invalid_scope(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        result = _ok(bug_hunt_start({"project": "/test", "scope": "invalid"}))
        assert result["status"] == "error"
        assert "scope" in result["error"].lower()

    def test_start_empty_project(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        result = _ok(bug_hunt_start({"project": "  "}))
        assert result["status"] == "error"

    def test_start_custom_scope(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        result = _ok(bug_hunt_start({"project": "/test", "scope": "custom"}))
        assert result["scope"] == "custom"

    def test_start_inits_tracker(self, monkeypatch, tmp_path):
        mt = _mock_core(monkeypatch, tmp_path)
        bug_hunt_start({"project": "/test"})
        assert mt.start.called


# ======================================================================
# bug_hunt_finding Tests
# ======================================================================

class TestBugHuntFinding:
    """bug_hunt_finding: Finding zu Session hinzufügen."""

    def test_finding_minimal(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        # Session anlegen
        from bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        import bughunt_core as bc
        bc.save_session(s)

        result = _ok(bug_hunt_finding({
            "session_id": s.session_id,
            "title": "Test Finding",
        }))
        assert result["status"] == "open"
        assert result["title"] == "Test Finding"
        assert result["severity"] == "P2"
        assert result["total_findings"] == 1

    def test_finding_all_params(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        import bughunt_core as bc
        from bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        bc.save_session(s)

        result = _ok(bug_hunt_finding({
            "session_id": s.session_id,
            "title": "execSync in stt.ts",
            "severity": "P0",
            "category": "security",
            "file": "src/stt.ts",
            "line": 78,
            "description": "execSync mit user input",
            "evidence": 'execSync(`cmd ${input}`)',
            "pattern_id": "S001",
            "suggested_fix": "execFile verwenden",
            "status": "open",
        }))
        assert result["status"] == "open"
        assert result["severity"] == "P0"
        assert result["finding_id"] is not None

    def test_finding_invalid_session(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        result = _ok(bug_hunt_finding({
            "session_id": "nonexistent",
            "title": "Test",
        }))
        assert result["status"] == "error"

    def test_finding_empty_session_id(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        result = _ok(bug_hunt_finding({"title": "Test"}))
        assert result["status"] == "error"

    def test_finding_empty_title(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        import bughunt_core as bc
        from bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        bc.save_session(s)
        result = _ok(bug_hunt_finding({"session_id": s.session_id, "title": ""}))
        assert result["status"] == "error"

    def test_finding_invalid_severity(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        import bughunt_core as bc
        from bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        bc.save_session(s)
        result = _ok(bug_hunt_finding({"session_id": s.session_id, "title": "T", "severity": "P5"}))
        assert result["status"] == "error"

    def test_finding_invalid_category(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        import bughunt_core as bc
        from bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        bc.save_session(s)
        result = _ok(bug_hunt_finding({"session_id": s.session_id, "title": "T", "category": "xyz"}))
        assert result["status"] == "error"

    def test_finding_p0_includes_instruction(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        import bughunt_core as bc
        from bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        bc.save_session(s)
        result = _ok(bug_hunt_finding({"session_id": s.session_id, "title": "Critical", "severity": "P0"}))
        assert result["status"] == "open"
        assert "instruction" in result
        assert len(result["instruction"]) > 0

    def test_finding_tracks_file(self, monkeypatch, tmp_path):
        mt = _mock_core(monkeypatch, tmp_path)
        import bughunt_core as bc
        from bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        bc.save_session(s)
        _ok(bug_hunt_finding({
            "session_id": s.session_id, "title": "Bug", "file": "src/bug.ts"
        }))
        assert mt.track_file.called


# ======================================================================
# bug_hunt_list Tests
# ======================================================================

class TestBugHuntList:
    """bug_hunt_list: Findings filtern und anzeigen."""

    def test_list_empty(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        import bughunt_core as bc
        from bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        bc.save_session(s)
        result = _ok(bug_hunt_list({"session_id": s.session_id}))
        assert result["status"] == "ok"
        assert result["count"] == 0
        assert result["total"] == 0

    def test_list_with_findings(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        import bughunt_core as bc
        from bughunt_core import BugHuntSession, Finding
        s = BugHuntSession(project="/test")
        s.add_finding(Finding(title="P0 Finding", severity="P0"))
        s.add_finding(Finding(title="P2 Finding", severity="P2"))
        bc.save_session(s)
        result = _ok(bug_hunt_list({"session_id": s.session_id}))
        assert result["status"] == "ok"
        assert result["count"] == 2
        assert result["total"] == 2

    def test_list_filter_severity(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        import bughunt_core as bc
        from bughunt_core import BugHuntSession, Finding
        s = BugHuntSession(project="/test")
        s.add_finding(Finding(title="P0", severity="P0"))
        s.add_finding(Finding(title="P1", severity="P1"))
        bc.save_session(s)
        result = _ok(bug_hunt_list({"session_id": s.session_id, "severity": "P0"}))
        assert result["count"] == 1
        assert result["findings"][0]["title"] == "P0"

    def test_list_invalid_session(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        result = _ok(bug_hunt_list({"session_id": "nonexistent"}))
        assert result["status"] == "error"

    def test_list_empty_session_id(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        result = _ok(bug_hunt_list({}))
        assert result["status"] == "error"


# ======================================================================
# bug_hunt_close Tests
# ======================================================================

class TestBugHuntClose:
    """bug_hunt_close: Session abschliessen."""

    def test_close_session(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        import bughunt_core as bc
        from bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        bc.save_session(s)

        result = _ok(bug_hunt_close({"session_id": s.session_id, "summary": "Done"}))
        assert result["status"] == "closed"

        # Session sollte jetzt geschlossen sein
        loaded = bc.load_session(s.session_id)
        assert loaded.status == "closed"
        assert loaded.summary == "Done"

    def test_close_resets_tracker(self, monkeypatch, tmp_path):
        mt = _mock_core(monkeypatch, tmp_path)
        import bughunt_core as bc
        from bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        bc.save_session(s)
        bug_hunt_close({"session_id": s.session_id})
        assert mt.reset.called

    def test_close_without_summary(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        import bughunt_core as bc
        from bughunt_core import BugHuntSession
        s = BugHuntSession(project="/test")
        bc.save_session(s)
        result = _ok(bug_hunt_close({"session_id": s.session_id}))
        assert result["status"] == "closed"
        assert result["total_findings"] == 0

    def test_close_nonexistent(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        result = _ok(bug_hunt_close({"session_id": "nonexistent"}))
        assert result["status"] == "error"

    def test_close_empty_session_id(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        result = _ok(bug_hunt_close({}))
        assert result["status"] == "error"


# ======================================================================
# Integration: Full Workflow
# ======================================================================

class TestWorkflow:
    """Integration über alle 4 Basic Tools."""

    def test_full_workflow(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        import bughunt_core as bc

        # 1. Start
        start_res = _ok(bug_hunt_start({"project": "/myapp", "scope": "quick"}))
        assert start_res["session_id"] is not None
        sid = start_res["session_id"]

        # 2. Findings hinzufügen
        f1 = _ok(bug_hunt_finding({"session_id": sid, "title": "P0 Bug",
                                    "severity": "P0", "category": "security"}))
        assert f1["status"] == "open"
        f2 = _ok(bug_hunt_finding({"session_id": sid, "title": "P2 Bug",
                                    "severity": "P2", "category": "code-quality"}))
        assert f2["status"] == "open"

        # 3. List
        lst = _ok(bug_hunt_list({"session_id": sid}))
        assert lst["total"] == 2
        assert lst["count"] == 2

        # 4. Close
        cls = _ok(bug_hunt_close({"session_id": sid, "summary": "2 Findings"}))
        assert cls["status"] == "closed"
        assert cls["total_findings"] == 2

        # 5. Verify session closed on disk
        loaded = bc.load_session(sid)
        assert loaded.status == "closed"
        assert loaded.summary == "2 Findings"

    def test_workflow_no_findings(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)

        start_res = _ok(bug_hunt_start({"project": "/empty"}))
        sid = start_res["session_id"]

        lst = _ok(bug_hunt_list({"session_id": sid}))
        assert lst["total"] == 0

        cls = _ok(bug_hunt_close({"session_id": sid}))
        assert cls["total_findings"] == 0

    def test_workflow_multiple_findings_then_triage(self, monkeypatch, tmp_path):
        _mock_core(monkeypatch, tmp_path)
        import bughunt_core as bc
        from bughunt_core import BugHuntSession

        s = BugHuntSession(project="/test")
        bc.save_session(s)
        sid = s.session_id

        # 3 Findings hinzufügen
        for i in range(3):
            _ok(bug_hunt_finding({"session_id": sid, "title": f"Bug {i}",
                                   "severity": "P2"}))

        lst = _ok(bug_hunt_list({"session_id": sid}))
        assert lst["count"] == 3


# ======================================================================
# Integrationstest: _get_core() lädt Pattern-Bibliothek
# ======================================================================

class TestGetCoreLoadsPatterns:
    """_get_core() muss ein Modul mit geladenen Patterns zurückgeben."""

    def test_get_core_returns_module_with_patterns(self):
        """_get_core() importiert via Package-Pfad und init_patterns() läuft."""
        import sys as _sys

        # Parent-Dir für Package-Import (bughunt.bughunt_tools)
        plugin_root = Path(__file__).parent.parent
        parent = str(plugin_root.parent)
        if parent not in _sys.path:
            _sys.path.insert(0, parent)

        from scout.bughunt.tools.base import _get_core
        core = _get_core()
        assert len(core.PATTERNS_BY_ID) > 0, "_get_core() muss Patterns laden"
        cats = core.list_categories()
        assert len(cats) > 0, "Pattern-Kategorien müssen verfügbar sein"
        assert any(c["category"] == "security" for c in cats), "security-Kategorie muss existieren"

    def test_get_core_has_all_five_categories(self):
        """Alle 12 Pattern-Kategorien müssen geladen sein."""
        import sys as _sys

        plugin_root = Path(__file__).parent.parent
        parent = str(plugin_root.parent)
        if parent not in _sys.path:
            _sys.path.insert(0, parent)

        from scout.bughunt.tools.base import _get_core
        core = _get_core()
        cats = {c["category"] for c in core.list_categories()}
        expected = {"security", "code-quality", "typescript", "go", "rust",
                    "react-next", "medusa-admin-ui", "custom",
                    "java", "cpp", "ruby"}
        assert cats == expected, f"Erwartet {expected}, habe {cats}"

    def test_get_core_returns_30_patterns(self):
        """Genau 56 Patterns müssen geladen sein."""
        import sys as _sys

        plugin_root = Path(__file__).parent.parent
        parent = str(plugin_root.parent)
        if parent not in _sys.path:
            _sys.path.insert(0, parent)

        from scout.bughunt.tools.base import _get_core
        core = _get_core()
        assert len(core.PATTERNS_BY_ID) == 71, f"Erwartet 71 Patterns, habe {len(core.PATTERNS_BY_ID)}"
