"""Integrationstests: echter Dispatch statt pauschaler Mock.

Testet die Dispatch-Pipeline:
  registry.dispatch() → handler(args) → Rückgabe-Formatierung

Verwendet leichte Test-Handler (kein Full-Stack File-Scan) um den
Mechanismus zu testen, nicht die Tool-Implementierung.
"""

from __future__ import annotations

import json

import pytest

from scout.analysis.tools.base import _call_tool


class TestDispatchMechanism:
    """Testet den Dispatch-Mechanismus mit echten, aber leichten Handlern.

    Registriert minimale Handler im real_registry und testet:
    - dispatch → handler routing
    - Argument-Übergabe (args dict)
    - Fehlerbehandlung (unbekannte Tools)
    - Response-Formatierung (String → JSON Parsing)
    - _call_tool wrapper (Timeout, json.loads)
    """

    @pytest.fixture
    def echo_handler_registry(self, request):
        """Registriert einen Echo-Handler statt Full-Stack Tools.

        Der Handler gibt die empfangenen args als JSON zurück —
        perfekt zum Testen ob Dispatch und Argument-Übergabe funktionieren.
        """
        from tests.fakes import RealDispatchRegistry

        reg = RealDispatchRegistry()

        def _handle_echo(args, **kw):
            return json.dumps({
                "status": "ok",
                "tool": "test_echo",
                "received_args": args,
                "extra_kw": {k: str(v) for k, v in kw.items()},
            })

        reg.register("test_echo", _handle_echo, {"description": "Echo handler for testing"})
        return reg

    @pytest.fixture
    def echo_env(self, echo_handler_registry):
        """Ersetzt die Plugin-Registry durch echo_handler_registry (und zurueck)."""
        from scout.shared import registry as registry_mod

        old = registry_mod.registry
        registry_mod.registry = echo_handler_registry
        try:
            yield echo_handler_registry
        finally:
            registry_mod.registry = old

    def test_dispatch_routes_to_handler(self, echo_env):
        """_call_tool ruft den registrierten Handler auf."""
        result = _call_tool("test_echo", foo="bar")
        assert result is not None
        assert isinstance(result, dict)
        assert result.get("status") == "ok"

    def test_arguments_passed_through_dispatch(self, echo_env):
        """Handler empfängt die übergebenen kwargs als args dict."""
        result = _call_tool("test_echo", username="test", user_id=42, active=True)
        assert isinstance(result, dict)
        received = result.get("received_args", {})
        assert received.get("username") == "test"
        assert received.get("user_id") == 42
        assert received.get("active") is True

    def test_unknown_tool_returns_error(self, echo_env):
        """Unbekanntes Tool gibt Fehler-Dict zurück."""
        result = _call_tool("nonexistent_tool_xyz")
        assert isinstance(result, dict)
        assert "error" in result
        assert "nonexistent_tool_xyz" in str(result.get("error", ""))

    def test_dispatch_does_not_use_mock_registry(self, echo_env):
        """Der Dispatch geht NICHT durch MockRegistry (kein 'mocked' im Result)."""
        result = _call_tool("test_echo")
        assert isinstance(result, dict)
        response_str = json.dumps(result)
        # MockRegistry gibt 'mocked' zurück — RealDispatchRegistry tut das nicht
        assert "mocked" not in response_str.lower()

    def test_dispatch_with_empty_args(self, echo_env):
        """_call_tool ohne kwargs gibt leeres args dict an Handler."""
        result = _call_tool("test_echo")
        assert isinstance(result, dict)
        received = result.get("received_args", {})
        assert isinstance(received, dict)

    def test_dispatch_handles_string_result(self, echo_env):
        """Handler der einen String returned wird von _call_tool parsed."""
        # Zusätzlicher Handler der raw String returned
        def _handle_raw(args, **kw):
            return '{"status": "ok", "from": "raw_string"}'

        echo_env.register("raw_string_tool", _handle_raw)
        # Registry kommt bereits aus dem echo_env-Fixture
        # Registry kommt bereits aus dem echo_env-Fixture

        result = _call_tool("raw_string_tool")
        assert isinstance(result, dict)
        assert result.get("status") == "ok"
        assert result.get("from") == "raw_string"

    def test_handler_exception_is_caught(self, echo_env):
        """Exception im Handler wird von _call_tool abgefangen."""
        def _handle_crash(args, **kw):
            raise RuntimeError("simulated crash")

        echo_env.register("crash_tool", _handle_crash)
        # Registry kommt bereits aus dem echo_env-Fixture
        # Registry kommt bereits aus dem echo_env-Fixture

        result = _call_tool("crash_tool")
        assert isinstance(result, dict)
        assert "error" in result

    def test_multiple_registrations(self, echo_env):
        """Mehrere Handler können registriert werden."""
        def _handle_a(args, **kw):
            return json.dumps({"status": "ok", "tool": "tool_a"})

        def _handle_b(args, **kw):
            return json.dumps({"status": "ok", "tool": "tool_b"})

        echo_env.register("tool_a", _handle_a)
        echo_env.register("tool_b", _handle_b)

        # Registry kommt bereits aus dem echo_env-Fixture

        result_a = _call_tool("tool_a")
        result_b = _call_tool("tool_b")
        assert isinstance(result_a, dict) and result_a.get("tool") == "tool_a"
        assert isinstance(result_b, dict) and result_b.get("tool") == "tool_b"


