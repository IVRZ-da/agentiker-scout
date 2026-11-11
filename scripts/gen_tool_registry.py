#!/usr/bin/env python3
"""Schreibt ``scout_tool_registry.json`` aus der echten Tool-Registrierung.

Warum
-----
Die Datei war frueher *Quelle* fuer bughunt/research und wurde fuer analysis
ignoriert — zwei Wahrheiten, die auseinanderlaufen konnten. Jetzt sammelt
``shared/tool_registry.py`` die Definitionen aus den Domaenen selbst; hier
entsteht daraus nur noch das Konsolidat, das Lint, README und Evals lesen.

Aufruf
------
    python3 scripts/gen_tool_registry.py            # schreiben
    python3 scripts/gen_tool_registry.py --check    # Exit 1 bei Drift
    python3 scripts/gen_tool_registry.py --manifest # zusaetzlich plugin.yaml
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_FILE = PLUGIN_ROOT / "scout_tool_registry.json"

sys.path.insert(0, str(PLUGIN_ROOT.parent))

from scout.shared.tool_registry import (  # noqa: E402
    DOMAINS,
    as_registry_map,
    collect,
    validate,
)


def render() -> str:
    """Erzeugt den Dateiinhalt (stabil sortiert, damit Diffs klein bleiben)."""
    registry = as_registry_map()
    ordered = {domain: registry.get(domain, []) for domain in DOMAINS}
    return json.dumps(ordered, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="nur pruefen, nicht schreiben (Exit 1 bei Drift)")
    parser.add_argument("--manifest", action="store_true",
                        help="anschliessend plugin.yaml neu erzeugen")
    args = parser.parse_args(argv)

    problems = validate()
    if problems:
        print("Tool-Definitionen fehlerhaft:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 2

    tools = collect()
    content = render()
    current = REGISTRY_FILE.read_text(encoding="utf-8") if REGISTRY_FILE.exists() else ""

    if args.check:
        if content != current:
            print(f"❌ {REGISTRY_FILE.name} ist veraltet — neu erzeugen mit "
                  f"scripts/gen_tool_registry.py", file=sys.stderr)
            return 1
        print(f"✅ {REGISTRY_FILE.name} passt zur Registrierung ({len(tools)} Tools)")
        return 0

    if content != current:
        REGISTRY_FILE.write_text(content, encoding="utf-8")
        print(f"✅ {REGISTRY_FILE.name} geschrieben ({len(tools)} Tools)")
    else:
        print(f"✅ {REGISTRY_FILE.name} unveraendert ({len(tools)} Tools)")

    if args.manifest:
        script = PLUGIN_ROOT / "scripts" / "gen_manifest_capabilities.py"
        result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stdout or result.stderr, file=sys.stderr)
            return result.returncode
        print("✅ plugin.yaml aktualisiert")

    return 0


if __name__ == "__main__":
    sys.exit(main())
