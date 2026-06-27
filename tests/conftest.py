"""Shared conftest for scout plugin tests.

Vereinheitlicht die Mock-Infrastruktur aus 3 Quell-Plugins.
Bietet MockPluginContext, MockRegistry und _fmt Mock.

Coverage wird vor sys.modules Shim gestartet, damit
auch ueber Shims geladene Module getrackt werden.
"""

from __future__ import annotations

import json
import sys
import types
import warnings
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# Coverage manuell starten (bevor sys.modules Shims injected werden)
try:
    import coverage
    _cov = coverage.Coverage(source_pkg=["scout"])
    _cov.start()
except Exception:
    pass

# ─── DeprecationWarning-Filter (importlib __package__ != __spec__.parent) ─
warnings.filterwarnings("ignore", message=".*__package__.*")

# ─── _fmt Mock (sys.modules Injection) ────────────────────────────────────

def _install_fmt_mock() -> None:
    """Install _fmt mock that returns plain JSON (not rich panels).

    Muss vor dem Import von scout Modulen laufen.
    Überschreibt sys.modules["scout._fmt"] falls bereits geladen.
    """
    fmt_mod = types.ModuleType("scout._fmt")
    # Also register as "_fmt" for backward compat with direct imports
    sys.modules["_fmt"] = fmt_mod
    sys.modules["scout._fmt"] = fmt_mod

    def _fmt_ok(data: Any = None, msg: str | None = None) -> str:
        result = {"status": "ok"}
        if isinstance(data, dict):
            result.update(data)
        if msg:
            result["message"] = msg
        return json.dumps(result, ensure_ascii=False)

    def _fmt_err(msg: str, details: Any = None) -> str:
        result: dict = {"status": "error", "error": msg, "message": msg}
        if details:
            result["details"] = details
        return json.dumps(result, ensure_ascii=False)

    fmt_mod.fmt_ok = _fmt_ok
    fmt_mod.fmt_err = _fmt_err
    fmt_mod.fmt_info = lambda msg, data=None: json.dumps(
        {"status": "info", "message": msg, **(data or {})}, ensure_ascii=False
    )
    fmt_mod.fmt_json = lambda data: json.dumps(data, ensure_ascii=False, indent=2, default=str)
    fmt_mod.fmt_table = lambda *a, **kw: ""
    fmt_mod.fmt_code = lambda code, lang="", **kw: f"```{lang}\n{code}\n```"
    fmt_mod.fmt_markdown = lambda text: text.strip()
    fmt_mod.fmt_warn = lambda msg, data=None: json.dumps(
        {"status": "warning", "message": msg, **(data or {})}, ensure_ascii=False
    )
    fmt_mod.fmt_research_status = lambda d, title=None: json.dumps(
        {"status": "ok", **(d or {})}, ensure_ascii=False
    )


_install_fmt_mock()

# ─── Hermes Module Mocks (für registry.dispatch, PluginContext etc.) ─────

_hermes = types.ModuleType("hermes_cli")
_hermes.plugins = types.ModuleType("hermes_cli.plugins")
_hermes.plugins.PluginContext = type("MockPluginContext", (), {
    "register_tool": lambda *a, **kw: None,
    "register_hook": lambda *a, **kw: None,
    "register_skill": lambda *a, **kw: None,
})
sys.modules["hermes_cli"] = _hermes
sys.modules["hermes_cli.plugins"] = _hermes.plugins

_tools = types.ModuleType("tools")
_tools.registry = types.ModuleType("tools.registry")
_tools.registry.registry = type("R", (), {
    "get_entry": lambda self, n: self._entries.get(n) if hasattr(self, "_entries") else None,
    "_entries": {},
    "register": lambda self, n, **kw: None,
    "dispatch": lambda self, n, a=None, **kw: '{"status":"mocked"}',
})()

# Einträge mit statischen Handlern (kein self!)
class _MockEntry:
    def __init__(self, handler):
        self.handler = staticmethod(handler)

_reg = _tools.registry.registry
_reg._entries["honcho_conclude"] = _MockEntry(lambda args: '{"status":"ok","concluded":true}')
_reg._entries["bug_hunt_finding"] = _MockEntry(lambda args: '{"status":"ok","finding_id":"test"}')
_reg._entries["plan_create"] = _MockEntry(lambda args: '{"status":"ok","plan_id":"test"}')
_tools.registry.dispatch = _reg.dispatch
sys.modules["tools"] = _tools
sys.modules["tools.registry"] = _tools.registry

# ─── Mock Registry ────────────────────────────────────────────────────────

