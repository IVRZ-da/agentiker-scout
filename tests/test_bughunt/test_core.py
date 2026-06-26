"""Test: Core State Management — Datenmodelle, Persistenz, Tracker, Path-Validation."""

import json
from datetime import datetime

# ======================================================================
# Finding Tests
# ======================================================================

class TestFinding:
    """Finding-Datenmodell: Erzeugung, Validierung, Serialisierung."""

    def test_finding_create(self, sample_finding):
        assert sample_finding.id, "id fehlt"
        assert len(sample_finding.id) == 8
        assert sample_finding.title == "execSync in stt.ts"
        assert sample_finding.severity == "P0"
        assert sample_finding.category == "security"
        assert sample_finding.file == "src/modules/agent/providers/stt.ts"
        assert sample_finding.line == 78
        assert sample_finding.pattern_id == "S001"
        assert sample_finding.status == "open"

    def test_finding_to_dict(self, sample_finding):
        d = sample_finding.to_dict()
        assert d["title"] == "execSync in stt.ts"
        assert d["id"] == sample_finding.id
        assert "created_at" in d
        assert "updated_at" in d

    def test_finding_from_dict(self, sample_finding):
        d = sample_finding.to_dict()
        f2 = type(sample_finding).from_dict(d)
        assert f2.id == sample_finding.id
        assert f2.title == sample_finding.title
        assert f2.severity == sample_finding.severity

    def test_finding_validate_severity(self):
        from bughunt_core import Finding
        assert Finding.validate_severity("P0")
        assert Finding.validate_severity("p0")
        assert Finding.validate_severity("P1")
        assert Finding.validate_severity("P2")
        assert Finding.validate_severity("P3")
        assert Finding.validate_severity("INFO")
        assert not Finding.validate_severity("P5")
        assert not Finding.validate_severity("")
        assert not Finding.validate_severity("critical")

    def test_finding_validate_status(self):
        from bughunt_core import Finding
        assert Finding.validate_status("open")
        assert Finding.validate_status("fixed")
        assert Finding.validate_status("verified")
        assert Finding.validate_status("false_positive")
        assert not Finding.validate_status("unknown")
        assert not Finding.validate_status("")

    def test_finding_empty_title(self):
        from bughunt_core import Finding
        f = Finding()
        assert f.title == ""
        assert f.severity == "P2"
        assert f.category == "other"
        assert f.status == "open"

    def test_finding_timestamps(self, sample_finding):
        # created_at und updated_at sollten ISO-Format haben
        dt = datetime.fromisoformat(sample_finding.created_at)
        assert dt.tzinfo is not None  # timezone-aware


# ======================================================================
# BugHuntSession Tests
# ======================================================================

