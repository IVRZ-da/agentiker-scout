"""Namespace-Fusion (T10): 50 Tools -> 3 Dispatcher mit ``op``-Enum.

Warum drei Dispatcher: siehe ``references/tool-usage-baseline.md``
(1.714 echte Calls; 42 Einzel-Tools waeren teurer). Sie sind **deferred** — einen
oeffentlichen Weg, Plugin-Tools eager zu setzen, gibt es nicht (Katalog-Regel 9);
jeder Aufruf laeuft ueber den ``tool_call``-Bridge.
Diese Tests halten die drei Eigenschaften fest, die die Fusion tragen:

1. **Vollstaendigkeit** — jeder echte Op ist im Enum erreichbar (kein stiller Verlust).
2. **Fehlerqualitaet** — ein falscher/fehlender Parameter nennt die verfuegbaren Ops,
   statt den Dispatcher zu sprengen.
3. **Rueckweg** — ``SCOUT_NAMESPACES=0`` registriert wieder 1:1, ohne Codeänderung.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

import scout  # noqa: E402
from scout import namespaces  # noqa: E402
from scout.shared.tool_registry import collect  # noqa: E402


class StubCtx:
    """Minimaler Plugin-Context: sammelt Registrierungen, ignoriert alles andere."""

    def __init__(self):
        self.tools = {}
        self.hooks = []
        self.middleware = []

    def register_tool(self, name, toolset, schema, handler, description=""):
        self.tools[name] = {"toolset": toolset, "schema": schema,
                            "handler": handler, "description": description}

    def register_hook(self, event, fn=None, **kwargs):
        self.hooks.append(event)

    def register_middleware(self, *a, **k):
        self.middleware.append((a, k))

    def __getattr__(self, item):
        return lambda *a, **k: None


@pytest.fixture(scope="module")
def registered():
    scout.TOOL_SCHEMAS.clear()
    scout.TOOL_DESCRIPTIONS.clear()
    ctx = StubCtx()
    scout.register(ctx)
    return ctx


# ─── 1. Vollstaendigkeit ─────────────────────────────────────────────

def test_three_dispatchers_instead_of_42_tools(registered):
    assert sorted(registered.tools) == sorted(namespaces.GROUPS)


def test_every_real_op_is_reachable(registered):
    real = [t.name for t in collect()]
    offered = set()
    for entry in registered.tools.values():
        offered.update(entry["schema"]["parameters"]["properties"]["op"]["enum"])
    missing = [namespaces.short_name(n) for n in real if namespaces.short_name(n) not in offered]
    assert not missing, f"Ops ohne Dispatcher-Eintrag: {missing}"
    assert len(real) == 50


def test_op_is_required_with_enum(registered):
    for name, entry in registered.tools.items():
        params = entry["schema"]["parameters"]
        assert params["required"] == ["op"], name
        assert params["properties"]["op"]["enum"], name


def test_parameter_union_keeps_core_parameters(registered):
    analysis = registered.tools["analysis"]["schema"]["parameters"]["properties"]
    assert {"path", "op"} <= set(analysis)
    assert "depth" in analysis


def test_every_dispatcher_has_description(registered):
    for name, entry in registered.tools.items():
        assert entry["description"].strip(), f"{name} ohne Beschreibung"
        assert len(entry["description"]) > 100, f"{name}: Beschreibung nennt die Ops nicht"


def test_schema_budget_is_bounded(registered):
    """50 Tools muessen unter 20.000 Zeichen (~5.000 Tokens) bleiben."""
    total = sum(len(json.dumps(e["schema"], ensure_ascii=False)) for e in registered.tools.values())
    assert total < 20_000, f"Dispatcher-Summe {total} chars ueberschreitet das Budget"


def test_dispatchers_are_not_forced_eager():
    """Katalog-Regel 9: kein Rebind von Hermes-Core, also keine eager-Markierung."""
    assert scout.EAGER_TOOLS == ()


def test_plugin_never_writes_core_attributes():
    """Regression: das Plugin darf kein Attribut eines Core-Moduls setzen.

    Der frueher genutzte Rebind ``toolsets._HERMES_CORE_TOOLS = core`` hat
    ``hermes plugins validate`` (Katalog-Regel 9) rot gemacht. Dieser Test haelt
    den Rueckweg zu.
    """
    import re
    from pathlib import Path

    root = Path(scout.__file__ or ".").resolve().parent
    pattern = re.compile(r"^(?!\s*#).*\._?[A-Za-z_]*HERMES_CORE[A-Za-z_]*\s*=", re.M)
    hits = [
        f"{p.relative_to(root)}:{i}"
        for p in root.rglob("*.py")
        if ".git" not in p.parts and "tests" not in p.parts
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
        if pattern.match(line)
    ]
    assert hits == [], f"Core-Attribut wird geschrieben: {hits}"


# ─── 2. Fehlerqualitaet (isolierter Dispatcher) ──────────────────────

def _fake_tool(name, domain, props, required, description=None):
    return SimpleNamespace(
        name=name,
        domain=domain,
        schema={"name": name, "description": description or name,
                "parameters": {"type": "object", "properties": props, "required": required}},
        description=description or name,
        handler=None,
        handler_module="x",
        handler_name="y",
    )


@pytest.fixture()
def dispatcher():
    calls = {}

    def handler(args, **kwargs):
        calls["last"] = args
        return {"status": "success", "args": args}

    tools = [
        _fake_tool("demo_alpha", "demo", {"path": {"type": "string", "description": "Datei"}}, ["path"]),
        _fake_tool("demo_beta", "demo", {"path": {"type": "string"}, "count": {"type": "integer"}}, []),
    ]
    spec = namespaces.build_dispatcher("demo", tools, lambda tool: handler)
    return spec, calls


def test_dispatcher_without_op_lists_available_ops(dispatcher):
    spec, _ = dispatcher
    result = json.loads(spec["handler"]({}))
    assert result["status"] == "error"
    assert "op" in result["error"]
    assert "alpha" in result["error"] and "beta" in result["error"]


def test_dispatcher_unknown_op_lists_available_ops(dispatcher):
    spec, _ = dispatcher
    result = json.loads(spec["handler"]({"op": "gibtsnicht"}))
    assert result["status"] == "error"
    assert "gibtsnicht" in result["error"]
    assert "alpha" in result["error"]


def test_dispatcher_enforces_required_parameters(dispatcher):
    spec, calls = dispatcher
    result = json.loads(spec["handler"]({"op": "alpha"}))
    assert result["status"] == "error"
    assert "path" in result["error"]
    assert "last" not in calls, "Handler darf bei fehlendem Pflichtparameter nicht laufen"


def test_dispatcher_accepts_short_and_full_name(dispatcher):
    spec, calls = dispatcher
    for op in ("alpha", "demo_alpha"):
        out = spec["handler"]({"op": op, "path": "/tmp/x"})
        assert out["status"] == "success", op
    assert calls["last"] == {"path": "/tmp/x"}, "op darf nicht an den Handler durchgereicht werden"


def test_dispatcher_wraps_handler_exceptions(dispatcher):
    tools = [_fake_tool("demo_gamma", "demo", {}, [])]
    spec = namespaces.build_dispatcher("demo", tools, lambda tool: (_ for _ in ()).throw(RuntimeError("boom")))
    result = json.loads(spec["handler"]({"op": "gamma"}))
    assert result["status"] == "error"
    assert "boom" in result["error"]


# ─── 3. Rueckweg: Legacy-Modus ───────────────────────────────────────

def test_legacy_mode_registers_all_tools(monkeypatch):
    monkeypatch.setenv(namespaces.NAMESPACES_ENV, "0")
    assert not namespaces.namespaces_enabled()
    ctx = StubCtx()
    scout.register(ctx)
    assert len(ctx.tools) == 50, sorted(ctx.tools)[:5]
    assert "analysis" not in ctx.tools


def test_namespaces_enabled_default_and_switches(monkeypatch):
    monkeypatch.delenv(namespaces.NAMESPACES_ENV, raising=False)
    assert namespaces.namespaces_enabled()
    for off in ("0", "false", "no", "off", " OFF "):
        monkeypatch.setenv(namespaces.NAMESPACES_ENV, off)
        assert not namespaces.namespaces_enabled(), off


def test_catalog_replay_covers_all_domains():
    catalog = namespaces.build_catalog(collect())
    assert {g: len(v) for g, v in catalog.items()} == {"analysis": 20, "bughunt": 13, "research": 17}


# ─── 4. Randfaelle der Schema-Union und der Registrierung ────────────

def test_merged_parameters_keeps_list_type():
    """Op mit ``type: [string, array]`` behaelt den Typ (kein Raten)."""
    tools = [
        _fake_tool("demo_a", "demo", {"path": {"type": ["string", "array"]}}, []),
        _fake_tool("demo_b", "demo", {"path": {"type": ["string", "array"]}}, []),
    ]
    params = namespaces.build_dispatcher("demo", tools, lambda t: None)["schema"]["parameters"]
    assert params["properties"]["path"]["type"] == ["string", "array"]


def test_merged_parameters_flags_conflicting_types():
    """Widerspruechliche Typen: Typ weg, Hinweis bleibt sichtbar."""
    tools = [
        _fake_tool("demo_a", "demo", {"depth": {"type": "integer", "description": "Tiefe"}}, []),
        _fake_tool("demo_b", "demo", {"depth": {"type": "string", "description": "Tiefe"}}, []),
    ]
    prop = namespaces.build_dispatcher("demo", tools, lambda t: None)["schema"]["parameters"]["properties"]["depth"]
    assert "type" not in prop
    assert "Typ je nach op" in prop["description"]


def test_merged_parameters_takes_description_from_later_op():
    """Erster Op ohne Beschreibung, zweiter mit — Beschreibung wird nachgezogen."""
    tools = [
        _fake_tool("demo_a", "demo", {"x": {"type": "string"}}, []),
        _fake_tool("demo_b", "demo", {"x": {"type": "string", "description": "Erklaerung"}}, []),
    ]
    prop = namespaces.build_dispatcher("demo", tools, lambda t: None)["schema"]["parameters"]["properties"]["x"]
    assert prop["description"] == "Erklaerung"


def test_dispatcher_reports_missing_handler():
    tools = [_fake_tool("demo_a", "demo", {}, [])]
    spec = namespaces.build_dispatcher("demo", tools, lambda t: None)
    result = json.loads(spec["handler"]({"op": "a"}))
    assert result["status"] == "error"
    assert "nicht gefunden" in result["error"]


def test_build_tool_specs_skips_empty_domains():
    catalog = {"analysis": [], "bughunt": [_fake_tool("bughunt_x", "bughunt", {}, [])], "research": []}
    specs = namespaces.build_tool_specs(catalog, lambda t: lambda a, **k: None)
    assert [s["name"] for s in specs] == ["bughunt"]


def test_register_namespaces_survives_broken_context():
    """Ein werfender Context darf die anderen Dispatcher nicht blockieren."""
    class Broken(StubCtx):
        def register_tool(self, name, *a, **k):
            if name == "bughunt":
                raise RuntimeError("kaputt")
            super().register_tool(name, *a, **k)

    catalog = namespaces.build_catalog(collect())
    ctx = Broken()
    count = namespaces.register_namespaces(ctx, catalog, lambda t: lambda a, **k: None)
    assert count == 3
    assert sorted(ctx.tools) == ["analysis", "research"]


def test_legacy_coverage_detects_missing_op():
    real = [_fake_tool("analysis_inspect", "analysis", {}, [])]
    ok_specs = namespaces.build_tool_specs(namespaces.build_catalog(real), lambda t: None)
    assert namespaces.legacy_coverage(namespaces.build_catalog(real), ok_specs) == []

    stale = [{"schema": {"parameters": {"properties": {"op": {"enum": ["andere"]}}}}}]
    assert namespaces.legacy_coverage(namespaces.build_catalog(real), stale) == ["inspect"]
