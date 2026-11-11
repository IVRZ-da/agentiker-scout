"""shared/registry.py — Tool-Dispatch fuer das Scout-Plugin.

Zwei Aufgaben
-------------
1. **Dispatch an echte Hermes-Tools.** Hermes 0.23.1 bietet dafuer die
   oeffentliche Plugin-API ``ctx.dispatch_tool(name, args)``. Beim ``register()``
   bindet ``__init__.py`` den Context hier ein (``bind_context``). Vorher zeigte
   ``tools.registry`` per sys.modules-Shim auf dieses Modul — die echte Registry
   war damit unerreichbar und jeder Dispatch lief still ins Leere.
2. **Lokale Registrierung** (``register``/``get_entry``) fuer plugin-interne
   Handler, die ohne Hermes laufen (Tests, Skripte).
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger("scout.registry")


class Entry:
    """Registry-Eintrag mit Handler + Schema."""

    def __init__(self, handler: Callable | None = None,
                 schema: dict | None = None) -> None:
        self.handler = handler
        self.schema = schema or {}


class Registry:
    """Plugin-Registry: lokale Handler zuerst, danach Hermes-Tools."""

    def __init__(self) -> None:
        self._entries: dict[str, Entry] = {}
        self._context: Any = None

    # ── Hermes-Anbindung ────────────────────────────────────────────
    def bind_context(self, ctx: Any) -> None:
        """Hermes-PluginContext setzen (in ``register()`` aufgerufen)."""
        self._context = ctx

    def _dispatch_hermes_tool(self, name: str, args: dict, **kwargs: Any) -> Any:
        if self._context is None:
            return None
        try:
            return self._context.dispatch_tool(name, args, **kwargs)
        except Exception as e:  # Tool fehlt/deaktiviert -> Plugin bleibt funktionsfaehig
            logger.debug("scout.registry: dispatch %s failed: %s", name, e)
            return None

    # ── Lokale Registry ─────────────────────────────────────────────
    def get_entry(self, name: str) -> Entry | None:
        return self._entries.get(name)

    def register(self, name: str, handler: Callable | None = None,
                 schema: dict | None = None, **kwargs: Any) -> None:
        self._entries[name] = Entry(handler=handler, schema=schema or {})

    def dispatch(self, name: str, args: dict | None = None, **kwargs: Any) -> Any:
        entry = self.get_entry(name)
        if entry and entry.handler:
            return entry.handler(args or {})
        return self._dispatch_hermes_tool(name, args or {}, **kwargs)

    def deregister(self, name: str) -> None:
        self._entries.pop(name, None)

    def get_all_tool_names(self) -> list[str]:
        return list(self._entries.keys())


# Singleton
registry = Registry()
