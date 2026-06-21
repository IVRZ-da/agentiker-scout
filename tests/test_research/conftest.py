"""
conftest.py — Mockt Hermes-Interne Module für scout.research Tests.

Wird vor allen Tests ausgeführt. Stellt sicher dass `scout._fmt`,
`scout.research.research_hooks`, `hermes_cli` und `tools.registry`
als Mock-Module verfügbar sind, damit das Research-Modul
auch ausserhalb von Hermes getestet werden kann.

Unterstützt die tools/ Package-Struktur unter scout/research/tools/.
"""

import json
import sys
import types
import warnings
from pathlib import Path

# ---------------------------------------------------------------------------
# DeprecationWarning-Filter: __package__ != __spec__.parent bei importlib
# Modul-Loading in Tests — bekanntes Python 3.12+ Artefakt
# ---------------------------------------------------------------------------
warnings.filterwarnings("ignore", message=".*__package__.*")

# ---------------------------------------------------------------------------
# sys.path + _fmt Mock (muss VOR _mock_hermes stehen, damit relative Imports
# sauber auflösen)
# ---------------------------------------------------------------------------
SCOUT_ROOT = Path(__file__).resolve().parent.parent.parent  # scout/
_PARENT = str(SCOUT_ROOT.parent)  # plugins/
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

# scout/research/ für bare `import research_hooks` in den Hook-Tests
_research_dir = SCOUT_ROOT / "research"
_str_research = str(_research_dir)
if _str_research not in sys.path:
    sys.path.insert(0, _str_research)

# _fmt Mock: registriert auf allen 3 Ebenen die die Source braucht
_fmt_mock = types.ModuleType("_fmt")
_fmt_mock.fmt_ok = lambda d, **kw: json.dumps(
    {**d, "status": "ok"} if "status" not in d else d, ensure_ascii=False)
_fmt_mock.fmt_err = lambda m, **kw: json.dumps({"error": m, "status": "error"}, ensure_ascii=False)
_fmt_mock.fmt_info = lambda m, **kw: json.dumps({"info": m, "status": "info"}, ensure_ascii=False)
_fmt_mock.fmt_markdown = lambda m, **kw: json.dumps({"result": m, "status": "ok"}, ensure_ascii=False)
_fmt_mock.fmt_code = lambda m, **kw: json.dumps({"result": m, "status": "ok"})
_fmt_mock.fmt_research_status = lambda d, **kw: json.dumps(
    {**d, "status": "ok"} if "status" not in d else d, ensure_ascii=False)
_fmt_mock.fmt_table = lambda d, **kw: json.dumps({"status": "ok", "rows": len(d) if d else 0}, ensure_ascii=False)
_fmt_mock.fmt_table_simple = lambda d, **kw: json.dumps({"status": "ok"}, ensure_ascii=False)
_fmt_mock.fmt_json = lambda d, **kw: json.dumps(d, ensure_ascii=False) if isinstance(d, dict | list) else json.dumps({"data": str(d)})
_fmt_mock.fmt_warn = lambda m, **kw: json.dumps({"warning": m, "status": "warning"}, ensure_ascii=False)
_fmt_mock._strip_ansi = lambda s: s.replace("\x1b[", "").replace("m", "")  # simple mock
sys.modules["_fmt"] = _fmt_mock
sys.modules["scout.research._fmt"] = _fmt_mock
# NICHT sys.modules["scout._fmt"] setzen — das macht die Root conftest

# scout Package in sys.modules vorhalten (verhindert Ausführung von __init__.py)
# Nur setzen wenn nicht bereits von conftest geladen
if "scout" not in sys.modules:
    _scout_pkg = types.ModuleType("scout")
    _scout_pkg.__path__ = [str(SCOUT_ROOT)]
    _scout_pkg.__package__ = "scout"
    sys.modules["scout"] = _scout_pkg

# scout.research sub-package
_research_pkg = types.ModuleType("scout.research")
_research_pkg.__path__ = [str(_research_dir)]
_research_pkg.__package__ = "scout.research"
sys.modules["scout.research"] = _research_pkg

# research_hooks via importlib laden (echter Code für die Hook-Tests)
# und in BEIDE Namespaces eintragen – so nutzen sowohl
#   `from scout.research.research_hooks import reset_tracker` (crud.py)
# als auch
#   `from research_hooks import on_post_tool_call` (Hook-Tests)
# dieselbe Modul-Instanz.
import importlib.util as _il  # noqa: E402

_hooks_path = _research_dir / "research_hooks.py"
_hooks_spec = _il.spec_from_file_location("scout.research.research_hooks", str(_hooks_path))
_hooks_mod = _il.module_from_spec(_hooks_spec)
_hooks_mod.__package__ = "scout.research"
sys.modules["scout.research.research_hooks"] = _hooks_mod
sys.modules["research_hooks"] = _hooks_mod  # bare Name für Hook-Tests
_hooks_spec.loader.exec_module(_hooks_mod)