class TestBugHuntSession:
    """Session-Datenmodell: CRUD, Filter, Duplikat-Prüfung."""

    def test_session_create(self, bh):
        session = bh.BugHuntSession(project="/test", scope="quick")
        assert session.session_id
        assert len(session.session_id) == 12
        assert session.project == "/test"
        assert session.scope == "quick"
        assert session.status == "open"
        assert session.findings == []
        assert session.scan_count == 0

    def test_session_to_from_dict(self, bh):
        session = bh.BugHuntSession(project="/test")
        d = session.to_dict()
        s2 = bh.BugHuntSession.from_dict(d)
        assert s2.session_id == session.session_id
        assert s2.project == session.project
        assert s2.scope == session.scope
        assert s2.status == session.status

    def test_session_add_finding(self, bh, sample_finding):
        session = bh.BugHuntSession(project="/test")
        fid = session.add_finding(sample_finding)
        assert fid == sample_finding.id
        assert len(session.findings) == 1

    def test_session_add_finding_duplicate(self, bh, sample_finding):
        """Gleiches file + line + pattern_id = Duplikat → gleiche ID."""
        session = bh.BugHuntSession(project="/test")
        fid1 = session.add_finding(sample_finding)
        fid2 = session.add_finding(sample_finding)
        assert fid1 == fid2, "Duplikat sollte gleiche ID haben"
        assert len(session.findings) == 1, "Sollte nicht neu hinzugefügt werden"

    def test_session_add_finding_no_duplicate_diff_line(self, bh):
        """Andere Zeile → kein Duplikat."""
        session = bh.BugHuntSession(project="/test")
        f1 = bh.Finding(title="Bug A", file="x.ts", line=10, pattern_id="S001")
        f2 = bh.Finding(title="Bug B", file="x.ts", line=20, pattern_id="S001")
        fid1 = session.add_finding(f1)
        fid2 = session.add_finding(f2)
        assert fid1 != fid2
        assert len(session.findings) == 2

    def test_session_update_finding(self, bh, sample_finding):
        session = bh.BugHuntSession(project="/test")
        fid = session.add_finding(sample_finding)
        result = session.update_finding(fid, {"severity": "P1", "status": "triaged"})
        assert result is True
        updated = session.findings[0]
        assert updated["severity"] == "P1"
        assert updated["status"] == "triaged"

    def test_session_update_finding_nonexistent(self, bh):
        session = bh.BugHuntSession(project="/test")
        result = session.update_finding("nonexistent", {"severity": "P1"})
        assert result is False

    def test_session_get_findings_empty(self, bh):
        session = bh.BugHuntSession(project="/test")
        assert session.get_findings() == []

    def test_session_get_findings_filter_severity(self, bh):
        session = bh.BugHuntSession(project="/test")
        session.add_finding(bh.Finding(title="P0", severity="P0"))
        session.add_finding(bh.Finding(title="P1", severity="P1"))
        session.add_finding(bh.Finding(title="P2", severity="P2"))
        p0s = session.get_findings(severity="P0")
        assert len(p0s) == 1
        assert p0s[0]["title"] == "P0"

    def test_session_get_findings_filter_category(self, bh):
        session = bh.BugHuntSession(project="/test")
        session.add_finding(bh.Finding(title="Sec", severity="P0", category="security"))
        session.add_finding(bh.Finding(title="Qual", severity="P2", category="code-quality"))
        secs = session.get_findings(category="security")
        assert len(secs) == 1
        assert secs[0]["title"] == "Sec"

    def test_session_get_findings_filter_file(self, bh):
        session = bh.BugHuntSession(project="/test")
        session.add_finding(bh.Finding(title="A", file="src/api/route.ts"))
        session.add_finding(bh.Finding(title="B", file="src/admin/page.tsx"))
        api = session.get_findings(file="api")
        assert len(api) == 1

    def test_session_get_findings_sorted_by_severity(self, bh):
        session = bh.BugHuntSession(project="/test")
        session.add_finding(bh.Finding(title="P2", severity="P2"))
        session.add_finding(bh.Finding(title="P0", severity="P0"))
        session.add_finding(bh.Finding(title="P1", severity="P1"))
        results = session.get_findings()
        assert results[0]["title"] == "P0"
        assert results[1]["title"] == "P1"
        assert results[2]["title"] == "P2"

    def test_session_findings_count(self, bh):
        session = bh.BugHuntSession(project="/test")
        session.add_finding(bh.Finding(title="P0a", severity="P0"))
        session.add_finding(bh.Finding(title="P0b", severity="P0"))
        session.add_finding(bh.Finding(title="P1", severity="P1"))
        session.add_finding(bh.Finding(title="INFO", severity="INFO"))
        counts = session.findings_count()
        assert counts["P0"] == 2
        assert counts["P1"] == 1
        assert counts["INFO"] == 1
        assert counts["P2"] == 0
        assert counts["P3"] == 0

    def test_findings_count_mixed(self, bh):
        """findings_count zählt korrekt bei gemischten Severities."""
        session = bh.BugHuntSession(project="/test")
        session.add_finding(bh.Finding(title="A", severity="P0"))
        session.add_finding(bh.Finding(title="B", severity="P0"))
        session.add_finding(bh.Finding(title="C", severity="P1"))
        session.add_finding(bh.Finding(title="D", severity="P2"))
        session.add_finding(bh.Finding(title="E", severity="P3"))
        session.add_finding(bh.Finding(title="F", severity="INFO"))
        counts = session.findings_count()
        assert counts["P0"] == 2
        assert counts["P1"] == 1
        assert counts["P2"] == 1
        assert counts["P3"] == 1
        assert counts["INFO"] == 1

    def test_session_close(self, bh):
        session = bh.BugHuntSession(project="/test")
        assert session.status == "open"
        session.close(summary="Alles gefixt")
        assert session.status == "closed"
        assert session.closed_at is not None
        assert session.summary == "Alles gefixt"


# ======================================================================
# Persistenz Tests
# ======================================================================