class TestRealDispatchWithRealHandlers:
    """Leichte Integrationstests mit ECHTEN Scout-Handlern.

    Verwendet das `real_registry`-Fixture (registriert echte TOOL_HANDLER)
    aber nur für Handler die keine schweren File-Scans machen.
    """

    @pytest.fixture
    def patched_registry(self, real_registry, monkeypatch):
        """Setzt die Plugin-Registry auf real_registry."""
        from scout.shared import registry as _reg_mod

        monkeypatch.setattr(_reg_mod, "registry", real_registry)
        return real_registry

    def test_dispatch_analysis_diff(self, patched_registry, tmp_path):
        """analysis_diff testet echten Dispatch mit minimalen Daten."""
        report_a = {"tool": "test_a", "path": str(tmp_path), "summary": {"files": 5}}
        report_b = {"tool": "test_b", "path": str(tmp_path), "summary": {"files": 10}}

        result = _call_tool(
            "analysis_diff",
            report_a=report_a,
            report_b=report_b,
            format="text",
        )
        assert result is not None
        if isinstance(result, dict):
            assert result.get("tool") == "analysis_diff"
            changes = result.get("changes", [])
            summary = result.get("summary", {})
            assert changes or summary

    def test_dispatch_analysis_report(self, patched_registry):
        """analysis_report testet echten Dispatch ohne File-IO."""
        result = _call_tool(
            "analysis_report",
            scope="module:test-integration",
            findings={"test": True, "result": "passed"},
        )
        assert result is not None
        if isinstance(result, dict):
            assert "scope" in result or "status" in result

    def test_registry_contains_scout_tools(self, patched_registry):
        """Scout-eigene Tools sind registriert."""
        tools = patched_registry.get_all_tool_names()
        assert "analysis_diff" in tools
        assert "analysis_report" in tools
        assert "analysis_inspect" in tools

    def test_dispatch_with_real_registry_object(self, patched_registry):
        """Fixture returned einen RealDispatchRegistry (duck-typing)."""
        # Check duck-typing statt isinstance (conftest module caching issue)
        assert hasattr(patched_registry, "dispatch")
        assert hasattr(patched_registry, "register")
        assert hasattr(patched_registry, "get_entry")
        assert hasattr(patched_registry, "get_all_tool_names")

    def test_path_validation_in_dispatch(self, patched_registry):
        """Echter _validate_path wird durchlaufen."""
        result = _call_tool("analysis_inspect", path="/nonexistent/path/12345xyz")
        if isinstance(result, dict):
            # _validate_and_resolve_path returned error für nicht-existente Pfade
            assert result.get("status") == "error" or result.get("error") is not None
        elif isinstance(result, str):
            import json
            parsed = json.loads(result)
            assert parsed.get("status") == "error"

    def test_real_registry_dispatch_unknown(self, patched_registry):
        """Unbekanntes Tool im real_registry gibt Fehler."""
        result = _call_tool("analysis_nonexistent_tool")
        assert isinstance(result, dict)
        assert "error" in result
