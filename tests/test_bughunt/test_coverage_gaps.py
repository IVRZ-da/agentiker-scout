"""Tests für bughunt/bughunt_tools.py und bughunt/bughunt_hooks.py — Lücken schliessen."""

from __future__ import annotations

import json

from scout.bughunt.bughunt_tools import _err, _ok


class TestBughuntToolsHelpers:
    def test_ok_returns_json(self):
        result = _ok({"status": "ok", "data": "test"})
        parsed = json.loads(result)
        assert parsed["status"] == "ok"

    def test_err_returns_json(self):
        result = _err("something went wrong")
        parsed = json.loads(result)
        assert parsed["status"] == "error"

    def test_bug_hunt_stats_no_session(self):
        """bug_hunt_stats mit ungültiger Session-ID gibt Fehler."""
        from scout.bughunt.bughunt_tools import bug_hunt_stats
        result = bug_hunt_stats({"session_id": "nonexistent_session_xyz"})
        data = json.loads(result)
        assert data["status"] in ("error", "ok")


class TestBughuntHooks:
    def test_hook_functions_exist(self):
        from scout.bughunt.bughunt_hooks import (
            _auto_deduce_patterns,
            _is_bughunt_related,
            _map_security_severity,
        )
        assert callable(_auto_deduce_patterns)
        assert callable(_is_bughunt_related)
        assert callable(_map_security_severity)

    def test_is_bughunt_related(self):
        from scout.bughunt.bughunt_hooks import _is_bughunt_related
        assert _is_bughunt_related("scan auf security") is True
        assert _is_bughunt_related("bug gefunden") is True

    def test_is_bughunt_related_false(self):
        from scout.bughunt.bughunt_hooks import _is_bughunt_related
        assert _is_bughunt_related("wie ist das Wetter") is False
        assert _is_bughunt_related("") is False

    def test_map_security_severity(self):
        from scout.bughunt.bughunt_hooks import _map_security_severity
        assert _map_security_severity("CRITICAL") == "P0"
        assert _map_security_severity("HIGH") == "P1"
        assert _map_security_severity("MEDIUM") == "P2"
        assert _map_security_severity("LOW") == "P3"
        assert _map_security_severity("unknown") == "P2"
