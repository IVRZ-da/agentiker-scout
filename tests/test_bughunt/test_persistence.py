"""Comprehensive tests for bughunt/core/persistence.py — Session CRUD, path validation, cleanup."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from scout.bughunt.core.model import BugHuntSession
from scout.bughunt.core.persistence import (
    _atomic_write_json,
    _ensure_dirs,
    cleanup_old_sessions,
    delete_session,
    list_sessions,
    load_session,
    save_session,
    validate_path,
)

# ─── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def tmp_sessions(tmp_path):
    """Patch SESSIONS_DIR to a temp directory for session tests."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    with patch("scout.bughunt.core.persistence.SESSIONS_DIR", sessions_dir):
        yield sessions_dir


@pytest.fixture
def fresh_session():
    """Return a simple BugHuntSession with a deterministic session_id."""
    s = BugHuntSession(project="test-proj", scope="quick")
    return s


# ── _ensure_dirs ─────────────────────────────────────────────────────


class TestEnsureDirs:
    def test_creates_dir(self, tmp_path: Path) -> None:
        """SESSIONS_DIR wird angelegt, wenn es nicht existiert."""
        target = tmp_path / "new_sessions"
        assert not target.exists()
        with patch("scout.bughunt.core.persistence.SESSIONS_DIR", target):
            _ensure_dirs()
            assert target.exists()

    def test_no_error_if_exists(self, tmp_path: Path) -> None:
        """Schlägt nicht fehl, wenn Verzeichnis bereits existiert."""
        target = tmp_path / "existing"
        target.mkdir()
        with patch("scout.bughunt.core.persistence.SESSIONS_DIR", target):
            _ensure_dirs()  # should not raise
            assert target.exists()


# ── _atomic_write_json ───────────────────────────────────────────────


class TestAtomicWriteJson:
    def test_writes_atomically(self, tmp_path: Path) -> None:
        target = tmp_path / "test.json"
        data = [{"a": 1, "b": "hello"}]
        _atomic_write_json(target, data)
        assert target.exists()
        assert json.loads(target.read_text(encoding="utf-8")) == data

    def test_tmp_file_does_not_remain(self, tmp_path: Path) -> None:
        target = tmp_path / "test.json"
        _atomic_write_json(target, [{"x": 2}])
        assert not (tmp_path / "test.json.tmp").exists()

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        target = tmp_path / "test.json"
        target.write_text(json.dumps([{"old": "data"}]))
        _atomic_write_json(target, [{"new": "data"}])
        assert json.loads(target.read_text(encoding="utf-8")) == [{"new": "data"}]

    def test_writes_utf8_properly(self, tmp_path: Path) -> None:
        target = tmp_path / "test.json"
        data = [{"ümlaut": "straße", "emoji": "🐛"}]
        _atomic_write_json(target, data)
        assert json.loads(target.read_text(encoding="utf-8")) == data


# ── save_session ─────────────────────────────────────────────────────


class TestSaveSession:
    def test_saves_and_returns_id(self, tmp_sessions: Path, fresh_session: BugHuntSession) -> None:
        sid = save_session(fresh_session)
        assert sid == fresh_session.session_id
        file_path = tmp_sessions / f"{sid}.json"
        assert file_path.exists()

    def test_writes_valid_json(self, tmp_sessions: Path, fresh_session: BugHuntSession) -> None:
        save_session(fresh_session)
        file_path = tmp_sessions / f"{fresh_session.session_id}.json"
        data = json.loads(file_path.read_text(encoding="utf-8"))
        assert data["session_id"] == fresh_session.session_id
        assert data["project"] == "test-proj"
        assert data["scope"] == "quick"

    def test_calls_ensure_dirs(self, tmp_sessions: Path, fresh_session: BugHuntSession) -> None:
        with patch("scout.bughunt.core.persistence._ensure_dirs") as mock_ensure:
            save_session(fresh_session)
            mock_ensure.assert_called_once()

    def test_saves_findings_too(self, tmp_sessions: Path, fresh_session: BugHuntSession) -> None:
        fresh_session.findings.append({"id": "f1", "title": "Test finding"})
        save_session(fresh_session)
        file_path = tmp_sessions / f"{fresh_session.session_id}.json"
        data = json.loads(file_path.read_text(encoding="utf-8"))
        assert len(data["findings"]) == 1
        assert data["findings"][0]["title"] == "Test finding"