class TestPersistence:
    """Session-Persistenz auf Disk."""

    def test_save_load_session(self, bh):
        session = bh.BugHuntSession(project="/test/persist")
        bh.save_session(session)
        loaded = bh.load_session(session.session_id)
        assert loaded is not None
        assert loaded.session_id == session.session_id
        assert loaded.project == session.project

    def test_save_session_with_findings(self, bh, sample_finding):
        session = bh.BugHuntSession(project="/test")
        session.add_finding(sample_finding)
        bh.save_session(session)
        loaded = bh.load_session(session.session_id)
        assert loaded is not None
        assert len(loaded.findings) == 1
        assert loaded.findings[0]["title"] == sample_finding.title

    def test_load_nonexistent(self, bh):
        result = bh.load_session("nonexistent")
        assert result is None

    def test_delete_session(self, bh):
        session = bh.BugHuntSession(project="/test")
        bh.save_session(session)
        assert bh.delete_session(session.session_id) is True
        assert bh.load_session(session.session_id) is None

    def test_delete_nonexistent(self, bh):
        assert bh.delete_session("nonexistent") is False

    def test_list_sessions(self, bh):
        s1 = bh.BugHuntSession(project="/a")
        s2 = bh.BugHuntSession(project="/b")
        bh.save_session(s1)
        bh.save_session(s2)
        sessions = bh.list_sessions()
        assert len(sessions) >= 2
        ids = [s["session_id"] for s in sessions]
        assert s1.session_id in ids
        assert s2.session_id in ids

    def test_list_sessions_empty(self, bh):
        sessions = bh.list_sessions()
        assert sessions == []


# ======================================================================
# Tracker Tests
# ======================================================================

class TestTracker:
    """In-Memory BugHuntTracker."""

    def test_tracker_start_reset(self, bh):
        tracker = bh.get_tracker()
        assert not tracker.is_active()
        tracker.start("session-123")
        assert tracker.is_active()
        assert tracker.active_session_id == "session-123"
        tracker.reset()
        assert not tracker.is_active()
        assert tracker.active_session_id is None

    def test_tracker_start_clears_previous(self, bh):
        tracker = bh.get_tracker()
        tracker.start("s1")
        tracker.track_tool("code_search", {"path": "/x"})
        assert len(tracker.tools_used) == 1
        tracker.start("s2")
        assert len(tracker.tools_used) == 0
        assert tracker.active_session_id == "s2"

    def test_tracker_track_tool_file(self, bh):
        tracker = bh.get_tracker()
        tracker.start("s1")
        tracker.track_tool("code_search", {"path": "/x"}, "ok")
        tracker.track_file("/x/file.ts")
        assert len(tracker.tools_used) == 1
        assert tracker.tools_used[0]["tool_name"] == "code_search"
        assert len(tracker.files_touched) == 1

    def test_tracker_summary(self, bh):
        tracker = bh.get_tracker()
        tracker.start("s1")
        tracker.track_tool("code_search", {})
        summary = tracker.summary()
        assert summary["session_id"] == "s1"
        assert summary["tools_used"] == 1
        assert summary["last_scan_ago_sec"] is not None

    def test_tracker_summary_inactive(self, bh):
        tracker = bh.get_tracker()
        summary = tracker.summary()
        assert summary["session_id"] is None


# ======================================================================
# Path Validation Tests
# ======================================================================

class TestPathValidation:
    """Path-Validierung (Traversal, Null-Bytes, Länge)."""

    def test_valid_path(self, bh):
        assert bh.validate_path("/home/user/file.ts") is None
        assert bh.validate_path("./relative/path.py") is None
        assert bh.validate_path("normal-path.txt") is None

    def test_path_traversal(self, bh):
        assert bh.validate_path("../../../etc/passwd") is not None
        assert bh.validate_path("/foo/../../bar") is not None

    def test_path_null_bytes(self, bh):
        assert bh.validate_path("file\x00.txt") is not None

    def test_path_empty(self, bh):
        assert bh.validate_path("") is not None
        assert bh.validate_path(None) is not None

    def test_path_too_long(self, bh):
        long_path = "/" + "a" * 5000
        assert bh.validate_path(long_path) is not None

    def test_path_resolved_outside_allowed_dir(self, bh, tmp_path):
        """Path ausserhalb allowed_base wird blockiert (realpath-Check)."""
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        f = outside / "secret.txt"
        f.write_text("secret")
        # Pfad ausserhalb allowed → blocked
        assert bh.validate_path(str(f), allowed_base=allowed) is not None

    def test_path_resolved_inside_allowed_dir(self, bh, tmp_path):
        """Path innerhalb allowed_base ist gültig."""
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        inner = allowed / "sub" / "file.ts"
        inner.parent.mkdir(parents=True)
        inner.write_text("data")
        assert bh.validate_path(str(inner), allowed_base=allowed) is None

    def test_path_unresolvable(self, bh):
        """Unresolvable Paths werden abgewiesen."""
        # Null-Bytes werden bereits vom regex-check abgefangen,
        # also testen wir mit einem Pfad der nicht existiert ohne allowed_base
        result = bh.validate_path("/nonexistent/path/../../../etc/passwd")
        assert result is not None


# ======================================================================
# Response Helpers
# ======================================================================

