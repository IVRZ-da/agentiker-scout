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


ANALYSIS_DESCRIPTIONS = {
    "analysis_architecture": "Full architecture analysis: workspace structure to dependency graph to hot paths to cycle detection to complexity hotspots.",
    "analysis_ask": "Ask a natural language question about a codebase using Honcho context.",
    "analysis_code_move": "Verschiebt ein Symbol (Funktion/Klasse) zwischen Dateien via AST-Extraktion.",
    "analysis_code_query": "Smart Query Router für Code-Intelligence — wählt automatisch das beste Tool.",
    "analysis_deadcode": "Dead code analysis: unused imports, unused functions, orphaned error handlers.",
    "analysis_dependency_risk": "Bewertet Abhängigkeitsrisiken (Score 0-10) einer Datei oder eines Projekts.",
    "analysis_diff": "Compare two analysis results and show what changed — structured diff.",
    "analysis_diff_analysis": "Vergleicht zwei Git-Refs und zeigt geänderte Funktionen mit Complexity-Delta.",
    "analysis_duplicates": "Findet duplizierte/ähnliche Code-Blöcke via AST-Vergleich.",
    "analysis_framework": "Zeigt das Framework-Profil eines Projekts mit Confidence-Scoring.",
    "analysis_graph": "Generate a Mermaid diagram from analysis results (dependency, cycles, summary).",
    "analysis_graph_query": "Durchsucht den Knowledge Graph eines Projekts (Callers, Callees, Hot Paths).",
    "analysis_inspect": "Multi-step code analysis: symbols → definition → references → call hierarchy.",
    "analysis_migration": "Führt YAML-basierte Bulk-Migrationen über ein Projekt aus (dry-run by default).",
    "analysis_pattern_discover": "Discover code patterns that look like bugs but aren't covered by shared patterns.",
    "analysis_performance": "Performance analysis: bottlenecks, complexity hotspots, slow paths.",
    "analysis_report": "Generate a structured analysis report from findings and persist in Honcho.",
    "analysis_review": "Automated Code Review zwischen Git-Refs: Diff + Security + Complexity-Delta.",
    "analysis_risk": "Multi-Faktor Risk Assessment: dependency + complexity + deadcode + security + hotspots.",
    "analysis_security": "Security analysis: orphaned error handlers, vulnerability patterns, anti-patterns.",
    "analysis_test_insight": "Analysiert Testabdeckung eines Symbols oder Projekts, generiert Scaffolds.",
    "analysis_timeline": "Zeigt Evolution eines Symbols über die Git-History mit Complexity-Trend.",
    "analysis_trend": "Trend analysis over time: Symbol-Count, Dead Code, Complexity Hotspots.",
    "analysis_ui_gap": "UI Gap Analysis: backend modules without admin/storefront pages, orphan pages.",
    "analysis_ui_inspect": "UI-Element-Analyse: A11y Tree + DOM-Inspektion + Console/Network-Check.",
    "analysis_watch": "Set up recurring analysis watch (cron job) with change reporting.",
}


class ScoutReadmeGenerator(ReadmeGenerator):

    def get_tools(self) -> list[dict]:
        """Extract tools from scout_tool_registry.json + analysis_tools.py."""
        tools = []

        # Analysis tools from analysis/analysis_tools.py
        analysis_file = self.plugin_dir / "analysis" / "analysis_tools.py"
        if analysis_file.exists():
            text = analysis_file.read_text("utf-8")
            analysis_names = re.findall(r'"(analysis_\w+)"', text)
            for name in sorted(set(analysis_names)):
                desc = ANALYSIS_DESCRIPTIONS.get(name, "Code & architecture analysis tool.")
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
