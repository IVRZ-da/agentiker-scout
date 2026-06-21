"""shared/registry.py — Interner Registry-Dispatch für Scout Plugin.

Ersetzt `from tools.registry import registry` (das in Scout nicht existiert).
Alle 19 Stellen in Domain-Modulen importieren weiterhin `tools.registry`,
aber __init__.py registriert dieses Modul via sys.modules.
"""

from __future__ import annotations

import json
from typing import Any, Callable


class Registry:
    """Minimaler Tool-Registry für Dispatch innerhalb des Plugins."""

    def __init__(self) -> None:
        self._entries: dict[str, Entry] = {}

    def get_entry(self, name: str) -> Entry | None:
        return self._entries.get(name)

    def register(self, name: str, handler: Callable | None = None,
                 schema: dict | None = None, **kwargs: Any) -> None:
        self._entries[name] = Entry(
            handler=handler, schema=schema or {},
        )

    def dispatch(self, name: str, args: dict | None = None,
                 **kwargs: Any) -> Any:
        entry = self.get_entry(name)
        if entry and entry.handler:
            return entry.handler(args or {})
        return None

    def deregister(self, name: str) -> None:
        self._entries.pop(name, None)

    def get_all_tool_names(self) -> list[str]:
        return list(self._entries.keys())


class Entry:
    """Registry-Eintrag mit Handler + Schema."""

    def __init__(self, handler: Callable | None = None,
                 schema: dict | None = None) -> None:
        self.handler = handler
        self.schema = schema or {}


# Singleton
registry = Registry()
