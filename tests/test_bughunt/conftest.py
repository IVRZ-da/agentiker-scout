"""Bughunt test infrastructure for scout plugin.

Provides bh, sample_finding, sample_session fixtures
and all required sys.modules mocks.
"""

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

# ─── sys.path setup ───────────────────────────────────────────────────

_plugin_root = Path(__file__).resolve().parent.parent.parent  # scout/
_parent = str(_plugin_root.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)
if str(_plugin_root) not in sys.path:
    sys.path.insert(0, str(_plugin_root))

# ─── Mocks ───────────────────────────────────────────────────────────

class MockPluginContext:
    def __init__(self):
        self.hooks = {}
        self.skills = []
        self.tools = {}
    def register_hook(self, name, cb): self.hooks[name] = cb
    def register_skill(self, n, p, d): self.skills.append({"name": n, "path": str(p), "description": d})
    def register_tool(self, name, toolset, schema, handler, description=None, emoji=None, override=False):
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler,
                            "description": description, "emoji": emoji, "override": override}


class MockEntry:
    def __init__(self, schema=None): self.schema = schema or {"description": ""}


class MockRegistry:
    def __init__(self): self.entries = {}
    def get_entry(self, name): return self.entries.get(name)
    def register(self, name, **kw): self.entries[name] = MockEntry(kw.get("schema", {"description": ""}))
    def dispatch(self, name, args): return json.dumps({"tool": name, "status": "mocked", "args": args})


# ─── sys.modules injection ───────────────────────────────────────────

# hermes_cli
_h = types.ModuleType("hermes_cli")
_h.plugins = types.ModuleType("hermes_cli.plugins")
_h.plugins.PluginContext = MockPluginContext
sys.modules["hermes_cli"] = _h
sys.modules["hermes_cli.plugins"] = _h.plugins

# tools.registry — Immer setzen (überschreibt root conftest für bughunt Tools)
_t = types.ModuleType("tools")
_t.registry = types.ModuleType("tools.registry")
_t.registry.registry = MockRegistry()
_t.registry.dispatch = lambda n, a: json.dumps({"tool": n, "status": "mocked", "args": a})
sys.modules["tools"] = _t
sys.modules["tools.registry"] = _t.registry

# _fmt mock
_f = types.ModuleType("_fmt")
_f.fmt_ok = (lambda d, **kw: json.dumps({**d, "status": "ok"} if "status" not in d else d, ensure_ascii=False))
_f.fmt_err = lambda m, **kw: json.dumps({"error": m, "status": "error"}, ensure_ascii=False)
_f.fmt_markdown = lambda m, **kw: json.dumps({"result": m, "status": "ok"}, ensure_ascii=False)
_f.fmt_warn = lambda msg, data=None: json.dumps({"status": "warning", "message": msg, **(data or {})}, ensure_ascii=False)
sys.modules["_fmt"] = _f
# NICHT sys.modules["scout._fmt"] setzen — das macht die Root conftest
sys.modules["scout.bughunt._fmt"] = _f

# scout Package
if "scout" not in sys.modules:
    _sp = types.ModuleType("scout")
    _sp.__path__ = [str(_plugin_root)]
    sys.modules["scout"] = _sp
else:
    _sp = sys.modules["scout"]

# scout.bughunt Package + legacy alias
_bd = _plugin_root / "bughunt"
_bp = types.ModuleType("scout.bughunt")
_bp.__path__ = [str(_bd)]
sys.modules["scout.bughunt"] = _bp
_sp.bughunt = _bp  # critical: set as attribute so monkeypatch.setattr("scout.bughunt.*") works

_bl = types.ModuleType("bughunt")
_bl.__path__ = [str(_bd)]
sys.modules["bughunt"] = _bl

# Load bughunt_core via importlib

_cp = _bd / "bughunt_core.py"
_spc = importlib.util.spec_from_file_location("scout.bughunt.bughunt_core", _cp)
_cm = importlib.util.module_from_spec(_spc)
_cm.__package__ = "scout.bughunt"
sys.modules["scout.bughunt.bughunt_core"] = _cm
sys.modules["bughunt.bughunt_core"] = _cm  # for monkeypatch.setattr("bughunt.bughunt_core.*")
sys.modules["bughunt_core"] = _cm  # for `from bughunt_core import Finding`
_bp.bughunt_core = _cm
_bl.bughunt_core = _cm
if _spc and _spc.loader:
    _spc.loader.exec_module(_cm)


# ─── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def bh(tmp_path):
    """Fresh bughunt_core module with isolated data dir."""
    source = _bd / "bughunt_core.py"
    mod_name = f"scout.bughunt.bughunt_core.{tmp_path.name}"
    spec = importlib.util.spec_from_file_location(mod_name, source)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "scout.bughunt"
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    mod.DATA_DIR = tmp_path / "data"
    mod.DATA_DIR.mkdir(parents=True, exist_ok=True)
    mod.SESSIONS_DIR = mod.DATA_DIR / "sessions"
    mod.SESSIONS_DIR.mkdir(exist_ok=True)
    mod.PATTERNS_DIR = mod.DATA_DIR / "patterns"
    mod.PATTERNS_DIR.mkdir(exist_ok=True)
    mod.PLUGIN_DIR = tmp_path
    return mod


@pytest.fixture
def ctx():
    return MockPluginContext()


@pytest.fixture
def sample_finding(bh):
    f = bh.Finding
    return f(title="execSync in stt.ts", severity="P0", category="security",
             file="src/modules/agent/providers/stt.ts", line=78,
             description="execSync mit user-gesteuerten Parametern",
             evidence='execSync(`ffmpeg ...`)', pattern_id="S001",
             suggested_fix="execFile mit param-Array")


@pytest.fixture
def sample_session(bh):
    s = bh.BugHuntSession(project="/test/project", scope="quick")
    bh.save_session(s)
    return s


@pytest.fixture
def sample_session_with_findings(bh, sample_finding):
    s = bh.BugHuntSession(project="/test/project", scope="comprehensive")
    s.add_finding(sample_finding)
    s.add_finding(bh.Finding(title="console.log", severity="P2", category="code-quality",
                              file="src/api/route.ts", line=10, pattern_id="C002"))
    s.add_finding(bh.Finding(title="Silent Catch", severity="P1", category="code-quality",
                              file="src/api/auth.ts", line=42, pattern_id="C001"))
    bh.save_session(s)
    return s
