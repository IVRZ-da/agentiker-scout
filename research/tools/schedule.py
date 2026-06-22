"""
tools/schedule.py — Periodische Recherchen: research_schedule.
"""

import uuid

from scout._fmt import fmt_ok
from scout.research.tools.base import _err

# ---------------------------------------------------------------------------
# research_schedule
# ---------------------------------------------------------------------------

def research_schedule(args: dict, **kwargs) -> str:
    """Plant periodische Recherchen via Hermes cronjob."""
    query = args.get("query", "").strip()
    if not query:
        return _err("query ist erforderlich")

    interval = args.get("interval", "daily")
    if interval not in ("daily", "weekly", "monthly"):
        return _err("interval muss 'daily', 'weekly' oder 'monthly' sein")

    max_sources = max(1, min(50, int(args.get("max_sources", 5))))
    name = args.get("name", f"Research: {query[:40]}")

    schedule_map = {
        "daily": "0 6 * * *",
        "weekly": "0 6 * * 1",
        "monthly": "0 6 1 * *",
    }
    cron_schedule = schedule_map[interval]

    research_id = str(uuid.uuid4())[:8]

    return fmt_ok({
        "research_id": research_id,
        "query": query,
        "interval": interval,
        "max_sources": max_sources,
        "name": name,
        "cron_schedule": cron_schedule,
        "auto_setup": True,
        "instruction": (
            f"Richte jetzt den periodischen Research-Cron-Job ein:\n\n"
            f"cronjob(\n"
            f"  action='create',\n"
            f"  name='{name}',\n"
            f"  schedule='{cron_schedule}',\n"
            f"  prompt='Führe eine Recherche durch zum Thema: {query}. '\n"
            f"          'Nutze research_auto(query=\"{query}\", depth=3, max_sources={max_sources}) '\n"
            f"          'um die Recherche zu starten. Folge den Anweisungen und speichere '\n"
            f"          'die Ergebnisse mit research_save.',\n"
            f"  skills=['deep-research'],\n"
            f")\n\n"
            f"Der Cron-Job läuft {interval} um {cron_schedule} UTC und verwendet "
            f"research_auto für eine vollautonome Recherche."
        ),
    })
