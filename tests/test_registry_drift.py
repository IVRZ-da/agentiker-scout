"""Registrierungs-Drift: eine Wahrheit, viele Artefakte.

Die Wahrheit sind die Domaenen (``shared/tool_registry.collect()``). Alles
andere — Konsolidat, Manifest, README — muss daraus folgen. Diese Tests
scheitern, sobald jemand ein Tool hinzufuegt und die Artefakte vergisst.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_FILE = PLUGIN_ROOT / "scout_tool_registry.json"
MANIFEST = PLUGIN_ROOT / "plugin.yaml"
README = PLUGIN_ROOT / "README.md"

sys.path.insert(0, str(PLUGIN_ROOT.parent))

from scout.shared.tool_registry import (  # noqa: E402
    DOMAIN_SCHEMA_FILES,
    DOMAINS,
    as_registry_map,
    by_name,
    collect,
    validate,
)


@pytest.fixture(scope="module")
def tools():
    return collect()


@pytest.fixture(scope="module")
def registry_map():
    return as_registry_map()


def test_collect_finds_all_domains(tools):
    domains = {tool.domain for tool in tools}
    assert domains == set(DOMAINS), domains
    assert len(tools) == 42, f"erwartet 42 Tools, gefunden {len(tools)}"


def test_no_duplicate_names(tools):
    names = [tool.name for tool in tools]
    assert len(names) == len(set(names))


def test_validate_has_no_problems(tools):
    assert validate(tools) == []


def test_every_tool_has_schema(tools):
    without = [t.name for t in tools if not t.schema]
    assert without == []


def test_every_tool_has_handler(tools):
    """Analysis liefert Handler direkt, bughunt/research per Modulpfad."""
    missing = [
        tool.name for tool in tools
        if tool.handler is None and not tool.handler_module
    ]
    assert missing == [], f"ohne Handler: {missing}"


def test_registry_file_matches_registration(registry_map):
    """Das eingecheckte Konsolidat muss der Registrierung entsprechen."""
    on_disk = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    assert set(on_disk) == set(DOMAINS), on_disk.keys()

    for domain in DOMAINS:
        disk = on_disk.get(domain, [])
        live = registry_map.get(domain, [])
        assert len(disk) == len(live), (
            f"{domain}: {len(disk)} in der Datei, {len(live)} registriert — "
            f"scripts/gen_tool_registry.py ausfuehren"
        )
        disk_names = sorted(entry["name"] for entry in disk)
        live_names = sorted(entry["name"] for entry in live)
        assert disk_names == live_names, f"{domain} driftet: {set(disk_names) ^ set(live_names)}"


def test_generator_is_idempotent():
    """Ein zweiter Lauf darf nichts aendern (sonst rauscht jeder Commit)."""
    before = REGISTRY_FILE.read_text(encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(PLUGIN_ROOT / "scripts" / "gen_tool_registry.py"), "--check"],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert REGISTRY_FILE.read_text(encoding="utf-8") == before


def _manifest_tools() -> list[str]:
    text = MANIFEST.read_text(encoding="utf-8")
    match = re.search(r"^provides_tools:\s*$(.*?)(?=^\S|\Z)", text, re.M | re.S)
    assert match, "provides_tools nicht im Manifest"
    return re.findall(r"^\s{2}- (\S+)$", match.group(1), re.M)


def test_manifest_lists_every_tool(tools):
    declared = set(_manifest_tools())
    actual = {tool.name for tool in tools}
    assert declared == actual, (
        f"fehlt im Manifest: {sorted(actual - declared)}; "
        f"zuviel: {sorted(declared - actual)}"
    )


def test_readme_tool_count_is_current(tools):
    text = README.read_text(encoding="utf-8")
    match = re.search(r"> (\d+) tools across", text)
    assert match, "Tool-Zahl im README nicht gefunden"
    assert int(match.group(1)) == len(tools), (
        f"README nennt {match.group(1)}, registriert sind {len(tools)} — "
        f"scripts/generate_readme.py ausfuehren"
    )


def test_each_json_domain_owns_its_schemas():
    """bughunt/research tragen ihre Schemas selbst — keine zentrale Datei."""
    for domain in ("bughunt", "research"):
        path = DOMAIN_SCHEMA_FILES[domain]
        assert path.exists(), f"{domain}: {path.name} fehlt"
        entries = json.loads(path.read_text(encoding="utf-8"))
        assert entries, f"{domain}: leere Schema-Datei"
        for entry in entries:
            assert entry.get("name"), f"{domain}: Eintrag ohne name"
            assert entry.get("schema"), f"{domain}/{entry.get('name')}: Schema fehlt"


def test_analysis_keeps_single_handler_map():
    """Analysis definiert Schema+Handler an genau einer Stelle."""
    from scout.analysis.analysis_tools import TOOL_HANDLERS

    for name, pair in TOOL_HANDLERS.items():
        assert isinstance(pair, tuple) and len(pair) == 2, name
        schema, handler = pair
        assert schema.get("name") in (name, None), f"{name}: Schema-Name passt nicht"
        assert callable(handler), name


def test_registry_lookup_is_complete(tools):
    index = by_name()
    assert set(index) == {tool.name for tool in tools}
    for name, tool in index.items():
        assert tool.name == name


# ---------------------------------------------------------------------------
# dispatch: alle drei Handler-Signaturen
# ---------------------------------------------------------------------------

def test_call_handler_args_dict_form():
    from scout.shared.registry import call_handler

    def handler(args):
        return args.get("x")

    assert call_handler(handler, {"x": 1}) == 1


def test_call_handler_kwargs_form():
    """``def handler(**kwargs)`` — antwortete vorher mit TypeError."""
    from scout.shared.registry import call_handler

    def handler(**kwargs):
        return kwargs.get("x")

    assert call_handler(handler, {"x": 2}) == 2


def test_call_handler_both_form():
    from scout.shared.registry import call_handler

    def handler(args, **kwargs):
        return (args.get("x"), kwargs.get("y"))

    assert call_handler(handler, {"x": 3}, y=4) == (3, 4)


def test_call_handler_no_parameters():
    from scout.shared.registry import call_handler

    def handler():
        return "ohne"

    assert call_handler(handler, {"ignored": True}) == "ohne"


def test_dispatch_uses_signature_aware_call():
    from scout.shared.registry import Registry

    registry = Registry()
    calls = []

    def kwargs_handler(**kwargs):
        calls.append(kwargs)
        return "ok"

    registry.register("demo", kwargs_handler)
    assert registry.dispatch("demo", {"a": 1}) == "ok"
    assert calls == [{"a": 1}]


def test_dispatch_falls_back_to_hermes_context():
    from scout.shared.registry import Registry

    class Ctx:
        def dispatch_tool(self, name, args, **kwargs):
            return ("hermes", name, args)

    registry = Registry()
    registry.bind_context(Ctx())
    assert registry.dispatch("fremd", {"q": 1}) == ("hermes", "fremd", {"q": 1})


def test_dispatch_without_context_returns_none():
    from scout.shared.registry import Registry

    registry = Registry()
    assert registry.dispatch("unbekannt", {}) is None


# ---------------------------------------------------------------------------
# Fehlerpfade der Registry (Deckung der Ausnahmen)
# ---------------------------------------------------------------------------

def test_hermes_dispatch_exception_is_swallowed():
    """Ein fehlendes Hermes-Tool darf das Plugin nicht aus dem Tritt bringen."""
    from scout.shared.registry import Registry

    class Broken:
        def dispatch_tool(self, name, args, **kwargs):
            raise RuntimeError("tool weg")

    registry = Registry()
    registry.bind_context(Broken())
    assert registry.dispatch("kaputt", {}) is None


def test_deregister_and_listing():
    from scout.shared.registry import Registry

    registry = Registry()
    registry.register("a", lambda args: None)
    registry.register("b", lambda args: None)
    assert sorted(registry.get_all_tool_names()) == ["a", "b"]
    registry.deregister("a")
    assert registry.get_all_tool_names() == ["b"]
    assert registry.get_entry("a") is None


def test_validate_reports_structural_problems():
    from scout.shared.tool_registry import ToolDef, validate

    tools = [
        ToolDef(name="BAD-NAME", domain="bughunt", schema={"parameters": {}}),
        ToolDef(name="BAD-NAME", domain="research", schema={"parameters": {}}),
        ToolDef(name="ohne_schema", domain="analysis", schema={}),
        ToolDef(name="json_ohne_modul", domain="bughunt", schema={"parameters": {}}),
        ToolDef(name="kaputte_params", domain="analysis", schema={"parameters": "nein"}),
    ]
    problems = validate(tools)

    joined = " ".join(problems)
    assert "ungueltiger Tool-Name" in joined
    assert "doppelt definiert" in joined
    assert "Schema fehlt" in joined
    assert "handler_module fehlt" in joined
    assert "parameters ist kein Objekt" in joined


def test_collect_survives_broken_domain(monkeypatch):
    """Eine defekte Domaene darf die anderen nicht mitreissen."""
    import scout.shared.tool_registry as tr

    def boom():
        raise ImportError("kaputt")

    monkeypatch.setattr(tr, "_analysis_tools", boom)
    tools = tr.collect()
    # analysis faellt aus, bughunt und research bleiben
    assert {t.domain for t in tools} == {"bughunt", "research"}


def test_json_domain_missing_file_is_skipped(tmp_path, monkeypatch):
    import scout.shared.tool_registry as tr

    monkeypatch.setitem(tr.DOMAIN_SCHEMA_FILES, "bughunt", tmp_path / "fehlt.json")
    assert tr._json_tools("bughunt") == []


def test_json_domain_accepts_wrapped_dict(tmp_path, monkeypatch):
    """Manche Quellen liefern {"tools": [...]} statt einer Liste."""
    import json

    import scout.shared.tool_registry as tr

    path = tmp_path / "wrapped.json"
    path.write_text(json.dumps({"tools": [
        {"name": "sauberes_tool", "schema": {"description": "x"}, "handler_module": "m"}
    ]}), encoding="utf-8")
    monkeypatch.setitem(tr.DOMAIN_SCHEMA_FILES, "bughunt", path)

    tools = tr._json_tools("bughunt")
    assert [t.name for t in tools] == ["sauberes_tool"]


def test_json_domain_skips_entries_without_name(tmp_path, monkeypatch):
    import json

    import scout.shared.tool_registry as tr

    path = tmp_path / "noname.json"
    path.write_text(json.dumps([{"schema": {}}, {"name": "echt", "schema": {}}]), encoding="utf-8")
    monkeypatch.setitem(tr.DOMAIN_SCHEMA_FILES, "bughunt", path)

    assert [t.name for t in tr._json_tools("bughunt")] == ["echt"]


def test_call_handler_without_introspection():
    """Builtins/C-Objekte lassen sich nicht inspizieren — Fallback greift."""
    from scout.shared.registry import call_handler

    class OhneSignatur:
        __signature__ = "kein Signature-Objekt"  # inspect.signature wirft TypeError

        def __call__(self, args):
            return args.get("x")

    assert call_handler(OhneSignatur(), {"x": 9}) == 9
