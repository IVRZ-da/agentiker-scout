"""Shared conftest for scout plugin tests.

Vereinheitlicht die Mock-Infrastruktur aus 3 Quell-Plugins.
Bietet MockPluginContext, MockRegistry und _fmt Mock.
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