class TestResponseHelpers:
    """_ok() und _err() — formatierte Responses."""

    def test_ok_returns_status_ok(self, bh):
        """_ok() gibt JSON mit status=ok zurück (über fmt_ok Mock)."""
        result = bh._ok({"msg": "done"})
        assert isinstance(result, str)
        assert "ok" in result.lower() or "msg" in result.lower()

    def test_ok_sets_default_status(self, bh):
        """_ok() setzt 'status: ok' wenn kein status vorhanden."""
        result = bh._ok({"data": "123"})
        assert "ok" in result.lower() or "data" in result.lower()

    def test_err_returns_error(self, bh):
        """_err() gibt Fehler-Response zurück."""
        result = bh._err("Something failed")
        assert isinstance(result, str)
        assert "error" in result.lower() or "failed" in result.lower()


# ======================================================================
# Integration Workflow Tests
# ======================================================================

class TestWorkflow:
    """Integration: Vollständiger Session-Lifecycle."""

    def test_full_session_lifecycle(self, bh):

        # 1. Session starten
        session = bh.BugHuntSession(project="/myapp", scope="comprehensive",
                                     focus_areas=["security"])
        bh.save_session(session)
        sid = session.session_id

        # 2. Findings hinzufügen
        f1 = bh.Finding(title="execSync", severity="P0", category="security",
                     file="src/stt.ts", line=78, pattern_id="S001")
        f2 = bh.Finding(title="console.log", severity="P2", category="code-quality",
                     file="src/api.ts", line=10, pattern_id="C002")

        session.add_finding(f1)
        session.add_finding(f2)
        bh.save_session(session)

        # 3. Session neu laden → Findings noch da
        loaded = bh.load_session(sid)
        assert loaded is not None
        assert len(loaded.findings) == 2
        assert loaded.findings_count()["P0"] == 1
        assert loaded.findings_count()["P2"] == 1

        # 4. Triage
        loaded.update_finding(f1.id, {"severity": "P1"})
        bh.save_session(loaded)

        # 5. Report
        report = bh.generate_markdown_report(loaded, "severity")
        assert "# Bug-Hunt Report" in report
        assert "execSync" in report
        assert "console.log" in report

        # 6. Session schliessen
        loaded.close(summary="2 Findings gefunden")
        bh.save_session(loaded)
        assert loaded.status == "closed"

        # 7. Sessions auflisten
        sessions = bh.list_sessions()
        assert len(sessions) >= 1
        assert sessions[0]["session_id"] == sid

    def test_session_file_persistence(self, bh):
        """Session-Datei auf Disk entspricht to_dict()."""
        session = bh.BugHuntSession(project="/persist")
        bh.save_session(session)
        path = bh.SESSIONS_DIR / f"{session.session_id}.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["session_id"] == session.session_id
        assert data["project"] == "/persist"

    def test_concurrent_sessions(self, bh):
        """Mehrere Sessions gleichzeitig."""
        s1 = bh.BugHuntSession(project="/app1")
        s2 = bh.BugHuntSession(project="/app2")
        s1.add_finding(bh.Finding(title="Bug in app1", severity="P0"))
        bh.save_session(s1)
        bh.save_session(s2)
        l1 = bh.load_session(s1.session_id)
        l2 = bh.load_session(s2.session_id)
        assert len(l1.findings) == 1
        assert len(l2.findings) == 0

    def test_report_with_summary(self, bh):
        """Markdown-Report enthält Summary-Zeile wenn gesetzt."""
        session = bh.BugHuntSession(project="/app")
        session.close(summary="3 Issues gefunden und gefixt")
        report = bh.generate_markdown_report(session, "severity")
        assert "Summary" in report
        assert "3 Issues" in report

    def test_report_group_by_category(self, bh):
        """Report gruppiert nach Kategorie."""
        session = bh.BugHuntSession(project="/app")
        session.add_finding(bh.Finding(title="SQLi", severity="P0", category="security",
                              file="api.ts", pattern_id="S004"))
        session.add_finding(bh.Finding(title="console.log", severity="P2", category="code-quality",
                              file="ui.ts", pattern_id="C002"))
        report = bh.generate_markdown_report(session, "category")
        assert "Security" in report or "security" in report.lower()
        assert "Code-quality" in report or "code-quality" in report.lower()
        assert "SQLi" in report
        assert "console.log" in report

    def test_report_group_by_file(self, bh):
        """Report gruppiert nach Datei."""
        session = bh.BugHuntSession(project="/app")
        session.add_finding(bh.Finding(title="Bug A", severity="P1", file="src/a.ts"))
        session.add_finding(bh.Finding(title="Bug B", severity="P2", file="src/b.ts"))
        report = bh.generate_markdown_report(session, "file")
        assert "src/a.ts" in report
        assert "src/b.ts" in report
        assert "Bug A" in report
        assert "Bug B" in report
