"""
research_tools.py — Legacy Shim für Struktur-Tests.

Re-exportiert alle Tool-Funktionen aus dem neuen tools/ Package.
Wird für Rückwärtskompatibilität in test_structure.py verwendet.
"""

# WICHTIG: Dieser Import funktioniert nur innerhalb des deep_research Packages.
# Für pytest-Struktur-Tests wird stattdessen tools/__init__.py geladen.
from scout.research.tools import (  # noqa: F401
    research_auto,
    research_cleanup,
    research_compare,
    research_delete,
    research_export,
    research_export_all,
    research_merge,
    research_save,
    research_schedule,
    research_search,
    research_start,
    research_stats,
    research_status,
    research_synthesize,
    research_tag,
    research_update,
    research_verify,
)
