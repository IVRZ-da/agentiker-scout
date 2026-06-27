"""tests/fakes/ — Wiederverwendbare Mock-Factorys für Scout Plugin Tests.

Ersetzt sys.modules Shims durch pytest Fixtures + monkeypatch.
Alle Hermes Plugins können diese Fakes nutzen.
"""

from __future__ import annotations

import json
from typing import Any, Callable
from unittest.mock import MagicMock

# ─── Registry Fake ────────────────────────────────────────────────

class MockEntry:
    """Simuliert einen Registry-Eintrag (tools.registry.Entry)."""

    def __init__(self, handler: Callable | None = None,
                 schema: dict | None = None):
        self.handler = handler or MagicMock(return_value='{"status": "mocked"}')
        self.schema = schema or {}


class MockRegistry:
    """Simuliert tools.registry.registry für Tests."""

    def __init__(self):
        self._entries: dict[str, MockEntry] = {}

    def get_entry(self, name: str) -> MockEntry | None:
        return self._entries.get(name)

    def register(self, name: str, **kwargs: Any) -> None:
        self._entries[name] = MockEntry(**kwargs)

    def deregister(self, name: str) -> None:
        self._entries.pop(name, None)

    def dispatch(self, name: str, args: dict | None = None,
                 **kwargs: Any) -> Any:
        entry = self._entries.get(name)
        if entry and entry.handler:
            return entry.handler(args or {})
        return None

    def get_all_tool_names(self) -> list[str]:
        return list(self._entries.keys())


def create_registry(
    with_devtools: bool = False,
    custom_entries: dict[str, Callable | None] | None = None,
) -> MockRegistry:
    """Erzeugt eine MockRegistry mit optionalen Einträgen.

    Args:
        with_devtools: Wenn True, MCP-DevTools als verfügbar markieren.
        custom_entries: Zusätzliche Tool-Einträge {name: handler_or_None}.

    Returns:
        Konfigurierte MockRegistry.
    """
    registry = MockRegistry()

    if with_devtools:
        registry._entries["mcp_chrome_devtools_list_console_messages"] = (
            MockEntry(MagicMock(return_value='{"messages": []}'))
        )
        registry._entries["mcp_chrome_devtools_list_network_requests"] = (
            MockEntry(MagicMock(return_value='{"requests": []}'))
        )
        registry._entries["mcp_chrome_devtools_take_snapshot"] = (
            MockEntry(MagicMock(return_value='{"snapshot": "mocked"}'))
        )
        registry._entries["mcp_chrome_devtools_evaluate_script"] = (
            MockEntry(MagicMock(
                return_value='{"totalElements": 10, "visible": 8, '
                             '"hidden": 2, "inputs": 2, "buttons": 3, '
                             '"links": 5, "images": 1, "headings": 2}'
            ))
        )
        registry._entries["mcp_chrome_devtools_navigate_page"] = (
            MockEntry(MagicMock(return_value='{"status": "navigated"}'))
        )

    if custom_entries:
        for name, handler in custom_entries.items():
            registry._entries[name] = MockEntry(
                handler or MagicMock(return_value='{"status": "ok"}')
            )

    return registry


# ─── _fmt Fake ────────────────────────────────────────────────────

def create_fmt_mock() -> dict[str, Callable]:
    """Erzeugt _fmt Mock-Funktionen die plain JSON zurückgeben.

    Returns:
        Dict mit fmt_ok, fmt_err, fmt_markdown, fmt_warn.
    """
    return {
        "fmt_ok": lambda d, **kw: json.dumps(
            {**d, "status": "ok"} if "status" not in d else d,
            ensure_ascii=False,
        ),
        "fmt_err": lambda m, **kw: json.dumps(
            {"error": m, "status": "error"}, ensure_ascii=False,
        ),
        "fmt_markdown": lambda m, **kw: json.dumps(
            {"result": m, "status": "ok"}, ensure_ascii=False,
        ),
        "fmt_warn": lambda msg, data=None: json.dumps(
            {"status": "warning", "message": msg, **(data or {})},
            ensure_ascii=False,
        ),
    }


# ─── PluginContext Fake ───────────────────────────────────────────

class MockPluginContext:
    """Simuliert hermes_cli.plugins.PluginContext für register()."""

    def __init__(self):
        self.hooks: dict[str, Any] = {}
        self.skills: list[dict] = []
        self.tools: dict[str, Any] = {}

    def register_hook(self, name: str, cb: Callable) -> None:
        self.hooks[name] = cb

    def register_skill(self, name: str, path: str,
                       description: str) -> None:
        self.skills.append({
            "name": name, "path": path, "description": description,
        })

    def register_tool(self, name: str, toolset: str, schema: dict,
                      handler: Callable, **kwargs: Any) -> None:
        self.tools[name] = {
            "toolset": toolset, "schema": schema, "handler": handler,
            **kwargs,
        }
