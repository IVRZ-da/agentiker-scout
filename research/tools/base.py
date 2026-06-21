"""
tools/base.py — Gemeinsame Helfer für das Deep Research Plugin.

Stellt _ok/_err Formatierung, JSON-IO, Pfad-Validierung und
Plan-Follow-Integration als lose gekoppelte Module bereit.
"""

import json
import typing
from datetime import datetime, timezone
from pathlib import Path

from scout._fmt import fmt_err, fmt_ok

PLUGIN_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PLUGIN_DIR / "data"
PLANS_DIR = DATA_DIR / "plans"
RESULTS_DIR = DATA_DIR / "results"

# Ensure directories exist on first import
PLANS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Zeit
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# JSON-IO
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            return {}
    return {}


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Validierung
# ---------------------------------------------------------------------------

def _validate_research_id(rid: str) -> str | None:
    """Validiert eine research_id. None = gültig, str = Fehlermeldung."""
    if not rid:
        return "research_id ist erforderlich"
    if "/" in rid or "\\" in rid or ".." in rid:
        return "research_id darf keine Pfad-Trennzeichen enthalten"
    return None


# ---------------------------------------------------------------------------
# Auflistungen
# ---------------------------------------------------------------------------

def _list_results() -> list[dict]:
    """List all completed research results, newest first."""
    results = []
    for f in sorted(RESULTS_DIR.glob("*.json"), reverse=True):
        data = _read_json(f)
        if data:
            results.append({
                "research_id": data.get("id", f.stem),
                "query": data.get("query", ""),
                "status": data.get("status", ""),
                "timestamp": data.get("saved_at", ""),
                "depth": data.get("depth", 0),
                "sources_count": len(data.get("sources", [])),
                "findings_count": len(data.get("findings", [])),
            })
    return results


def _list_orphan_plans() -> list[dict]:
    """List plans that have no matching result (started but never saved)."""
    orphans = []
    for f in sorted(PLANS_DIR.glob("*.json"), reverse=True):
        data = _read_json(f)
        if data:
            rid = data.get("id", f.stem)
            if not (RESULTS_DIR / f"{rid}.json").exists():
                orphans.append({
                    "research_id": rid,
                    "query": data.get("query", ""),
                    "status": data.get("status", "planned"),
                    "depth": data.get("depth", 0),
                    "created_at": data.get("created_at", ""),
                })
    return orphans


# ---------------------------------------------------------------------------
# Response-Wrapper
# ---------------------------------------------------------------------------

def _ok(data: dict) -> str:
    return fmt_ok(data)


def _err(msg: str) -> str:
    return fmt_err(msg)


# ---------------------------------------------------------------------------
# Plan-Follow Integration (lose Kopplung via Registry)
# ---------------------------------------------------------------------------

def _try_create_plan_follow_plan(query: str, research_id: str) -> dict | None:
    """
    Erzeugt einen Plan im plan_follow Plugin via Registry (lose Kopplung).

    Schlägt silent fehl wenn plan_follow nicht geladen ist.
    Wirft keine Exceptions — Fehler werden als dict returned.
    """
    try:
        from tools.registry import registry

        entry = registry.get_entry("plan_create")
        if entry is None:
            return None  # plan_follow nicht geladen

        handler = getattr(entry, "handler", None)
        if not callable(handler):
            return None

        result = handler({
            "goal": f"Recherche: {query}",
            "template": "research",
        })

        if isinstance(result, str):
            return typing.cast(dict, json.loads(result))
        if isinstance(result, dict):
            return result
        return None
    except ImportError:
        return None  # tools.registry nicht verfügbar (z.B. Tests)
    except Exception as e:
        return {"error": str(e)}
