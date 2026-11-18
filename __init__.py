"""scout plugin — unified analysis, bug-hunt, and web-research.

Fusion von analysis, bughunt und deep-research mit Shared Pattern Pipeline.
Tool-Namensräume bleiben erhalten: analysis_*, bug_hunt_*, research_*.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hermes_cli.plugins import PluginContext

logger = logging.getLogger("scout")

PLUGIN_DIR = Path(__file__).resolve().parent

# ─── Shutdown-Guard ───────────────────────────────────────────────────
logging.raiseExceptions = False

# ─── Tool-Schema-Index (wird von _register_tools befüllt) ────────────

TOOL_DESCRIPTIONS: dict[str, str] = {}
TOOL_SCHEMAS: dict[str, dict] = {}

# ─── Eager-Tools (Namespace-Modus) ───────────────────────────────────

# Die drei Dispatcher sind der Anker im Tool-Prompt. Gemessen: 42 Einzel-Tools
# kosten 49.751 Zeichen (~12.438 Tokens) als Deferral-Katalog, aber jede Nutzung
# einen Bridge-Turn (`tool_describe` -> `tool_call`). Bei 1.714 echten Calls
# (references/tool-usage-baseline.md) war der Bridge-Umweg der Kostentreiber —
# deshalb wurden die Namen frueher in die Core-Liste rebindet (eager).
# Katalog-Regel 9 verbietet das; seither sind die Dispatcher deferred.
EAGER_TOOLS: tuple[str, ...] = ()
# Bewusst leer: Hermes hat (Stand 0.23.1, auch auf Upstream-main) keinen
# oeffentlichen Weg, ein Plugin-Tool eager zu setzen. ``ctx.register_tool()``
# kennt keinen ``eager``-Parameter, ``plugin.yaml`` kein solches Feld, und
# ``tools/tool_search.py::is_deferrable_tool_name()`` macht nur Core-Tools bzw.
# Tools aus ``_DIRECT_SURFACE_TOOLSETS`` eager. Der frueher genutzte Rebind von
# ``toolsets._HERMES_CORE_TOOLS`` ist Katalog-Regel 9 (kein Runtime-Override von
# Hermes-Core) und deshalb entfernt — die Dispatcher laufen ueber den
# ``tool_call``-Bridge. Ein Upstream-Issue fuer einen echten Seam liegt vor
# (siehe references/core-override-analysis.md).
# ``scripts/tool_schema_audit.py`` rechnet mit leerem EAGER_TOOLS die Summe
# aller Schemata als obere Schranke — das Pre-Commit-Budget bleibt damit gueltig.



# ─── Tool-Registrierung ──────────────────────────────────────────────

def _register_tools(ctx: PluginContext) -> None:
    """Registriert die Tools aus der einen Wahrheit (``shared.tool_registry``).

    Zwei Modi:
    * **Namespace (Default):** 3 Dispatcher (``analysis``/``bughunt``/``research``)
      mit ``op``-Enum, gebaut per Replay der echten Registrierung
      (``namespaces.py``). Sie werden eager gesetzt.
    * **Legacy (``SCOUT_NAMESPACES=0``):** 1:1-Registrierung aller 42 Tools,
      vollstaendig deferred.

    In beiden Modi werden Handler, Schemas und Beschreibungen vorab aufgeloest —
    die Dispatcher bekommen dieselben gewrappten Handler wie der Legacy-Pfad.
    """
    try:
        from scout import namespaces
        from scout.shared.tool_registry import collect
    except ImportError as exc:
        logger.warning("Tool-Registry nicht ladbar: %s", exc)
        return

    tools = list(collect())
    resolved: dict[str, object] = {}
    for tool in tools:
        try:
            handler = tool.handler
            if handler is None:
                handler = _resolve_handler(tool.handler_module, tool.handler_name)
            if handler is None:
                logger.debug("Handler %s.%s nicht gefunden — %s uebersprungen",
                             tool.handler_module, tool.handler_name, tool.name)
                continue

            resolved[tool.name] = _wrap_response_format(handler, tool.schema)
            TOOL_DESCRIPTIONS[tool.name] = tool.description
            TOOL_SCHEMAS[tool.name] = tool.schema
        except Exception as exc:  # noqa: BLE001 - ein Tool darf nicht alle kippen
            logger.warning("Tool %s nicht registrierbar: %s", tool.name, exc)

    if namespaces.namespaces_enabled():
        catalog = namespaces.build_catalog(tools)
        catalog = {
            group: [tool for tool in members if tool.name in resolved]
            for group, members in catalog.items()
        }
        count = namespaces.register_namespaces(
            ctx, catalog, lambda tool: resolved.get(tool.name)
        )
        if count:
            logger.info("scout: %d Namespace-Dispatcher fuer %d Tools", count, len(resolved))
        else:  # nichts dispatchbar -> lieber die Einzeltools als gar nichts
            logger.warning("scout: keine Dispatcher gebaut — Fallback auf Einzel-Tools")
            namespaces = None  # type: ignore[assignment]

    if namespaces is None or not namespaces.namespaces_enabled():
        for tool in tools:
            handler = resolved.get(tool.name)
            if handler is None:
                continue
            try:
                ctx.register_tool(tool.name, tool.domain, tool.schema, handler,
                                  description=tool.description)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Tool %s nicht registrierbar: %s", tool.name, exc)


def _wrap_response_format(handler, schema: dict):
    """Wendet ``response_format="concise"`` zentral auf das Handler-Ergebnis an.

    Nur wenn das Schema den Parameter anbietet — sonst waere die Verdichtung
    eine stille Verhaltensaenderung an Tools, die sie nicht versprechen.
    """
    props = ((schema.get("parameters") or {}).get("properties") or {})
    if "response_format" not in props or handler is None:
        return handler

    from scout._fmt import condense_json, wants_concise

    def wrapped(args: dict | None = None, **kwargs):
        result = handler(args or {}, **kwargs)
        if wants_concise(args):
            return condense_json(result)
        return result

    return wrapped


def _register_domain_tools(
    ctx: PluginContext,
    domain: str,
    tools: list[dict],
) -> None:
    """Register tools for a domain from the registry map."""
    for tool in tools:
        name = tool["name"]
        handler_mod = tool["handler_module"]
        handler_name = tool["handler_name"]
        schema = tool.get("schema", {})
        desc = schema.get("description", name)

        handler = _resolve_handler(handler_mod, handler_name)
        if handler is None:
            logger.debug("Handler %s.%s nicht gefunden", handler_mod, handler_name)
            continue

        handler = _wrap_response_format(handler, schema)

        ctx.register_tool(name, domain, schema, handler, description=desc)
        TOOL_DESCRIPTIONS[name] = desc
        TOOL_SCHEMAS[name] = schema


def _resolve_handler(module_path: str, handler_name: str) -> object:
    """Lazy-import a handler function by dotted module path."""
    try:
        import importlib
        mod = importlib.import_module(module_path)
        return getattr(mod, handler_name, None)
    except (ImportError, AttributeError) as e:
        logger.debug("Handler-Import fehlgeschlagen: %s.%s (%s)",
                     module_path, handler_name, e)
        return None


# ─── Hook-Registrierung ──────────────────────────────────────────────

def _register_hooks(ctx: PluginContext) -> None:
    """Register shared hooks (single pre_llm_call, post_tool_call, on_session_end)."""
    try:
        from scout.shared import intent as intent_mod
        ctx.register_hook("pre_llm_call", intent_mod.on_pre_llm_call)
    except ImportError as e:
        logger.debug("pre_llm_call hook nicht registriert: %s", e)

    try:
        from scout.shared import honcho as honcho_mod
        ctx.register_hook("post_tool_call", honcho_mod.on_post_tool_call)
        ctx.register_hook("on_session_end", honcho_mod.on_session_end)
    except ImportError as e:
        logger.debug("honcho hooks nicht registriert: %s", e)

    # Nutzungs-Messung (v0.6.7): eigenständiger Handler, damit ein Defekt in honcho
    # die Messung nicht mitreißt (und umgekehrt).
    try:
        from scout.shared import usage as usage_mod
        ctx.register_hook("post_tool_call", usage_mod.on_post_tool_call)
    except ImportError as e:
        logger.debug("usage hook nicht registriert: %s", e)


# ─── Namespace-Paket ───────────────────────────────────────────────
# Hermes laedt Plugins unter einem eigenen Modulnamen. Damit die absoluten
# 'from scout.X import Y'-Importe funktionieren, wird 'scout' als
# Namespace-Paket in sys.modules registriert (nur der eigene Name - kein
# Eingriff in 'tools' oder 'shared').
_SCOUT_SHIM_REGISTERED = False


def _ensure_scout_namespace() -> None:
    global _SCOUT_SHIM_REGISTERED
    if _SCOUT_SHIM_REGISTERED:
        return
    if "scout" not in sys.modules:
        scout_mod = type(sys)("scout")
        scout_mod.__path__ = [str(PLUGIN_DIR)]
        scout_mod.__package__ = "scout"
        scout_mod.__name__ = "scout"
        sys.modules["scout"] = scout_mod
    _SCOUT_SHIM_REGISTERED = True


# → Module-Level Execution ←
# 'scout' wird als Namespace-Paket registriert, damit die absoluten
# 'from scout.X import Y'-Importe auch funktionieren, wenn Hermes das Plugin
# unter einem anderen Modulnamen laedt. KEIN Shim fuer 'tools'/'shared' mehr:
# die haetten den Hermes-Core-Namespace ueberschrieben (siehe 0.5.17).
_ensure_scout_namespace()


# ─── Data-Dirs ───────────────────────────────────────────────────────

def _ensure_dirs() -> None:
    """Create the Nutzdaten directories (~/.hermes/data/scout) on first access."""
    from scout.shared import paths

    paths.ensure_dirs()


# ─── Plugin Entry Point ──────────────────────────────────────────────

def register(ctx: PluginContext) -> None:
    """Plugin entry point — registers hooks + tools.

    Abhaengigkeiten stehen im Manifest (``python_dependencies``); fehlende Pakete
    meldet Hermes selbst und installiert sie via ``hermes pm repair``. Kein
    pip-Aufruf zur Laufzeit mehr.
    """
    # Plugin-Dispatch an die echte Hermes-Tool-Registry binden
    # (analysis/research/bughunt rufen honcho_search, code_search_by_error, ...).
    from scout.shared import registry as _registry_mod

    binder = getattr(_registry_mod.registry, "bind_context", None)
    if callable(binder):
        binder(ctx)

    _ensure_dirs()
    _register_tools(ctx)
    _register_hooks(ctx)