class MockRegistry:
    """Minimal registry mock for tests."""

    def __init__(self):
        self._entries: dict[str, MagicMock] = {}

    def get_entry(self, name: str) -> MagicMock | None:
        return self._entries.get(name)

    def register(self, name: str, *args, **kwargs) -> None:
        entry = MagicMock()
        entry.name = name
        entry.handler = MagicMock(return_value=json.dumps({"status": "ok"}))
        self._entries[name] = entry

    def deregister(self, name: str) -> None:
        self._entries.pop(name, None)

    def dispatch(self, name: str, args: dict = None, **kwargs) -> Any:
        entry = self.get_entry(name)
        if entry and entry.handler:
            return entry.handler(args or {})
        return None

    def get_all_tool_names(self) -> list[str]:
        return list(self._entries.keys())


@pytest.fixture
def mock_registry():
    """Provide a fresh MockRegistry per test."""
    return MockRegistry()


@pytest.fixture
def mock_plugin_context(mock_registry):
    """Provide a minimal PluginContext mock for register() tests."""
    context = MagicMock()
    context.register_tool = MagicMock()
    context.register_hook = MagicMock()
    context.tool_registry = mock_registry
    return context


# ─── Path Helpers ─────────────────────────────────────────────────────────

@pytest.fixture
def scout_plugin_dir() -> Path:
    """Return the scout plugin directory."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def tmp_shared_patterns(tmp_path) -> Path:
    """Return a temp directory for shared patterns (usable in tests)."""
    path = tmp_path / "patterns"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ─── Integration-Test Registry: echter Dispatch statt pauschaler Mock ────


class RealDispatchRegistry:
    """Registry that dispatches to REAL handler functions.

    Ermöglicht Integrationstests die den gesamten Dispatch-Pipeline testen:
    registry.dispatch() → handler(args) → response parsing.

    Handler werden via .register(name, handler, schema) registriert.
    Die .dispatch()-Methode ruft den Handler mit args auf und returned
    das echte Ergebnis (kein Mock).
    """

    def __init__(self):
        self._entries: dict[str, dict] = {}

    def register(self, name: str, handler, schema: dict | None = None) -> None:
        self._entries[name] = {"handler": handler, "schema": schema or {}}

    def get_entry(self, name: str):
        entry = self._entries.get(name)
        if entry is None:
            return None
        return type("_Entry", (), {
            "handler": staticmethod(entry["handler"]),
            "schema": entry["schema"],
        })()

    def deregister(self, name: str) -> None:
        self._entries.pop(name, None)

    def dispatch(self, name: str, args: dict | None = None, **kwargs) -> str:
        entry = self._entries.get(name)
        if entry is None:
            return json.dumps({"status": "error", "error": f"Unknown tool: {name}"})
        try:
            result = entry["handler"](args or {}, **kwargs)
            if isinstance(result, str):
                return result
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e), "tool": name})

    def get_all_tool_names(self) -> list[str]:
        return list(self._entries.keys())


@pytest.fixture
def real_registry(request):
    """Fixture: Patched registry mit echten Handlern für Integrationstests.

    Nutzt die TOOL_HANDLERS aus analysis.analysis_tools um Scout-eigene
    Tools mit echten Handler-Funktionen zu registrieren.

    Usage:
        def test_real_dispatch(real_registry):
            result = _call_tool("analysis_framework", path="/tmp")
            assert result["status"] != "mocked"

    Optional: Per `request.param` können zusätzliche Handler übergeben werden:
        @pytest.mark.parametrize("real_registry", [extra_handlers], indirect=True)
    """
    import contextlib

    # RealDispatchRegistry aufsetzen
    reg = RealDispatchRegistry()

    # Scout-eigene Handler registrieren (analysis_tools.TOOL_HANDLERS)
    try:
        from scout.analysis.analysis_tools import TOOL_HANDLERS as analysis_handlers

        for name, (schema, handler) in analysis_handlers.items():
            reg.register(name, handler, schema)
    except ImportError:
        pass  # Fallback: nur mit registrierten Handlern weitermachen

    # Zusätzliche Handler via request.param (optional)
    extra = getattr(request, "param", {}) or {}
    for name, (handler, schema) in extra.items():
        reg.register(name, handler, schema)

    # tools.registry patchen
    _tools_module = types.ModuleType("tools")
    _tools_module.registry = types.ModuleType("tools.registry")
    _tools_module.registry.registry = reg
    _tools_module.registry.dispatch = reg.dispatch

    @contextlib.contextmanager
    def _registry_active():
        old_modules = {}
        for mod_name in ("tools", "tools.registry"):
            old_modules[mod_name] = sys.modules.get(mod_name)
            sys.modules[mod_name] = _tools_module if mod_name == "tools" else _tools_module.registry
        try:
            yield reg
        finally:
            for mod_name, old_mod in old_modules.items():
                if old_mod is not None:
                    sys.modules[mod_name] = old_mod
                else:
                    sys.modules.pop(mod_name, None)

    with _registry_active():
        yield reg
