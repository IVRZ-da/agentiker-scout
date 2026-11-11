"""analysis_profiles — Profile, Subagent-Steering und Delegate-Task-Patching.

Bietet:
  - ANALYSIS_PROFILES: 6 Profile (all/code/architecture/deadcode/db/web)
  - get_active_analysis_profile / get_profile_tools
  - inject_subagent_steering: Steering-Text für Subagents
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger("analysis")


# ---------------------------------------------------------------------------
# Analyse-Profile
# ---------------------------------------------------------------------------

ANALYSIS_PROFILES: Dict[str, Dict[str, Any]] = {
    "all": {
        "description": "Alle Analyse-Tools (default)",
        "tools": [
            "analysis_inspect", "analysis_architecture",
            "analysis_deadcode", "analysis_report",
        ],
        "code_intel_profile": "all",
        "recommended_intents": ["code", "architecture", "deadcode", "bug", "performance", "db", "web"],
    },
    "code": {
        "description": "Code-Struktur-Analyse",
        "tools": ["analysis_inspect", "analysis_report"],
        "code_intel_profile": "core",
        "recommended_intents": ["code", "bug"],
    },
    "architecture": {
        "description": "Architektur-Analyse",
        "tools": ["analysis_architecture", "analysis_report"],
        "code_intel_profile": "all",
        "recommended_intents": ["architecture"],
    },
    "deadcode": {
        "description": "Dead-Code-Analyse",
        "tools": ["analysis_deadcode", "analysis_report"],
        "code_intel_profile": "search",
        "recommended_intents": ["deadcode"],
    },
    "db": {
        "description": "Datenbank-Analyse",
        "tools": ["analysis_report"],
        "code_intel_profile": "core",
        "recommended_intents": ["db"],
    },
    "web": {
        "description": "Web-Recherche",
        "tools": ["analysis_report"],
        "code_intel_profile": "core",
        "recommended_intents": ["web"],
    },
}


def get_active_analysis_profile() -> str:
    """Get the active analysis profile from environment variable."""
    profile = os.environ.get("ANALYSIS_PROFILE", "all").lower()
    if profile not in ANALYSIS_PROFILES:
        profile = "all"
    return profile


def get_profile_tools(profile: Optional[str] = None) -> list:
    """Get the list of tools for a given profile."""
    if profile is None:
        profile = get_active_analysis_profile()
    return ANALYSIS_PROFILES.get(profile, ANALYSIS_PROFILES["all"])["tools"]


# ---------------------------------------------------------------------------
# Subagent-Steering
# ---------------------------------------------------------------------------

def inject_subagent_steering() -> str:
    """Generate subagent steering text for analysis context.

    Can be injected into delegate_task child prompts to ensure
    subagents use the right analysis tools.
    """
    profile = get_active_analysis_profile()
    profile_info = ANALYSIS_PROFILES[profile]

    return (
        "\n\n## 🔍 Analysis Tools Available\n"
        f"Active profile: {profile} — {profile_info['description']}\n"
        f"Recommended intents: {', '.join(profile_info['recommended_intents'])}\n\n"
        "**Automated Analysis Tools:**\n"
        "- `analysis_inspect(path, depth)` — multi-step code inspection\n"
        "- `analysis_architecture(path)` — full architecture analysis\n"
        "- `analysis_deadcode(path)` — dead code detection\n"
        "- `analysis_report(scope, findings)` — persist in Honcho\n\n"
        "**Manual code-intel tools (prefer over grep/read_file):**\n"
        "- `code_symbols` / `code_capsule` / `code_overview` — understand file structure\n"
        "- `code_definition` / `code_references` / `code_callers` — navigate code\n"
        "- `code_diagnostics` — LSP errors and warnings\n"
        "- `code_cycle_detector` / `code_dependency_graph` — architecture analysis\n"
        "- `code_unused_finder` — dead code detection\n"
        "- `code_complexity` / `code_hot_paths` — performance hotspots\n\n"
        "Results are automatically tracked and persisted in Honcho for future reference."
    )
