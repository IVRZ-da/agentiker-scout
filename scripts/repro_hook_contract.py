#!/usr/bin/env python3
"""Repro: prueft den pre_llm_call-Vertrag des scout-Plugins gegen Hermes 0.23.1.

Hintergrund
-----------
Hermes <= 0.2x rief pre_llm_call-Hooks mit ``messages=[...]`` auf.
Seit Hermes 0.23.1 kommen diese kwargs:

    session_id, task_id, turn_id, user_message, conversation_history,
    is_first_turn, model, platform, parent_session_id, sender_id

Ein Hook, der nur ``messages`` liest, liefert still ``None`` - kein Fehler im Log,
die Intent-Injektion ist einfach tot.

Exit-Codes
----------
0  Hook liefert mit dem echten 0.23.1-Kwarg-Satz Kontext (Vertrag erfuellt)
1  Hook liefert None / Fehler (Bug vorhanden)

Aufruf
------
    cd ~/.hermes/plugins/scout && python3 scripts/repro_hook_contract.py
"""

from __future__ import annotations

import importlib.util
import sys
import traceback
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent

PROMPT = "analysiere die architektur von /home/jo/projekt und finde dead code"


def _load_scout():
    """Importiert das Plugin-Paket, ohne den Hermes-Plugin-Manager zu brauchen."""
    if str(PLUGIN_DIR.parent) not in sys.path:
        sys.path.insert(0, str(PLUGIN_DIR.parent))
    name = "scout"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name,
        PLUGIN_DIR / "__init__.py",
        submodule_search_locations=[str(PLUGIN_DIR)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("scout-Paket konnte nicht geladen werden")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def hermes_0_23_kwargs() -> dict:
    """Exakt der Kwarg-Satz, den agent/turn_context.py in Hermes 0.23.1 uebergibt."""
    return {
        "session_id": "repro-session",
        "task_id": "repro-task",
        "turn_id": "repro-turn",
        "user_message": PROMPT,
        "conversation_history": [],
        "is_first_turn": True,
        "model": "deepseek-v4-flash",
        "platform": "cli",
        "parent_session_id": "",
        "sender_id": "",
    }


def main() -> int:
    _load_scout()
    from scout.shared import intent

    hook = getattr(intent, "on_pre_llm_call", None)
    if hook is None:
        print("FAIL: scout.shared.intent.on_pre_llm_call fehlt", file=sys.stderr)
        return 1

    try:
        result = hook(**hermes_0_23_kwargs())
    except Exception:
        print("FAIL: Hook hat mit dem 0.23.1-Kwarg-Satz eine Exception geworfen:", file=sys.stderr)
        traceback.print_exc()
        return 1

    if isinstance(result, str) and result.strip():
        print("OK: Hook liefert Kontext (%d Zeichen):" % len(result))
        print("   ", result.strip().splitlines()[0][:120])
        return 0

    if isinstance(result, dict) and result.get("context"):
        print("OK: Hook liefert dict mit context (%d Zeichen)" % len(str(result.get("context"))))
        return 0

    print("FAIL: Hook liefert None - Intent-Kontext wird nicht injiziert.", file=sys.stderr)
    print("      Ursache: der Hook liest kwargs['messages'], Hermes 0.23.1 sendet", file=sys.stderr)
    print("      user_message + conversation_history.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
