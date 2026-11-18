"""Nutzungs-Messung: eine JSONL-Zeile pro Scout-Tool-Aufruf.

Ohne diese Zahlen ist „wird kaum benutzt" Bauchgefühl. Die Datei ist append-only,
eine Zeile pro Aufruf, kein Locking nötig (Zeilen < 4 KiB, ``O_APPEND`` ist atomar).

Pfad: ``~/.hermes/logs/plugin-usage.jsonl`` — umstellbar über ``PLUGIN_USAGE_LOG``
(Tests schreiben in ein tmp-Verzeichnis). Auswertung::

    python3 -c "import json,collections,sys; \\
      c=collections.Counter((json.loads(l)['tool'], json.loads(l)['op']) \\
      for l in open('/home/jo/.hermes/logs/plugin-usage.jsonl')); print(c.most_common(20))"
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_ENV = "PLUGIN_USAGE_LOG"
_DEFAULT_LOG = Path.home() / ".hermes" / "logs" / "plugin-usage.jsonl"

# Dispatcher-Namen (Namespace-Modus) und deren Legacy-Präfixe (SCOUT_NAMESPACES=0).
# Achtung: die Legacy-Namen heißen ``bug_hunt_*`` (mit Unterstrich), nicht ``bughunt_*``.
_DOMAINS = ("analysis", "bughunt", "research")
_LEGACY_PREFIXES = ("analysis_", "bug_hunt_", "research_")


def log_path() -> Path:
    """Ziel-Datei; ``PLUGIN_USAGE_LOG`` gewinnt (Tests, Umzüge)."""
    return Path(os.environ.get(LOG_ENV) or _DEFAULT_LOG)


def is_scout_tool(name: str) -> bool:
    """True für die drei Dispatcher und ihre 42 Legacy-Einzelnamen."""
    return name in _DOMAINS or name.startswith(_LEGACY_PREFIXES)


def _op_of(kwargs: dict[str, Any]) -> str | None:
    """``op`` aus den Tool-Argumenten, egal ob dict oder JSON-String."""
    args: Any = kwargs.get("arguments") or kwargs.get("tool_args") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            return None
    if isinstance(args, dict):
        op = args.get("op")
        return op if isinstance(op, str) else None
    return None


def on_post_tool_call(**kwargs: Any) -> None:
    """Schreibt eine Messzeile für jeden Scout-Aufruf; bricht nie einen Turn."""
    name = str(kwargs.get("tool_name") or "")
    if not is_scout_tool(name):
        return
    try:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "plugin": "scout",
            "tool": name,
            "op": _op_of(kwargs),
            "session_id": kwargs.get("session_id"),
            "error": bool(kwargs.get("error") or kwargs.get("is_error")),
        }
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 — Messung darf nie einen Turn brechen
        pass