# ── load_session ─────────────────────────────────────────────────────


class TestLoadSession:
    def test_returns_none_if_not_exists(self, tmp_sessions: Path) -> None:
        result = load_session("nonexistent")
        assert result is None

    def test_loads_valid_session(self, tmp_sessions: Path, fresh_session: BugHuntSession) -> None:
        save_session(fresh_session)
        loaded = load_session(fresh_session.session_id)
        assert loaded is not None
        assert loaded.session_id == fresh_session.session_id
        assert loaded.project == "test-proj"
        assert loaded.scope == "quick"
        assert loaded.status == "open"

    def test_corrupt_json_returns_none(self, tmp_sessions: Path) -> None:
        (tmp_sessions / "bad.json").write_text("{invalid json", encoding="utf-8")
        result = load_session("bad")
        assert result is None

    def test_json_decode_error_handled(self, tmp_sessions: Path) -> None:
        """JSONDecodeError wird abgefangen → None."""
        (tmp_sessions / "bad2.json").write_text("{broken", encoding="utf-8")
        result = load_session("bad2")
        assert result is None

    def test_graceful_with_extra_keys(self, tmp_sessions: Path) -> None:
        """from_dict ist tolerant gegenüber unbekannten/fehlenden Keys."""
        (tmp_sessions / "extra.json").write_text(
            json.dumps({"not_a_session_key": "value", "session_id": "custom-id", "project": "p"}),
            encoding="utf-8",
        )
        result = load_session("extra")
        assert result is not None
        # from_dict setzt auch unbekannte Attribute — das ist OK
        assert result.session_id == "custom-id"
        assert result.project == "p"

    def test_roundtrip_preserves_data(self, tmp_sessions: Path) -> None:
        """Nach save + load sind alle Attribute erhalten."""
        s = BugHuntSession(project="my-project", scope="comprehensive")
        s.findings.append({"id": "f1", "title": "bug", "severity": "P0"})
        s.status = "closed"
        s.summary = "Done."
        save_session(s)
        loaded = load_session(s.session_id)
        assert loaded is not None
        assert loaded.project == "my-project"
        assert loaded.scope == "comprehensive"
        assert loaded.status == "closed"
        assert loaded.summary == "Done."
        assert len(loaded.findings) == 1


# ── delete_session ───────────────────────────────────────────────────


class TestDeleteSession:
    def test_returns_true_when_deleted(self, tmp_sessions: Path, fresh_session: BugHuntSession) -> None:
        save_session(fresh_session)
        path = tmp_sessions / f"{fresh_session.session_id}.json"
        assert path.exists()
        result = delete_session(fresh_session.session_id)
        assert result is True
        assert not path.exists()

    def test_returns_false_when_not_found(self, tmp_sessions: Path) -> None:
        result = delete_session("nonexistent")
        assert result is False

    def test_idempotent_delete(self, tmp_sessions: Path) -> None:
        """Mehrmaliges Löschen derselben ID ist unproblematisch."""
        result1 = delete_session("ghost")
        result2 = delete_session("ghost")
        assert result1 is False
        assert result2 is False


# ── list_sessions ────────────────────────────────────────────────────


