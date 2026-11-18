"""namespaces.py — 3 Dispatcher statt 42 Einzel-Tools (Analogie zu code_intel v0.6.25).

Warum: 42 Tool-Schemata sind nur dann billig, solange sie deferred sind. Jede Nutzung
kostet dann aber einen Bridge-Turn (``tool_describe`` → ``tool_call``). Die Messung in
``references/tool-usage-baseline.md`` zeigt 1.714 echte Calls — der Bridge-Umweg ist der
Kostentreiber, nicht die Anzahl der Tools. Drei Dispatcher mit ``op``-Enum sind billig und behalten die gesamte Funktionsflaeche.
Sie sind **deferred**: Hermes bietet keinen oeffentlichen Weg, Plugin-Tools eager zu
setzen (Katalog-Regel 9 verbietet den frueheren Rebind von ``toolsets._HERMES_CORE_TOOLS``).

Aufbau (bewusst kein zweites Mapping):
* Der Katalog wird durch **Replay der echten Registrierung** aufgebaut
  (``shared.tool_registry.collect()``), nicht aus einer handgepflegten Liste. Drift ist
  damit strukturell ausgeschlossen.
* Parameter eines Dispatchers = **Union** der Parameter seiner Ops; ``required`` bleibt
  leer, die Pflichtparameter werden beim Dispatch geprueft (Fehler nennt sie + die
  verfuegbaren Ops).
* ``SCOUT_NAMESPACES=0`` stellt die 1:1-Registrierung wieder her.

Der Dispatcher-Name ist der Domain-Name (``analysis``, ``bughunt``, ``research``), der
``op`` ist entweder der volle Tool-Name (``analysis_inspect``) oder der Kurzname
(``inspect``) — beides wird akzeptiert.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable, Iterable

logger = logging.getLogger("scout")

NAMESPACES_ENV = "SCOUT_NAMESPACES"
GROUPS: tuple[str, ...] = ("analysis", "bughunt", "research")

# Domain -> akzeptierte Tool-Praefixe. ``bughunt`` ist der Sonderfall: die Domain
# heisst ohne Unterstrich, die Tools beginnen aber mit ``bug_hunt_``. Beide Formen
# werden akzeptiert, damit Umbenennungen in der Registry nichts unerreichbar machen.
DOMAIN_PREFIXES: dict[str, tuple[str, ...]] = {
    "analysis": ("analysis_",),
    "bughunt": ("bug_hunt_", "bughunt_"),
    "research": ("research_",),
}

# Deckel fuer die Kurzbeschreibung eines Ops im Dispatcher-Schema. Ohne Deckel kostet
# die Aufzaehlung so viel wie die Einzelschemata, die sie ersetzt.
_OP_DESC_LIMIT = 70
_PROP_DESC_LIMIT = 80


def namespaces_enabled() -> bool:
    """Default an; ``SCOUT_NAMESPACES=0`` (auch false/no/off) schaltet auf Legacy."""
    raw = os.environ.get(NAMESPACES_ENV, "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _first_sentence(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def short_name(tool_name: str) -> str:
    """``analysis_inspect`` -> ``inspect``, ``bug_hunt_start`` -> ``start``.

    Die Domain ``bughunt`` traegt das Praefix ``bug_hunt_`` (mit Unterstrich) — die
    naive Regel ``domain + "_"`` wuerde dort nichts strippen und das Enum mit 13
    redundanten Langnamen fuellen.
    """
    for prefixes in DOMAIN_PREFIXES.values():
        for prefix in prefixes:
            if tool_name.startswith(prefix):
                return tool_name[len(prefix):]
    return tool_name


def _local_short(tool_name: str, domain: str) -> str:
    """Kurzname relativ zum *eigenen* Dispatcher-Domain.

    ``short_name`` kennt die drei festen Domains; ein Dispatcher muss jedes Praefix
    seiner eigenen Gruppe strippen (sonst existiert der Kurzname nicht und nur der
    volle Tool-Name waere erreichbar).
    """
    for prefix in DOMAIN_PREFIXES.get(domain, (domain + "_",)):
        if tool_name.startswith(prefix):
            return tool_name[len(prefix):]
    return tool_name


def build_catalog(tools: Iterable[Any]) -> dict[str, list[Any]]:
    """Gruppiert die echten Tool-Objekte nach Domain (Replay der Registrierung)."""
    catalog: dict[str, list[Any]] = {group: [] for group in GROUPS}
    for tool in tools:
        domain = getattr(tool, "domain", None)
        if domain in catalog:
            catalog[domain].append(tool)
        else:  # unbekannte Domain: nicht verschlucken, aber auch nicht dispatchen
            logger.warning("scout namespaces: Domain %r unbekannt (%s)", domain, tool.name)
    return catalog


def _merged_parameters(tools: list[Any]) -> dict[str, Any]:
    """Union der Parameter aller Ops — Konflikte bleiben konfliktfrei statt zu raten.

    Typ-Logik: ``type: ["string", "array"]`` ist eine **Union** (einer von beiden),
    kein Konflikt. Ein echter Konflikt liegt nur vor, wenn ein Op weniger erlaubt als
    die Gesamtmenge (``string`` vs. ``integer``) — dann faellt der Typ weg und die
    Beschreibung sagt "Typ je nach op". Ein flaches Set pro Parameter reicht dafuer
    nicht: es wuerde die Union eines einzelnen Ops als Konflikt zaehlen.
    """
    props: dict[str, Any] = {}
    declared_sets: dict[str, list[frozenset[str]]] = {}
    ordered: dict[str, list[str]] = {}
    for tool in tools:
        params = (tool.schema or {}).get("parameters") or {}
        for name, spec in (params.get("properties") or {}).items():
            spec = dict(spec or {})
            declared = spec.get("type")
            if isinstance(declared, list):
                current = frozenset(str(t) for t in declared)
            elif declared:
                current = frozenset({str(declared)})
            else:
                current = None
            if current:
                declared_sets.setdefault(name, []).append(current)
                # Reihenfolge des ersten Ops erhalten (semantisch: haeufigste Form zuerst)
                for item in ([str(x) for x in declared] if isinstance(declared, list) else [str(declared)]):
                    bucket = ordered.setdefault(name, [])
                    if item not in bucket:
                        bucket.append(item)
            if name not in props:
                desc = _first_sentence(spec.get("description", ""), _PROP_DESC_LIMIT)
                props[name] = {k: v for k, v in spec.items() if k in ("type", "items", "enum")}
                if desc:
                    props[name]["description"] = desc
            elif not props[name].get("description") and spec.get("description"):
                props[name]["description"] = _first_sentence(spec["description"], _PROP_DESC_LIMIT)

    for name, sets in declared_sets.items():
        merged = frozenset().union(*sets)
        conflict = any(seen != merged for seen in sets)
        if conflict:
            props[name].pop("type", None)
            props[name]["description"] = (
                props[name].get("description", "") + " (Typ je nach op)"
            ).strip()
        elif len(merged) > 1:
            props[name]["type"] = ordered.get(name, sorted(merged))
        else:
            props[name]["type"] = next(iter(merged))
    return {"type": "object", "properties": props}


def build_dispatcher(domain: str, tools: list[Any], resolve: Callable[[Any], Callable | None]) -> dict[str, Any]:
    """Baut Schema + Handler fuer einen Namespace."""
    by_full = {tool.name: tool for tool in tools}
    by_short = {_local_short(tool.name, domain): tool for tool in tools}

    lines = [f"Scout {domain}: waehle die Operation ueber 'op'."]
    for tool in sorted(tools, key=lambda t: t.name):
        lines.append(f"- {_local_short(tool.name, domain)}: {_first_sentence(tool.description or tool.name, _OP_DESC_LIMIT)}")
    description = "\n".join(lines)

    parameters = _merged_parameters(tools)
    parameters["required"] = ["op"]
    parameters["properties"] = {
        "op": {
            "type": "string",
            "enum": sorted(by_short),
            "description": "Operation (Kurzname). Alternativ der volle Tool-Name.",
        },
        **parameters["properties"],
    }

    schema = {"name": domain, "description": description, "parameters": parameters}

    def handler(args: dict | None = None, **kwargs) -> Any:
        args = dict(args or {})
        op = args.pop("op", None)
        if not op:
            return _error(
                f"Pflichtparameter 'op' fehlt. Verfuegbar: {', '.join(sorted(by_short))}",
                domain,
            )
        tool = by_full.get(str(op)) or by_short.get(str(op))
        if tool is None:
            return _error(
                f"Unbekannter op {op!r} fuer {domain}. Verfuegbar: {', '.join(sorted(by_short))}",
                domain,
            )
        try:
            fn = resolve(tool)
        except Exception as exc:  # Lookup-Fehler darf den Dispatcher nicht kippen
            return _error(
                f"Handler-Lookup fuer {tool.name} fehlgeschlagen: {type(exc).__name__}: {exc}",
                domain,
            )
        if fn is None:
            return _error(f"Handler fuer {tool.name} nicht gefunden", domain)

        required = ((tool.schema or {}).get("parameters") or {}).get("required") or []
        missing = [p for p in required if p not in args]
        if missing:
            return _error(
                f"{_local_short(tool.name, domain)}: Pflichtparameter fehlt: {', '.join(missing)}",
                domain,
            )
        try:
            return fn(args, **kwargs)
        except Exception as exc:  # ein kaputter Op darf den Dispatcher nicht kippen
            logger.warning("scout %s.%s failed: %s", domain, op, exc)
            return _error(f"{tool.name} fehlgeschlagen: {type(exc).__name__}: {exc}", domain)

    return {"name": domain, "schema": schema, "handler": handler, "description": description}


def _error(message: str, domain: str) -> str:
    return json.dumps({"status": "error", "namespace": domain, "error": message}, ensure_ascii=False)


def build_tool_specs(catalog: dict[str, list[Any]], resolve: Callable[[Any], Callable | None]) -> list[dict[str, Any]]:
    specs = []
    for domain in GROUPS:
        tools = catalog.get(domain) or []
        if not tools:
            continue
        specs.append(build_dispatcher(domain, tools, resolve))
    return specs


def register_namespaces(ctx, catalog: dict[str, list[Any]], resolve: Callable[[Any], Callable | None]) -> int:
    """Registriert die Dispatcher. Gibt die Anzahl zurueck."""
    specs = build_tool_specs(catalog, resolve)
    for spec in specs:
        try:
            ctx.register_tool(
                spec["name"],
                spec["name"],
                spec["schema"],
                spec["handler"],
                description=spec["description"],
            )
        except Exception as exc:  # ein Namespace darf die anderen nicht blockieren
            logger.warning("scout namespaces: %s nicht registrierbar: %s", spec["name"], exc)
    return len(specs)


def legacy_coverage(catalog: dict[str, list[Any]], specs: list[dict[str, Any]]) -> list[str]:
    """Ops im Katalog, die kein Dispatcher anbietet (muss leer sein)."""
    offered = set()
    for spec in specs:
        offered.update(spec["schema"]["parameters"]["properties"]["op"]["enum"])
    return [
        short_name(tool.name)
        for tools in catalog.values()
        for tool in tools
        if short_name(tool.name) not in offered
    ]