# ---------------------------------------------------------------------------
# Mock hermes_cli.plugins + tools.registry
# ---------------------------------------------------------------------------
def _mock_hermes():
    """Mock hermes_cli.plugins + tools.registry — NUR setzen wenn nicht von root conftest."""
    if "hermes_cli" not in sys.modules or not hasattr(sys.modules["hermes_cli"], "plugins"):
        modules_to_mock = {
            "hermes_cli": types.ModuleType("hermes_cli"),
            "hermes_cli.plugins": types.ModuleType("hermes_cli.plugins"),
        }
        for name, mod in modules_to_mock.items():
            sys.modules[name] = mod

        hermes_cli_plugins = sys.modules["hermes_cli.plugins"]
        hermes_cli_plugins.PluginContext = type("PluginContext", (), {})

    # tools.registry — root conftest hat bereits Einträge (plan_create, honcho_conclude)
    # Nur setzen wenn root conftest noch nicht aktiv war
    if "tools" not in sys.modules or not hasattr(sys.modules["tools"], "registry"):
        _tools_mod = types.ModuleType("tools")
        _tools_reg = types.ModuleType("tools.registry")
        _tools_reg.registry = type("Registry", (), {"get_entry": lambda self, name: None, "_entries": {}})()
        _tools_mod.registry = _tools_reg
        sys.modules["tools"] = _tools_mod
        sys.modules["tools.registry"] = _tools_reg
    else:
        # Registry existiert — ergänze plan_follow Mock
        tools_reg = sys.modules["tools.registry"]
        if not hasattr(tools_reg, "_plan_follow_handler"):
            tools_reg._plan_follow_handler = None
        if not hasattr(tools_reg, "set_plan_follow_mock"):
            tools_reg.set_plan_follow_mock = _set_plan_follow_mock


def _set_plan_follow_mock(handler):
    """Setzt einen Mock-Handler für plan_create im Registry."""
    from tools.registry import registry  # noqa: F811

    if handler is not None:
        entry = type("MockEntry", (), {})()
        entry.handler = handler
        registry.get_entry = lambda name, e=entry: e if name == "plan_create" else None
    else:
        registry.get_entry = lambda name: None


_mock_hermes()


# ---------------------------------------------------------------------------
# Plugin-Test-Hilfsfunktionen (shared zwischen Tests)
# ---------------------------------------------------------------------------

def make_research_tools(tmp_path: Path):
    """
    Erzeugt eine Tools-Instanz mit tmp_path als Plugin-Verzeichnis.

    Lädt die tools/ Package-Struktur aus scout/research/tools/ in folgender Reihenfolge:
    1. tools/base.py laden (exec_module)
    2. Pfade auf tmp_path patchen (NACH exec_module, damit Funktionen
       zur Call-Time die gepatchten Werte sehen)
    3. tools/crud.py, tools/search.py, tools/export.py, tools/schedule.py
       laden — importieren PLANS_DIR etc. von der gepatchten base
    4. Combined Modul-Objekt für Rückwärtskompatibilität
    """
    # Alte Module-Reste entfernen
    for key in list(sys.modules.keys()):
        if "research_tools" in key or "scout.research.tools" in key:
            del sys.modules[key]

    import importlib.util  # noqa: F811

    def _load_tool_module(filepath: str, module_name: str, pkg: str):
        """Lädt ein Tool-Modul und gibt es zurück."""
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = pkg
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)
        return mod

    # 1. Base laden (erstmal mit echten Pfaden)
    base_path = _research_dir / "tools" / "base.py"
    base_mod = _load_tool_module(
        str(base_path),
        f"scout.research.tools.base.{tmp_path.name}",
        "scout.research.tools",
    )

    # 2. Nach exec_module: Pfade auf tmp_path patchen
    #    (Module-Level Variablen werden beim exec_module überschrieben,
    #     aber Funktionen wie research_start lesen PLANS_DIR zur Call-Zeit)
    base_mod.PLUGIN_DIR = tmp_path
    base_mod.DATA_DIR = tmp_path / "data"
    base_mod.PLANS_DIR = tmp_path / "data" / "plans"
    base_mod.RESULTS_DIR = tmp_path / "data" / "results"
    base_mod.PLANS_DIR.mkdir(parents=True, exist_ok=True)
    base_mod.RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Wichtig: base_mod in sys.modules mit package-qualified name
    # Damit from .base import PLANS_DIR in crud.py richtig auflöst
    sys.modules["scout.research.tools.base"] = base_mod

    # 3. CRUD, Search, Export, Schedule laden
    #    Diese importieren from .base import PLANS_DIR, RESULTS_DIR —
    #    und bekommen die gepatchten Werte
    tool_configs = [
        ("crud", _research_dir / "tools" / "crud.py"),
        ("search", _research_dir / "tools" / "search.py"),
        ("export", _research_dir / "tools" / "export.py"),
        ("schedule", _research_dir / "tools" / "schedule.py"),
    ]

    tool_funcs = {}
    for mod_name, mod_path in tool_configs:
        full_name = f"scout.research.tools.{mod_name}.{tmp_path.name}"
        mod = _load_tool_module(str(mod_path), full_name, "scout.research.tools")
        for attr in dir(mod):
            if not attr.startswith("_") and callable(getattr(mod, attr)):
                tool_funcs[attr] = getattr(mod, attr)

    # 4. Combined Modul für Rückwärtskompatibilität
    combined = types.ModuleType(f"research_tools.{tmp_path.name}")
    for name, func in tool_funcs.items():
        setattr(combined, name, func)
    # Aliase
    combined.PLUGIN_DIR = tmp_path
    combined.DATA_DIR = tmp_path / "data"
    combined.PLANS_DIR = tmp_path / "data" / "plans"
    combined.RESULTS_DIR = tmp_path / "data" / "results"

    sys.modules[f"research_tools.{tmp_path.name}"] = combined
    return combined