class TestListSessions:
    def test_empty_dir_returns_empty_list(self, tmp_sessions: Path) -> None:
        result = list_sessions()
        assert result == []

    def test_returns_sorted_newest_first(self, tmp_sessions: Path) -> None:
        s_old = BugHuntSession(project="old")
        s_new = BugHuntSession(project="new")
        save_session(s_old)
        save_session(s_new)

        result = list_sessions()
        assert len(result) == 2
        # Sorted by filename (session_id) in reverse
        ids = [r["session_id"] for r in result]
        assert ids == sorted(ids, reverse=True)

    def test_includes_all_fields(self, tmp_sessions: Path, fresh_session: BugHuntSession) -> None:
        fresh_session.findings.append({"id": "f1", "title": "bug"})
        fresh_session.status = "closed"
        fresh_session.scope = "comprehensive"
        save_session(fresh_session)

        result = list_sessions()
        assert len(result) == 1
        entry = result[0]
        assert entry["session_id"] == fresh_session.session_id
        assert entry["project"] == fresh_session.project
        assert entry["scope"] == "comprehensive"
        assert entry["status"] == "closed"
        assert entry["findings_count"] == 1
        assert entry["started_at"] == fresh_session.started_at
        assert entry["closed_at"] == fresh_session.closed_at

    def test_skips_corrupt_files(self, tmp_sessions: Path) -> None:
        s = BugHuntSession(project="ok")
        save_session(s)
        (tmp_sessions / "bad.json").write_text("{corrupt}", encoding="utf-8")
        (tmp_sessions / "also_bad.json").write_text("not json at all", encoding="utf-8")

        result = list_sessions()
        assert len(result) == 1
        assert result[0]["session_id"] == s.session_id

    def test_skips_files_with_exception_in_reading(self, tmp_sessions: Path) -> None:
        """Auch wenn data.get() schlägt fehl, wird die Datei übersprungen."""
        s = BugHuntSession(project="ok")
        save_session(s)
        # Write a file that will cause a different exception (not JSONDecodeError)
        (tmp_sessions / "weird.json").write_text('{"session_id":}', encoding="utf-8")
        result = list_sessions()
        assert len(result) == 1


# ── validate_path ────────────────────────────────────────────────────


