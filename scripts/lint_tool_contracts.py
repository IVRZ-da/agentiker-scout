#!/usr/bin/env python3
"""Lint die Tool-Vertraege des scout-Plugins.

Warum
-----
Die Tool-Description ist das, was das Modell sieht, bevor es entscheidet. Ein
Ein-Zeiler wie "Start a bug-hunt session." sagt nicht, *wann* das Tool passt,
*was* zurueckkommt und *was* danach kommt — und genau das kostet Fehlversuche
und Kontext.

Regeln (aus Anthropic "Writing effective tools" + AWS "MCP tool design"):
  R1 Description >= 120 Zeichen
  R2 Description nennt die Rueckgabe (Returns/liefert/gibt ... zurueck)
  R3 Jeder Parameter hat eine description
  R4 Parameter mit <= 6 diskreten Werten tragen ein enum
  R5 <= 8 Parameter pro Tool
  R6 required gesetzt, ausser Tool ist als arg-frei deklariert
  R7 Listen-/Report-Tools bieten response_format (concise|detailed)

Usage:
    python3 scripts/lint_tool_contracts.py            # Report + exit code
    python3 scripts/lint_tool_contracts.py --json     # maschinenlesbar
    python3 scripts/lint_tool_contracts.py --list     # nur Verstoesse
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
REGISTRY_FILE = PLUGIN_DIR / "scout_tool_registry.json"
ANALYSIS_SCHEMAS = PLUGIN_DIR / "analysis" / "tools" / "schemas_data.json"

MIN_DESCRIPTION = 120
MAX_PARAMS = 8

# Tools, die ohne Argumente sinnvoll sind (R6-Ausnahme).
ARG_FREE_OK = {
    "bug_hunt_stats",
    "bug_hunt_history",
    "bug_hunt_pattern",
    "research_stats",
    "research_status",
    "research_search",
    "research_cleanup",
    "research_export",
    "analysis_trend",
}

# Tools, die eine Liste/einen Report liefern -> response_format lohnt (R7).
RESPONSE_FORMAT_TOOLS = {
    "bug_hunt_list",
    "bug_hunt_report",
    "bug_hunt_history",
    "bug_hunt_stats",
    "bug_hunt_pattern",
    "research_search",
    "research_status",
    "research_stats",
    "research_export",
    "research_compare",
    "analysis_inspect",
    "analysis_architecture",
    "analysis_deadcode",
    "analysis_performance",
    "analysis_security",
    "analysis_review",
    "analysis_duplicates",
    "analysis_ui_gap",
    "analysis_graph_query",
    "analysis_diff_analysis",
}

RETURN_HINTS = (
    "returns",
    "return",
    "liefert",
    "gibt",
    "zurueck",
    "zurück",
    "output",
    "ergebnis",
    "result",
    "report",
    "listet",
    "zeigt",
)

# Parameter, die diskrete Wertelisten haben sollten. Bewusst OHNE "scope" und
# "language": scope ist ein freier Projektpfad/Name, language ist offen (35+
# Sprachen) — ein enum waere dort eine willkuerliche Einschraenkung.
VALUE_HINTS = {
    "format",
    "severity",
    "status",
    "action",
    "depth",
    "tier",
    "group_by",
    "mode",
    "level",
    "kind",
}


def load_tools() -> list[dict]:
    """Alle Tool-Schemas aus der einen Wahrheit (``shared.tool_registry``).

    Frueher wurden Registry-JSON und ``schemas_data.json`` getrennt gelesen —
    sobald das Konsolidat die analysis-Tools mitfuehrt, zaehlt das doppelt.
    """
    sys.path.insert(0, str(PLUGIN_DIR.parent))
    from scout.shared.tool_registry import collect

    return [
        {"name": tool.name, "domain": tool.domain, "schema": tool.schema}
        for tool in collect()
    ]


def check_tool(tool: dict) -> list[dict]:
    """Prueft ein Tool gegen alle Regeln. Gibt Verstoesse zurueck."""
    name = tool["name"]
    schema = tool["schema"]
    params = schema.get("parameters") or {}
    props = params.get("properties") or {}
    required = params.get("required") or []
    desc = (schema.get("description") or "").strip()
    issues: list[dict] = []

    def add(rule: str, detail: str) -> None:
        issues.append({"tool": name, "domain": tool["domain"], "rule": rule, "detail": detail})

    if len(desc) < MIN_DESCRIPTION:
        add("R1", f"Description {len(desc)} Zeichen, mindestens {MIN_DESCRIPTION}")

    if desc and not any(h in desc.lower() for h in RETURN_HINTS):
        add("R2", "Description nennt die Rueckgabe nicht")

    for pname, spec in props.items():
        if not isinstance(spec, dict):
            add("R3", f"Parameter '{pname}' ist kein Objekt")
            continue
        if not (spec.get("description") or "").strip():
            add("R3", f"Parameter '{pname}' ohne description")
        if "enum" not in spec and pname in VALUE_HINTS and spec.get("type") == "string":
            add("R4", f"Parameter '{pname}' hat diskrete Werte, aber kein enum")

    if len(props) > MAX_PARAMS:
        add("R5", f"{len(props)} Parameter, maximal {MAX_PARAMS}")

    if not required and name not in ARG_FREE_OK and props:
        add("R6", "kein required gesetzt")

    if name in RESPONSE_FORMAT_TOOLS and "response_format" not in props:
        add("R7", "response_format (concise|detailed) fehlt")

    return issues


def main() -> int:
    ap = argparse.ArgumentParser(description="scout tool contract lint")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list", action="store_true", help="nur Verstoesse")
    args = ap.parse_args()

    tools = load_tools()
    all_issues: list[dict] = []
    for tool in tools:
        all_issues.extend(check_tool(tool))

    by_rule: dict[str, int] = {}
    for issue in all_issues:
        by_rule[issue["rule"]] = by_rule.get(issue["rule"], 0) + 1

    if args.json:
        print(
            json.dumps(
                {
                    "tools": len(tools),
                    "violations": len(all_issues),
                    "by_rule": by_rule,
                    "issues": all_issues,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0 if not all_issues else 1

    print(f"Tools geprueft: {len(tools)}   Verstoesse: {len(all_issues)}")
    if by_rule:
        print("nach Regel: " + ", ".join(f"{r}={n}" for r, n in sorted(by_rule.items())))

    if all_issues and not args.list:
        print()
        for issue in all_issues[:60]:
            print(f"  [{issue['rule']}] {issue['tool']:30} {issue['detail']}")
        if len(all_issues) > 60:
            print(f"  ... und {len(all_issues) - 60} weitere (--json fuer alles)")

    if not all_issues:
        print("Alle Tool-Vertraege erfuellen die Regeln.")
    return 0 if not all_issues else 1


if __name__ == "__main__":
    sys.exit(main())
