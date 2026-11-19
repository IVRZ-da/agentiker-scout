"""Regression: zentrale Alias-Aufloesung im Registry-Dispatch.

Hintergrund: code_intel hat seine 70 Einzeltools auf 7 Namespace-Dispatcher
gefaltet. Scout rief an vielen Stellen weiter ``code_symbols`` & Co. auf; der
Alias-Layer existierte, wurde aber nur an zwei Stellen benutzt und sein
Verfuegbarkeits-Praedikat fragte die *lokale* Registry — dort ist ein
Host-Tool nie zu finden. Ergebnis: ``Unknown tool: code_symbols``, von den
Analysis-Tools still als leeres Ergebnis ausgegeben.

Diese Tests stellen den Hermes-Host nach (kennt nur die Namespaces) und
pruefen, dass der Dispatch dennoch beim richtigen Tool landet.
"""

from __future__ import annotations

import json

import pytest

from scout.shared import registry as reg_mod
from scout.shared.registry import Registry


class FakeHost:
    """Minimaler Hermes-Ersatz: kennt eine feste Menge Toolnamen."""

    def __init__(self, known: set[str]) -> None:
        self.known = known
        self.calls: list[tuple[str, dict]] = []

    # -- PluginContext-Aequivalent ------------------------------------
    def dispatch_tool(self, name: str, args: dict, **kwargs) -> str:
        self.calls.append((name, dict(args)))
        if name not in self.known:
            return json.dumps({"error": f"Unknown tool: {name}"})
        if name.startswith("code_"):
            return json.dumps({"status": "ok", "tool": name, "op": args.get("op"),
                               "args": {k: v for k, v in args.items() if k != "op"}})
        return json.dumps({"status": "ok", "tool": name})


class FakeHermesRegistry:
    def __init__(self, known: set[str]) -> None:
        self.known = known

    def get_entry(self, name: str, **_kwargs):
        return {"name": name} if name in self.known else None


NAMESPACES = {"code_search", "code_lsp", "code_graph", "code_edit",
              "code_review", "code_git", "code_meta"}
LEGACY = {"code_symbols", "code_security_scan", "code_unused_finder",
          "code_complexity", "code_hot_paths", "code_diagnostics"}


@pytest.fixture()
def host_only_namespaces(monkeypatch):
    """Host mit aktivierten Namespaces: Einzelnamen existieren nicht."""
    host = FakeHost(set(NAMESPACES))
    hermes = FakeHermesRegistry(set(NAMESPACES))
    monkeypatch.setattr(reg_mod, "hermes_registry", lambda: hermes)
    r = Registry()
    r.bind_context(host)
    return r, host


@pytest.fixture()
def host_both(monkeypatch):
    """Host mit ``CODE_INTEL_NAMESPACES=0``: Einzelnamen UND Namespaces da."""
    known = set(NAMESPACES) | LEGACY
    host = FakeHost(known)
    hermes = FakeHermesRegistry(known)
    monkeypatch.setattr(reg_mod, "hermes_registry", lambda: hermes)
    r = Registry()
    r.bind_context(host)
    return r, host


def test_legacy_name_is_rewritten_to_namespace(host_only_namespaces):
    r, host = host_only_namespaces
    result = json.loads(r.dispatch("code_symbols", {"path": "/tmp/x.py"}))
    assert result["tool"] == "code_search"
    assert result["op"] == "symbols"
    assert result["args"] == {"path": "/tmp/x.py"}
    assert [c[0] for c in host.calls] == ["code_search"], "kein Fehlversuch vorab"


def test_every_legacy_alias_resolves(host_only_namespaces):
    """Jeder Eintrag der Tabelle muss auf einen existierenden Namespace zeigen."""
    from scout.shared.tool_alias import TOOL_ALIASES

    r, host = host_only_namespaces
    for legacy, (group, op) in TOOL_ALIASES.items():
        host.calls.clear()
        result = r.dispatch(legacy, {"path": "/tmp/x.py"})
        assert "Unknown tool" not in result, legacy
        assert host.calls[0][0] == group, legacy
        assert host.calls[0][1]["op"] == op, legacy


def test_single_tool_mode_stays_untouched(host_both):
    """Existiert der Einzelname noch, darf nicht umgeschrieben werden."""
    r, host = host_both
    r.dispatch("code_symbols", {"path": "/tmp/x.py"})
    assert host.calls == [("code_symbols", {"path": "/tmp/x.py"})]


def test_existing_op_argument_is_respected(host_only_namespaces):
    """Nennt der Aufrufer schon eine andere Operation, nicht ueberschreiben."""
    r, host = host_only_namespaces
    r.dispatch("code_symbols", {"op": "overview", "path": "/tmp/x.py"})
    assert host.calls[0] == ("code_symbols", {"op": "overview", "path": "/tmp/x.py"})


def test_unknown_tool_without_alias_stays_visible(host_only_namespaces):
    """Kein Alias vorhanden -> Fehler bleibt sichtbar, wird nicht verschluckt."""
    r, _host = host_only_namespaces
    result = r.dispatch("voellig_unbekannt", {})
    assert "Unknown tool" in result


def test_fallback_when_host_lookup_is_unavailable(monkeypatch):
    """Ohne erreichbare Host-Registry greift der Fallback nach 'Unknown tool'."""
    host = FakeHost(set(NAMESPACES))  # kennt nur die Namespaces
    monkeypatch.setattr(reg_mod, "hermes_registry", lambda: None)  # Lookup blind
    r = Registry()
    r.bind_context(host)
    result = json.loads(r.dispatch("code_unused_finder", {"path": "/tmp"}))
    assert result["tool"] == "code_review"
    assert result["op"] == "unused_finder"


def test_local_handler_wins_over_alias():
    """Lokal registrierte Handler haben Vorrang (kein Host-Dispatch)."""
    r = Registry()
    r.register("code_symbols", handler=lambda args, **kw: "lokal")
    assert r.dispatch("code_symbols", {}) == "lokal"