class TestValidatePath:
    def test_empty_path_returns_error(self) -> None:
        assert validate_path("") is not None

    def test_none_path_returns_error(self) -> None:
        assert validate_path(None) is not None  # type: ignore[arg-type]

    def test_non_string_returns_error(self) -> None:
        assert validate_path(123) is not None  # type: ignore[arg-type]

    def test_too_long_path_returns_error(self) -> None:
        long_path = "a" * 5000
        err = validate_path(long_path)
        assert err is not None
        assert "too long" in err

    def test_control_chars_returns_error(self) -> None:
        assert validate_path("test\x00file") is not None
        assert validate_path("test\x1ffile") is not None
        assert validate_path("test\x7ffile") is not None

    def test_traversal_dotdot_returns_error(self) -> None:
        assert validate_path("../etc/passwd") is not None
        assert validate_path("foo/../../bar") is not None
        assert validate_path("a\\..\\b") is not None

    def test_traversal_url_encoded_returns_error(self) -> None:
        assert validate_path("%2e%2e/esc") is not None
        assert validate_path("foo/%2e%2e/bar") is not None

    def test_traversal_outside_allowed_base(self, tmp_path: Path) -> None:
        outside = tmp_path / "outside"
        outside.mkdir()
        allowed = tmp_path / "allowed"
        allowed.mkdir()

        test_file = outside / "test.txt"
        test_file.write_text("data")

        error = validate_path(str(test_file), allowed_base=allowed)
        assert error is not None
        assert "outside allowed directory" in error

    def test_valid_path_no_error(self, tmp_path: Path) -> None:
        error = validate_path(str(tmp_path))
        assert error is None

    def test_valid_path_within_allowed_base(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        error = validate_path(str(sub), allowed_base=tmp_path)
        assert error is None

    def test_oserror_on_unresolvable_path(self) -> None:
        with patch("scout.bughunt.core.persistence.Path.resolve", side_effect=OSError("mock error")):
            error = validate_path("/some/path")
            assert error is not None

    def test_value_error_on_unresolvable_path(self) -> None:
        with patch("scout.bughunt.core.persistence.Path.resolve", side_effect=ValueError("mock error")):
            error = validate_path("/some/path")
            assert error is not None

    def test_allowed_base_symlink_safety(self, tmp_path: Path) -> None:
        """Symlinks innerhalb des erlaubten Verzeichnisses sind OK."""
        sub = tmp_path / "sub"
        sub.mkdir()
        link = tmp_path / "link"
        try:
            link.symlink_to(sub)
        except OSError:
            pytest.skip("Cannot create symlinks on this platform")
        error = validate_path(str(link / "test.txt"), allowed_base=tmp_path)
        assert error is None


# ── cleanup_old_sessions ─────────────────────────────────────────────


class TestCleanupOldSessions:
    def test_removes_old_files_by_age(self, tmp_sessions: Path) -> None:
        old_file = tmp_sessions / "old.json"
        old_file.write_text("{}", encoding="utf-8")
        old_mtime = time.time() - (100 * 86400)  # 100 days ago
        os.utime(str(old_file), (old_mtime, old_mtime))

        fresh_file = tmp_sessions / "fresh.json"
        fresh_file.write_text("{}", encoding="utf-8")

        deleted = cleanup_old_sessions(max_sessions=10, max_age_days=30)
        assert deleted >= 1
        assert not old_file.exists()
        assert fresh_file.exists()

    def test_removes_excess_files_by_count(self, tmp_sessions: Path) -> None:
        for i in range(5):
            (tmp_sessions / f"file{i}.json").write_text("{}", encoding="utf-8")
            time.sleep(0.01)

        deleted = cleanup_old_sessions(max_sessions=2, max_age_days=365)
        assert deleted >= 3

    def test_no_cleanup_needed(self, tmp_sessions: Path) -> None:
        """Wenn alles innerhalb Limits, wird nichts gelöscht."""
        for i in range(3):
            (tmp_sessions / f"file{i}.json").write_text("{}", encoding="utf-8")
            time.sleep(0.01)

        deleted = cleanup_old_sessions(max_sessions=10, max_age_days=365)
        assert deleted == 0

    def test_only_count_removal(self, tmp_sessions: Path) -> None:
        """Nur Count-Limit greift, Age-Limit nicht."""
        for i in range(5):
            (tmp_sessions / f"file{i}.json").write_text("{}", encoding="utf-8")
            time.sleep(0.01)

        # max_age_days sehr groß, max_sessions sehr klein
        deleted = cleanup_old_sessions(max_sessions=1, max_age_days=36500)
        assert deleted >= 4

    def test_only_age_removal(self, tmp_sessions: Path) -> None:
        """Nur Age-Limit greift, Count-Limit nicht."""
        old_file = tmp_sessions / "old.json"
        old_file.write_text("{}", encoding="utf-8")
        old_mtime = time.time() - (100 * 86400)
        os.utime(str(old_file), (old_mtime, old_mtime))

        fresh_file = tmp_sessions / "fresh.json"
        fresh_file.write_text("{}", encoding="utf-8")

        # max_sessions sehr groß, max_age_days sehr klein
        deleted = cleanup_old_sessions(max_sessions=100, max_age_days=1)
        assert deleted >= 1
        assert not old_file.exists()
        assert fresh_file.exists()

    def test_oserror_handled_gracefully(self, tmp_sessions: Path) -> None:
        """Wenn unlink fehlschlägt, wird OSError abgefangen."""
        (tmp_sessions / "stuck.json").write_text("{}", encoding="utf-8")

        with patch.object(Path, "unlink", side_effect=OSError("permission denied")):
            deleted = cleanup_old_sessions(max_sessions=0, max_age_days=0)
            assert deleted >= 0
            # Should not crash

    def test_logs_on_deletion(self, tmp_sessions: Path, caplog) -> None:
        """Bei Löschung wird ein Debug-Log ausgegeben."""
        import logging
        caplog.set_level(logging.DEBUG)

        (tmp_sessions / "old.json").write_text("{}", encoding="utf-8")
        old_mtime = time.time() - (100 * 86400)
        os.utime(str(tmp_sessions / "old.json"), (old_mtime, old_mtime))

        cleanup_old_sessions(max_sessions=10, max_age_days=1)
        assert any("cleanup_old_sessions" in rec.message for rec in caplog.records)
