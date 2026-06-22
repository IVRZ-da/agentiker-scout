"""
research_core.py — Research Session-Tracker für Honcho-Integration.

Stellt get_active_research() bereit, das von shared/honcho.py
für die Post-Session-Persistenz verwendet wird.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PLUGIN_DIR = Path(__file__).parent
TRACKER_PATH = PLUGIN_DIR / "data" / "_tracker.json"


def get_active_research() -> dict | None:
    """Get current active research session from tracker.

    Returns:
        Dict with query, sources_count if a research is active, else None.
    """
    try:
        if TRACKER_PATH.exists():
            data = json.loads(TRACKER_PATH.read_text())
            research_id = data.get("research_started")
            if research_id:
                return {
                    "query": data.get("query", ""),
                    "sources_count": len(data.get("firecrawl_calls", [])),
                    "research_id": research_id,
                }
    except Exception as e:
        logger.debug("research_core: failed to load tracker: %s", e)
    return None
