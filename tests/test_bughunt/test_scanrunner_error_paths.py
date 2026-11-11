"""Scanrunner: Antwort-Parsing und Fehlerpfade.

``_get_result_text`` muss drei MCP-Antwortformate verstehen (verschachtelt,
flach, roh) — geht eines kaputt, verliert der Scan still seine Findings.
Die grep-Fehlerpfade muessen degradieren statt zu werfen.
"""
from __future__ import annotations

import subprocess
import sys

from scout.bughunt.bughunt_scanrunner import (
    _get_result_text,
    is_mcp_devtools_available,
    run_grep_scan,
)


class TestGetResultText:
    def test_non_dict_returns_empty(self):
        assert _get_result_text("kein dict") == ""
        assert _get_result_text(None) == ""
        assert _get_result_text([1, 2]) == ""

    def test_mcp_content_list(self):
        result = {"result": {"content": [{"text": "a"}, {"text": "b"}, {"other": 1}]}}
        assert _get_result_text(result) == "a\nb"

    def test_mcp_content_empty_texts_are_dropped(self):
        result = {"result": {"content": [{"text": ""}, {"text": "echt"}]}}
        assert _get_result_text(result) == "echt"

    def test_flat_text(self):
        assert _get_result_text({"result": {"text": "direkt"}}) == "direkt"

    def test_raw_string_result(self):
        assert _get_result_text({"result": "roh"}) == "roh"

    def test_top_level_content(self):
        assert _get_result_text({"content": [{"text": "top"}]}) == "top"

    def test_unknown_shape_returns_empty(self):
        assert _get_result_text({"irgendwas": 1}) == ""


class TestGrepScanErrorPaths:
    def test_timeout_returns_empty(self, monkeypatch):
        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="grep", timeout=1)

        monkeypatch.setattr("scout.bughunt.bughunt_scanrunner.subprocess.run", timeout)
        assert run_grep_scan("x", "", "/tmp", timeout=1) == []

    def test_missing_binary_returns_empty(self, monkeypatch):
        def missing(*args, **kwargs):
            raise FileNotFoundError("kein grep")

        monkeypatch.setattr("scout.bughunt.bughunt_scanrunner.subprocess.run", missing)
        assert run_grep_scan("x", "", "/tmp", timeout=1) == []

    def test_unexpected_error_returns_empty(self, monkeypatch):
        def boom(*args, **kwargs):
            raise OSError("kaputt")

        monkeypatch.setattr("scout.bughunt.bughunt_scanrunner.subprocess.run", boom)
        assert run_grep_scan("x", "", "/tmp", timeout=1) == []

    def test_nonzero_exit_returns_empty(self, monkeypatch):
        class Proc:
            returncode = 2
            stdout = ""
            stderr = "syntax error"

        monkeypatch.setattr(
            "scout.bughunt.bughunt_scanrunner.subprocess.run", lambda *a, **k: Proc()
        )
        assert run_grep_scan("x", "", "/tmp", timeout=1) == []


class TestMcpAvailability:
    def test_false_when_registry_unimportable(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "scout.shared.registry", None)
        assert is_mcp_devtools_available() is False

    def test_false_when_registry_has_no_attribute(self, monkeypatch):
        import types

        fake = types.ModuleType("scout.shared.registry")
        monkeypatch.setitem(sys.modules, "scout.shared.registry", fake)
        assert is_mcp_devtools_available() is False

    def test_true_when_entry_exists(self, monkeypatch):
        import types

        class Registry:
            def get_entry(self, name):
                return object()

        fake = types.ModuleType("scout.shared.registry")
        fake.registry = Registry()
        monkeypatch.setitem(sys.modules, "scout.shared.registry", fake)
        assert is_mcp_devtools_available() is True

    def test_false_when_entry_missing(self, monkeypatch):
        import types

        class Registry:
            def get_entry(self, name):
                return None

        fake = types.ModuleType("scout.shared.registry")
        fake.registry = Registry()
        monkeypatch.setitem(sys.modules, "scout.shared.registry", fake)
        assert is_mcp_devtools_available() is False
