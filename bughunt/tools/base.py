"""Bug-Hunt Tool Handler — 12 Tools für Bug-Jagd, Triage, Reporting.

Jeder Handler folgt dem Hermes Dispatch Contract:
    (args: dict, **kwargs) -> str
"""

import importlib.util
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger("scout.bughunt")

# Import shared tool dispatch (analysis/tools/base.py)
try:
    from scout.analysis.tools.base import _call_tool
except ImportError:
    # Fallback: _call_tool definieren (falls analysis nicht verfügbar)
    def _call_tool(name: str, **kwargs):
        """Fallback wenn analysis tools nicht geladen."""
        logger.debug("_call_tool: %s nicht verfügbar (analysis tools fehlen)", name)
        return {"error": f"{name} nicht verfügbar"}

# Lazy-load bughunt_core via importlib (avoid relative import issues in tool dispatch)
_CORE_MODULE = None
_PLUGIN_DIR = Path(__file__).resolve().parent.parent


def _get_core():
    """Lazy-load bughunt_core, ensuring init_patterns() is called.

    Tries normal relative import first (uses Python module cache — same
    instance that __init__.py already initialized). Falls back to importlib
    for contexts where relative imports fail (subagent dispatch, etc)."""
    global _CORE_MODULE
    if _CORE_MODULE is not None:
        return _CORE_MODULE

    # 1) Normal relative import — uses sys.modules cache → Singleton
    try:
        from scout.bughunt import bughunt_core as core_mod
        core_mod.init_patterns()  # idempotent — befüllt PATTERNS_BY_ID
        _CORE_MODULE = core_mod
        return _CORE_MODULE
    except (ImportError, AttributeError, ValueError) as e:
        logger.debug("bughunt_core lazy-import fallback: %s", e)
        pass

    # 2) Fallback: importlib mit korrektem Package-Namen
    #    ('scout.bughunt.bughunt_core' statt 'bughunt_core_loader' damit
    #     __package__='scout.bughunt' gesetzt wird → relative imports in
    #     init_patterns() funktionieren)
    core_path = _PLUGIN_DIR / 'bughunt_core.py'

    # Wenn bereits ein sys.modules['bughunt_core'] existiert (z.B. von Tests
    # die 'bughunt_core' direkt importieren und via monkeypatch patchen),
    # dieses verwenden statt eine neue importlib-Instanz zu erzeugen.
    if 'bughunt_core' in sys.modules:
        _CORE_MODULE = sys.modules['bughunt_core']
        _CORE_MODULE.init_patterns()
        return _CORE_MODULE

    spec = importlib.util.spec_from_file_location('scout.bughunt.bughunt_core', core_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load bughunt_core from {core_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules['scout.bughunt.bughunt_core'] = mod
    spec.loader.exec_module(mod)
    mod.init_patterns()  # jetzt sicher: __package__='scout.bughunt'
    # Auch unter bare-name registrieren — für monkeypatch.setattr("bughunt_core.xxx", mock)
    # in Tests. Sonst patchen Tests eine andere Instanz als die Handler verwenden.
    if 'bughunt_core' not in sys.modules:
        sys.modules['bughunt_core'] = mod
    _CORE_MODULE = mod
    return _CORE_MODULE


# Lazy-import bughunt_fix (keine zirkulären Abhängigkeiten)
_FIX_MODULE = None


def _get_fix_mod():
    """Lazy-import bughunt_fix — kein Core-Zugriff nötig."""
    global _FIX_MODULE
    if _FIX_MODULE is not None:
        return _FIX_MODULE
    try:
        from scout.bughunt import bughunt_fix as fix_mod
        _FIX_MODULE = fix_mod
        return _FIX_MODULE
    except (ImportError, AttributeError, ValueError) as e:
        logger.debug("bughunt_fix lazy-import fallback: %s", e)
        pass
    if "bughunt_fix" in sys.modules:
        _FIX_MODULE = sys.modules["bughunt_fix"]
        return _FIX_MODULE
    fix_path = _PLUGIN_DIR / "bughunt_fix.py"
    spec = importlib.util.spec_from_file_location("bughunt_fix", fix_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load bughunt_fix from {fix_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["bughunt_fix"] = mod
    spec.loader.exec_module(mod)
    _FIX_MODULE = mod
    return _FIX_MODULE


# ─── plan_follow Integration via Registry-Dispatch ─────────────────────
# Lose Kopplung: Wenn plan_follow Plugin geladen ist, können wir
# automatisch Bug-Hunt Pläne erstellen. Wenn nicht → Silent Skip.


def _try_create_bughunt_plan(project: str, session_id: str,
                              scope: str = "quick",
                              findings_count: int = 0) -> dict | None:
    """Create a plan_follow plan for the current bug hunt.

    Uses Registry-Dispatch for lose coupling — if plan_follow is not
    loaded, returns None silently.

    Returns:
        dict with plan status, or None if plan_follow unavailable.
    """
    try:
        from tools.registry import registry
        entry = registry.get_entry("plan_create")
        if entry is None:
            return None
        handler = getattr(entry, "handler", None)
        if not callable(handler):
            return None

        # Build plan with 3 phases: Scan → Fix → Verify
        plan_result = handler({
            "goal": f"Bug-Hunt: {project} ({scope})",
            "template": "research",
            "params": {
                "project": project,
                "session_id": session_id,
                "scope": scope,
            },
        })
        return json.loads(plan_result) if isinstance(plan_result, str) else plan_result
    except Exception:
        return None


def _ok(data: dict) -> str:
    """Success response — preserves existing status keys."""
    data.setdefault("status", "ok")
    return json.dumps(data, ensure_ascii=False)


def _err(msg: str) -> str:
    """Error response."""
    return json.dumps({"error": msg, "status": "error"}, ensure_ascii=False)
