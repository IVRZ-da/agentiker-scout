#!/usr/bin/env python3
"""generate_readme.py — Auto-Generierung der README.md für das scout Plugin.

Liest plugin.yaml, CHANGELOG.md und scout_tool_registry.json und erzeugt
eine README.md mit Tool-Übersicht, Status und aktuellen Changes.

Usage:
    python3 scripts/generate_readme.py
"""

import json
import os
import re
import sys

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_plugin_yaml() -> dict:
    """Read plugin.yaml, return {name, version, description, author}."""
    path = os.path.join(PLUGIN_DIR, "plugin.yaml")
    if not os.path.exists(path):
        return {"name": "scout", "version": "?", "description": "", "author": "agentiker"}
    with open(path) as f:
        text = f.read()
    result = {}
    for key in ("name", "version", "description", "author"):
        m = re.search(rf"^{key}:\s*(.+)", text, re.MULTILINE)
        result[key] = m.group(1).strip().strip("\"'") if m else "?"
    return result


def read_changelog() -> str:
    """Return the latest CHANGELOG entry (everything up to the next ##)."""
    path = os.path.join(PLUGIN_DIR, "CHANGELOG.md")
    if not os.path.exists(path):
        return "—"
    with open(path) as f:
        text = f.read()
    # Find first ## [version] block
    pattern = r'^(#{2,3})\s+\[?([\d.]+)\]?(.*?)(?=\n#{2,3}\s+\[|\Z)'
    m = re.search(pattern, text, re.DOTALL | re.MULTILINE)
    if m:
        return m.group(0).strip()
    return text[:500] + "…" if len(text) > 500 else text


def read_tool_registry() -> dict:
    """Read scout_tool_registry.json, return {domain: [(name, desc)]}."""
    path = os.path.join(PLUGIN_DIR, "scout_tool_registry.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        data = json.load(f)
    result = {}
    for domain, tools in data.items():
        entries = []
        for t in tools:
            schema = t.get("schema", {})
            desc = schema.get("description", "") if isinstance(schema, dict) else ""
            entries.append((t["name"], desc[:80] + "…" if len(desc) > 80 else desc))
        result[domain] = entries
    return result


def make_tool_table(entries: list[tuple[str, str]]) -> str:
    """Format tool list as markdown table."""
    if not entries:
        return "_Keine Tools registriert_"
    lines = [
        "| Tool | Description |",
        "|------|-------------|",
    ]
    for name, desc in entries:
        lines.append(f"| `{name}` | {desc} |")
    return "\n".join(lines)


def generate() -> str:
    meta = read_plugin_yaml()
    changelog = read_changelog()
    registry = read_tool_registry()

    total_tools = sum(len(v) for v in registry.values())

    lines = [
        f"# {meta.get('name', 'scout').title()} Plugin — Hermes Agent",
        "",
        meta.get("description", ""),
        "",
        f"- **Version:** {meta.get('version', '?')}",
        f"- **Author:** {meta.get('author', 'agentiker')}",
        "- **License:** MIT",
        f"- **Total Tools:** {total_tools}",
        "",
        "---",
        "",
        "## Tool-Übersicht",
        "",
    ]

    # Domain sections
    domain_labels = {
        "analysis": "Analysis — Code & Architecture Analysis",
        "bughunt": "Bug-Hunt — Automated Bug Pattern Scanning",
        "research": "Research — Web Research & Synthesis",
    }
    for domain, label in domain_labels.items():
        entries = registry.get(domain, [])
        lines.append(f"### {label} ({len(entries)} Tools)")
        lines.append("")
        lines.append(make_tool_table(entries))
        lines.append("")

    lines.extend([
        "---",
        "",
        "## Latest Changes",
        "",
        changelog,
        "",
        "---",
        "",
        "## Development",
        "",
        "### Setup",
        "",
        "```bash",
        "# Pre-commit hook aktivieren",
        "git config core.hooksPath .githooks",
        "",
        "# Tests ausführen",
        "python3 -m pytest tests/ -q --tb=short",
        "",
        "# Ruff Lint",
        "python3 -m ruff check . --select F,E,T,W,I",
        "```",
        "",
        "Siehe `CONTRIBUTING.md` und `BRANCHING.md` für Details.",
    ])

    return "\n".join(lines)


def main():
    readme = generate()
    out_path = os.path.join(PLUGIN_DIR, "README.md")
    with open(out_path, "w") as f:
        f.write(readme)
    print(f"✅ README.md generated ({len(readme)} chars)")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
