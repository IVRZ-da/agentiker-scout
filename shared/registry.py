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

import inspect
import logging
import re
from typing import Any, Callable

logger = logging.getLogger("scout.registry")

#: Antwort eines Hosts, wenn er den Toolnamen nicht kennt. Hermes liefert das als
#: String ("Unknown tool: X") bzw. als JSON-Objekt mit ``error``-Feld.
_UNKNOWN_TOOL_RE = re.compile(
    r"(?i)\bunknown tool\b|\btool not found\b|\bno such tool\b|\bnot registered\b"
)


def _is_unknown_tool(result: Any) -> bool:
    """True, wenn ``result`` die Antwort 'dieses Tool gibt es nicht' ist.

    Bewusst nur auf kurze Strings pruefen: ein echter Report kann das Wort
    enthalten, ist aber lang.
    """
    if not isinstance(result, str):
        return False
    return len(result) <= 300 and bool(_UNKNOWN_TOOL_RE.search(result))


def hermes_registry() -> Any:
    """Echte Hermes-Tool-Registry, oder ``None`` ausserhalb von Hermes.

    Wichtig: ``tools.registry`` ist das Host-Modul. Frueher zeigte ein
    ``sys.modules``-Shim diesen Namen auf dieses Modul — dann waere hier immer
    ``None`` bzw. die falsche Registry zurueckgekommen.
    """
    try:
        from tools.registry import registry as _hr  # type: ignore[import-not-found]
        return _hr
    except Exception:  # noqa: BLE001 — Standalone (Tests, Skripte)
        return None


def hermes_has_tool(name: str) -> bool:
    """Ist ``name`` beim Host registriert? Wirft nie."""
    hr = hermes_registry()
    if hr is None:
        return False
    try:
        return hr.get_entry(name) is not None
    except Exception:  # noqa: BLE001
        return False


_ALIAS_CACHE: dict[str, tuple[str, str]] | None = None


def _tool_aliases() -> dict[str, tuple[str, str]]:
    """Alias-Tabelle, lazy geladen (kein Import-Zyklus auf Modulebene)."""
    global _ALIAS_CACHE
    if _ALIAS_CACHE is None:
        table: dict[str, tuple[str, str]] = {}
        try:
            from scout.shared.tool_alias import TOOL_ALIASES

            table = TOOL_ALIASES
        except Exception:  # noqa: BLE001 — ohne Tabelle bleibt alles beim Alten
            logger.debug("scout.registry: Alias-Tabelle nicht ladbar", exc_info=True)
        _ALIAS_CACHE = table
    return _ALIAS_CACHE



def call_handler(handler: Callable, args: dict | None = None, **kwargs: Any) -> Any:
    """Ruft einen Handler mit der Signatur auf, die er tatsaechlich hat.

    Drei Formen sind im Umlauf und alle drei sind legitim:

    * ``handler(args: dict)``          — Hermes-Standard
    * ``handler(**kwargs)``            — reine Keyword-Handler
    * ``handler(args, **kwargs)``      — beides gemischt

    Vorher rief ``dispatch`` immer ``handler(args)`` auf; ein ``**kwargs``-Handler
    antwortete mit ``TypeError: takes 0 positional arguments``.
    """
    args = args or {}
    try:
        signature = inspect.signature(handler)
    except (TypeError, ValueError):
        # Builtins/C-Erweiterungen: keine Introspektion moeglich
        return handler(args, **kwargs)

    parameters = list(signature.parameters.values())
    accepts_var_kw = any(p.kind is p.VAR_KEYWORD for p in parameters)
    positional = [
        p for p in parameters
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]

    if not positional:
        if accepts_var_kw:
            return handler(**{**args, **kwargs})
        # handler() ohne jeden Parameter
        return handler()

    return handler(args, **kwargs)


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
        """Ruft einen lokalen Handler auf — oder reicht an Hermes weiter.

        Alte code_intel-Einzelnamen (``code_symbols``, ``code_security_scan`` …)
        werden hier **zentral** auf den Namespace-Dispatcher umgeschrieben
        (``code_search``/``op=symbols``). Das ist die einzige Stelle, die alle
        Aufrufer abdeckt: ``_call_tool``, direkte ``registry.dispatch``-Aufrufe
        und die Hook-Pfade. Ohne diese Umschreibung liefen die Aufrufe mit
        aktivierten Namespaces in ``Unknown tool`` und die Analyse-Tools
        lieferten still leere Ergebnisse.
        """
        entry = self.get_entry(name)
        if entry and entry.handler:
            return call_handler(entry.handler, args, **kwargs)

        args = dict(args or {})
        target, target_args = self.resolve_alias(name, args)
        result = self._dispatch_hermes_tool(target, target_args, **kwargs)

        if not _is_unknown_tool(result):
            return result

        # Gegenrichtung probieren: Namespace-Erkennung kann daneben liegen
        # (z.B. wenn ``tools.registry`` aus dem Plugin nicht erreichbar ist).
        if target != name:
            retry_name, retry_args = name, args
        else:
            retry_name, retry_args = self.force_alias(name, args)
        if retry_name and retry_name != target:
            alternative = self._dispatch_hermes_tool(retry_name, retry_args, **kwargs)
            if not _is_unknown_tool(alternative):
                return alternative
        return result

    def resolve_alias(self, name: str, args: dict) -> tuple[str, dict]:
        """Alias nur anwenden, wenn der Host den Namespace kennt und den Einzelnamen nicht."""
        alias = _tool_aliases().get(name)
        if alias is None:
            return name, args
        group, op = alias
        if not hermes_has_tool(group):
            return name, args  # Namespaces aus (CODE_INTEL_NAMESPACES=0)
        if hermes_has_tool(name):
            return name, args  # Einzeltool existiert weiterhin
        return self._apply_alias(name, args)

    def force_alias(self, name: str, args: dict) -> tuple[str | None, dict]:
        """Alias ohne Verfuegbarkeitspruefung — Fallback nach einem ``Unknown tool``."""
        if name not in _tool_aliases():
            return None, args
        return self._apply_alias(name, args)

    @staticmethod
    def _apply_alias(name: str, args: dict) -> tuple[str, dict]:
        group, op = _tool_aliases()[name]
        existing = args.get("op")
        if existing not in (None, "", op):
            return name, args  # der Aufrufer meint eine andere Operation
        rewritten = dict(args)
        rewritten["op"] = op
        return group, rewritten

    def deregister(self, name: str) -> None:
        self._entries.pop(name, None)

    def get_all_tool_names(self) -> list[str]:
        return list(self._entries.keys())


# Singleton
registry = Registry()
