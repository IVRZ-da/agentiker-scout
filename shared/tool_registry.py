"""Eine Wahrheit fuer alle Tool-Definitionen.

Vorher gab es drei Stellen, an denen Tools definiert waren:

* ``analysis/analysis_tools.py`` — ``TOOL_HANDLERS`` (Schema + Handler)
* ``bughunt/data/tool_schemas.json`` — Name, Handler-Pfad, Schema
* ``research/data/tool_schemas.json`` — dito

Diese Datei sammelt sie in **eine** Liste gleicher Form. Alles andere
(Manifest, README, Lint, Evals) ist damit ein Artefakt, kein zweiter Ort fuer
Wahrheit.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

PLUGIN_DIR = Path(__file__).resolve().parent.parent

DOMAINS = ("analysis", "bughunt", "research")

#: Wo eine Domaene ihre Tool-Schemas ablegt (analysis nutzt TOOL_HANDLERS).
DOMAIN_SCHEMA_FILES = {
    "bughunt": PLUGIN_DIR / "bughunt" / "data" / "tool_schemas.json",
    "research": PLUGIN_DIR / "research" / "data" / "tool_schemas.json",
}

#: Reihenfolge, in der Domaenen im Manifest erscheinen.
_TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,60}$")


@dataclass
class ToolDef:
    """Eine Tool-Definition, unabhaengig von ihrer Herkunft."""

    name: str
    domain: str
    schema: dict
    handler: object | None = None
    handler_module: str = ""
    handler_name: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def description(self) -> str:
        return str(self.schema.get("description") or self.name)

    def as_registry_entry(self) -> dict:
        """Form, die ``scout_tool_registry.json`` erwartet."""
        entry = {
            "name": self.name,
            "handler_module": self.handler_module,
            "handler_name": self.handler_name,
            "schema": self.schema,
        }
        entry.update({k: v for k, v in self.extra.items() if k not in entry})
        return entry


def _analysis_tools() -> list[ToolDef]:
    from scout.analysis.analysis_tools import TOOL_HANDLERS

    tools: list[ToolDef] = []
    for name, pair in TOOL_HANDLERS.items():
        schema, handler = pair
        tools.append(ToolDef(
            name=name,
            domain="analysis",
            schema=schema,
            handler=handler,
            handler_module=getattr(handler, "__module__", ""),
            handler_name=getattr(handler, "__name__", name),
        ))
    return tools


def _json_tools(domain: str) -> list[ToolDef]:
    path = DOMAIN_SCHEMA_FILES[domain]
    if not path.exists():
        logger.warning("%s: Schema-Datei fehlt (%s)", domain, path)
        return []

    entries = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(entries, dict):
        entries = entries.get("tools", [])

    tools: list[ToolDef] = []
    for entry in entries:
        name = entry.get("name", "")
        if not name:
            continue
        tools.append(ToolDef(
            name=name,
            domain=domain,
            schema=entry.get("schema", {}),
            handler_module=entry.get("handler_module", ""),
            handler_name=entry.get("handler_name", name),
            extra={k: v for k, v in entry.items()
                   if k not in ("name", "schema", "handler_module", "handler_name")},
        ))
    return tools


def collect(domains: tuple[str, ...] = DOMAINS) -> list[ToolDef]:
    """Sammelt alle Tool-Definitionen in einer Liste.

    Importfehler einer Domaene werden geloggt und uebersprungen — ein defektes
    Analyse-Modul darf die Registrierung der anderen nicht verhindern.
    """
    collected: list[ToolDef] = []
    for domain in domains:
        try:
            if domain == "analysis":
                collected.extend(_analysis_tools())
            else:
                collected.extend(_json_tools(domain))
        except Exception as exc:  # noqa: BLE001 - eine Domaene darf nicht alles kippen
            logger.warning("Domaene %s nicht ladbar: %s", domain, exc)
    return collected


def by_name(domains: tuple[str, ...] = DOMAINS) -> dict[str, ToolDef]:
    return {tool.name: tool for tool in collect(domains)}


def validate(tools: list[ToolDef] | None = None) -> list[str]:
    """Prueft die gesammelten Definitionen auf strukturelle Fehler."""
    tools = collect() if tools is None else tools
    problems: list[str] = []
    seen: dict[str, str] = {}

    for tool in tools:
        if not _TOOL_NAME_RE.match(tool.name):
            problems.append(f"{tool.name}: ungueltiger Tool-Name (snake_case erwartet)")
        if tool.name in seen:
            problems.append(f"{tool.name}: doppelt definiert ({seen[tool.name]} und {tool.domain})")
        seen[tool.name] = tool.domain

        if not isinstance(tool.schema, dict) or not tool.schema:
            problems.append(f"{tool.name}: Schema fehlt")
            continue
        if tool.domain != "analysis" and not tool.handler_module:
            problems.append(f"{tool.name}: handler_module fehlt")
        params = tool.schema.get("parameters")
        if params is not None and not isinstance(params, dict):
            problems.append(f"{tool.name}: parameters ist kein Objekt")

    return problems


def as_registry_map(tools: list[ToolDef] | None = None) -> dict[str, list[dict]]:
    """Form fuer ``scout_tool_registry.json`` (nach Domaene gruppiert)."""
    tools = collect() if tools is None else tools
    result: dict[str, list[dict]] = {domain: [] for domain in DOMAINS}
    for tool in tools:
        result.setdefault(tool.domain, []).append(tool.as_registry_entry())
    return result
