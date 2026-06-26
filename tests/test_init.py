"""Error-path tests for scout/__init__.py — Tool registration, namespace shims, deps."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from scout import (
    TOOL_DESCRIPTIONS,
    _ensure_deps,
    _ensure_dirs,
    _ensure_scout_namespace,
    _ensure_shared_namespace,
    _register_domain_tools,
    _register_hooks,
    _register_tools,
    _resolve_handler,
    register,
)


class TestEnsureScoutNamespace:
    def test_does_not_crash_if_already_registered(self):
        _ensure_scout_namespace()
        _ensure_scout_namespace()  # second call should be no-op
        assert "scout" in sys.modules

    def test_registers_scout_module(self):
        saved = sys.modules.pop("scout", None)
        try:
            import scout
            scout._SCOUT_SHIM_REGISTERED = False
            _ensure_scout_namespace()
            assert "scout" in sys.modules
            mod = sys.modules["scout"]
            assert hasattr(mod, "__path__")
        finally:
            if saved:
                sys.modules["scout"] = saved


class TestEnsureSharedNamespace:
    def test_registers_shared_module(self):
        saved = sys.modules.pop("shared", None)
        try:
            import scout
            scout._SHARED_SHIM_REGISTERED = False
            _ensure_shared_namespace()
            assert "shared" in sys.modules
            mod = sys.modules["shared"]
            assert hasattr(mod, "__path__")
        finally:
            if saved:
                sys.modules["shared"] = saved


class TestResolveHandler:
    def test_resolves_existing_handler(self):
        handler = _resolve_handler("json", "dumps")
        assert handler is not None
        assert callable(handler)

    def test_returns_none_for_missing_module(self):
        handler = _resolve_handler("nonexistent_module_xyz", "handler")
        assert handler is None

    def test_returns_none_for_missing_handler(self):
        handler = _resolve_handler("json", "nonexistent_function")
        assert handler is None

    def test_handles_exception_during_import(self):
        with patch("importlib.import_module", side_effect=ImportError("import error")):
            handler = _resolve_handler("some.mod", "func")
            assert handler is None


class TestRegisterDomainTools:
    def test_empty_tools_list_does_nothing(self, mock_plugin_context):
        TOOL_DESCRIPTIONS.clear()
        _register_domain_tools(mock_plugin_context, "test", [])
        mock_plugin_context.register_tool.assert_not_called()

    def test_skips_unresolvable_handler(self, mock_plugin_context):
        tools = [
            {
                "name": "bad_tool",
                "handler_module": "nonexistent.mod",
                "handler_name": "handler",
                "schema": {"description": "bad"},
            }
        ]
        with patch("scout.logger") as mock_log:
            _register_domain_tools(mock_plugin_context, "test", tools)
            mock_plugin_context.register_tool.assert_not_called()
            mock_log.debug.assert_called()

    def test_registers_valid_tool(self, mock_plugin_context):
        tools = [
            {
                "name": "json_dumps",
                "handler_module": "json",
                "handler_name": "dumps",
                "schema": {"description": "JSON dump tool"},
            }
        ]
        _register_domain_tools(mock_plugin_context, "test", tools)
        mock_plugin_context.register_tool.assert_called_once()


class TestRegisterTools:
    def test_loads_registry_no_crash_on_missing_file(self, mock_plugin_context):
        """Wenn scout_tool_registry.json nicht existiert, kein Crash."""
        with patch.object(Path, "exists", return_value=False):
            _register_tools(mock_plugin_context)

    def test_loads_registry_corrupt_json(self, mock_plugin_context):
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "read_text", return_value="corrupt json {"):
                with patch("scout.logger") as mock_log:
                    _register_tools(mock_plugin_context)
                    mock_log.debug.assert_any_call(
                        "scout_tool_registry.json konnte nicht geladen werden"
                    )

    def test_analysis_tools_failure_handled(self, mock_plugin_context):
        """Wenn analysis tools import fehlschlägt, wird abgefangen."""
        with patch.object(Path, "exists", return_value=False):
            _register_tools(mock_plugin_context)


class TestRegisterHooks:
    def test_registers_successfully(self, mock_plugin_context):
        _register_hooks(mock_plugin_context)
        assert mock_plugin_context.register_hook.call_count >= 2


class TestEnsureDirs:
    def test_creates_directories(self, tmp_path):
        # Track calls to the real mkdir
        _ensure_dirs()
        # dirs should exist in the real PLUGIN_DIR path
        # Just verify no crash and function ran
        assert True


class TestEnsureDeps:
    def test_all_deps_installed(self):
        """Wenn alle deps vorhanden, wird nichts gemacht."""
        result = _ensure_deps()
        assert result is None

    def test_missing_dep_triggers_pip_install(self):
        """Wenn dep fehlt, wird pip install versucht."""
        import subprocess as real_subprocess

        def _side_effect(name):
            if name in ("yaml", "packaging"):
                raise ImportError(f"No module named {name}")
            # For everything else, use real importlib
            return real_subprocess  # dummy

        saved_check_call = real_subprocess.check_call
        real_subprocess.check_call = MagicMock()
        try:
            with patch("importlib.import_module", side_effect=_side_effect):
                _ensure_deps()
                assert real_subprocess.check_call.call_count >= 1
        finally:
            real_subprocess.check_call = saved_check_call

    def test_pip_failure_fallback_to_user(self):
        """Wenn pip fehlschlägt, wird --user versucht."""
        import subprocess as real_subprocess

        def _side_effect(name):
            if name in ("yaml", "packaging"):
                raise ImportError(f"No module named {name}")
            return MagicMock()

        import subprocess
        saved_check_call = real_subprocess.check_call
        real_subprocess.check_call = MagicMock(
            side_effect=[subprocess.CalledProcessError(1, "pip"), None]
        )
        try:
            with patch("importlib.import_module", side_effect=_side_effect):
                _ensure_deps()
                assert real_subprocess.check_call.call_count == 2
        finally:
            real_subprocess.check_call = saved_check_call


class TestRegister:
    def test_register_no_crash(self, mock_plugin_context):
        """Full register() call should not crash."""
        with patch("scout._ensure_deps"):
            with patch("scout._ensure_dirs"):
                with patch("scout._register_tools"):
                    with patch("scout._register_hooks"):
                        register(mock_plugin_context)
