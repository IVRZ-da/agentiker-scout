#!/usr/bin/env python3
"""README auto-generator for scout — uses shared generate_readme_base.py.

Usage:
    python3 scripts/generate_readme.py          # update README.md in place
    python3 scripts/generate_readme.py --check  # exit 1 if README is stale
    python3 scripts/generate_readme.py --verbose  # show debug info
"""

import json
import re
import sys
from pathlib import Path

BASE = Path.home() / ".hermes" / "scripts" / "generate_readme_base.py"
sys.path.insert(0, str(BASE.parent))
from generate_readme_base import ReadmeGenerator  # noqa: E402, I001


PLUGIN_DIR = Path(__file__).resolve().parent.parent


class ScoutReadmeGenerator(ReadmeGenerator):

    def get_tools(self) -> list[dict]:
        """Extract tools from scout_tool_registry.json + analysis_tools.py."""
        tools = []

        # Analysis tools from analysis/analysis_tools.py
        analysis_file = self.plugin_dir / "analysis" / "analysis_tools.py"
        if analysis_file.exists():
            text = analysis_file.read_text("utf-8")
            analysis_names = re.findall(r'"(analysis_\w+)"', text)
            existing = self._read_existing_descriptions()
            for name in sorted(set(analysis_names)):
                desc = existing.get(name, "Code & architecture analysis tool.")
                tools.append({"name": name, "description": desc, "category": "Analysis — Code & Architecture"})

        # Bughunt + Research from registry
        registry_file = self.plugin_dir / "scout_tool_registry.json"
        if registry_file.exists():
            with open(registry_file) as f:
                registry = json.load(f)
            DOMAIN_LABELS = {
                "bughunt": "Bug-Hunt — Vulnerability Scanning",
                "research": "Research — Web Research & Synthesis",
            }
            for domain, entries in registry.items():
                label = DOMAIN_LABELS.get(domain, domain)
                for entry in entries:
                    name = entry.get("name", "?")
                    schema = entry.get("schema", {})
                    desc = schema.get("description", "") if isinstance(schema, dict) else ""
                    if desc:
                        desc = desc.split(".")[0] + "." if "." in desc else desc[:120]
                    tools.append({"name": name, "description": desc, "category": label})

        return tools

    def _read_existing_descriptions(self) -> dict[str, str]:
        """Read tool descriptions from current README table."""
        if not self.readme_path.exists():
            return {}
        from generate_readme_base import read_existing_descriptions
        return read_existing_descriptions(self.readme_path)

    def get_profiles(self) -> list[dict]:
        return []

    def get_languages(self) -> list[str]:
        return []


if __name__ == "__main__":
    gen = ScoutReadmeGenerator(PLUGIN_DIR)
    sys.exit(gen.run())
