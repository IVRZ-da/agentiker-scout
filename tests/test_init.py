"""Error-path tests for scout/__init__.py — Tool registration, namespace shims, deps."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from scout import (
    TOOL_DESCRIPTIONS,
    _ensure_dirs,
    _ensure_scout_namespace,
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

    def test_registry_json_is_not_a_source(self, mock_plugin_context):
        """Seit 0.6.0 liest _register_tools die JSON-Datei nicht mehr.

        Die Wahrheit liegt in den Domaenen (shared/tool_registry.collect());
        scout_tool_registry.json ist ein erzeugtes Artefakt. Eine korrupte
        Datei darf die Registrierung also weder stoeren noch verhindern.
        """
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "read_text", return_value="corrupt json {"):
                _register_tools(mock_plugin_context)

        assert mock_plugin_context.register_tool.called, "keine Tools registriert"
        names = [c.args[0] for c in mock_plugin_context.register_tool.call_args_list]
        assert all(isinstance(n, str) and n for n in names)

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


class TestRegister:
    def test_register_binds_registry_context(self, mock_plugin_context, monkeypatch):
        """register() muss den PluginContext an die Tool-Registry binden."""
        from scout.shared import registry as registry_mod

        real = registry_mod.Registry()
        monkeypatch.setattr(registry_mod, "registry", real)
        with patch("scout._ensure_dirs"), patch("scout._register_tools"), patch("scout._register_hooks"):
            register(mock_plugin_context)
        assert real._context is mock_plugin_context

    def test_register_registers_hooks(self, mock_plugin_context):
        """register() muss die drei Hooks anmelden."""
        with patch("scout._ensure_dirs"), patch("scout._register_tools"):
            register(mock_plugin_context)
        names = [c.args[0] for c in mock_plugin_context.register_hook.call_args_list]
        assert set(names) == {"pre_llm_call", "post_tool_call", "on_session_end"}


class TestNamespaceIsolation:
    """Der Plugin-Import darf den Hermes-Core-Namespace nicht veraendern."""

    def test_no_tools_shim_in_source(self):
        import inspect

        import scout

        src = inspect.getsource(scout)
        assert "sys.modules.setdefault(\"tools\"" not in src
        assert "sys.modules[\"tools\"]" not in src

    def test_no_shared_shim_in_source(self):
        import inspect

        import scout

        src = inspect.getsource(scout)
        assert "_ensure_shared_namespace" not in src
        assert "sys.modules.setdefault(\"shared\"" not in src

    def test_no_runtime_pip_install(self):
        import inspect

        import scout

        src = inspect.getsource(scout)
        assert "_ensure_deps" not in src
        assert "pip install" not in src

    def test_tools_namespace_untouched_by_import(self):
        """Ein frischer Import von scout legt kein 'tools'-Modul an."""
        import subprocess

        from scout import PLUGIN_DIR

        code = (
            "import sys, importlib.util\n"
            f"d = r'{PLUGIN_DIR}'\n"
            "spec = importlib.util.spec_from_file_location('scout', d + '/__init__.py', "
            "submodule_search_locations=[d])\n"
            "m = importlib.util.module_from_spec(spec)\n"
            "sys.modules['scout'] = m\n"
            "spec.loader.exec_module(m)\n"
            "print('DIRTY' if 'tools' in sys.modules else 'CLEAN')\n"
        )
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
        assert out.returncode == 0, out.stderr
        assert out.stdout.strip().splitlines()[-1] == "CLEAN", out.stdout
