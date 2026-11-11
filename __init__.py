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

# ─── Tool-Registrierung ──────────────────────────────────────────────

def _register_tools(ctx: PluginContext) -> None:
    """Register all tools via ctx.register_tool() from scout_tool_registry.json."""
    import json  # lazy import — structure test erzwingt das

    # Lade Schema-Map aus JSON (wenn vorhanden)
    _schemas_path = PLUGIN_DIR / "scout_tool_registry.json"
    _registry_map: dict[str, list[dict]] = {}
    if _schemas_path.exists():
        try:
            _registry_map = json.loads(_schemas_path.read_text())
        except (json.JSONDecodeError, OSError):
            logger.debug("scout_tool_registry.json konnte nicht geladen werden")

    # ── Analysis (13 Tools) ──────────────────────────────────────────
    try:
        from scout.analysis.analysis_tools import TOOL_HANDLERS
        for name, (schema, handler) in TOOL_HANDLERS.items():
            desc = (schema.get("description") or schema.get("name", name))
            ctx.register_tool(name, "analysis", schema, handler, description=desc)
            TOOL_DESCRIPTIONS[name] = desc
            TOOL_SCHEMAS[name] = schema
    except ImportError as e:
        logger.debug("Konnte analysis tools nicht registrieren: %s", e)

    # ── Bughunt (13 Tools) ───────────────────────────────────────────
    _register_domain_tools(ctx, "bughunt", _registry_map.get("bughunt", []))

    # ── Research (17 Tools) ──────────────────────────────────────────
    _register_domain_tools(ctx, "research", _registry_map.get("research", []))


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
    """Create data directories on first access."""
    (PLUGIN_DIR / "bughunt" / "data" / "sessions").mkdir(parents=True, exist_ok=True)
    (PLUGIN_DIR / "bughunt" / "data" / "patterns").mkdir(parents=True, exist_ok=True)
    (PLUGIN_DIR / "research" / "data" / "results").mkdir(parents=True, exist_ok=True)
    (PLUGIN_DIR / "analysis" / "data").mkdir(parents=True, exist_ok=True)


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
