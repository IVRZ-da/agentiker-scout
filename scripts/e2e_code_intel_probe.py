#!/usr/bin/env python3
"""e2e_code_intel_probe.py — Beweist, dass die Scout-Analysis-Tools nach dem
Alias-Fix echte code_intel-Ergebnisse bekommen.

Stellt den Hermes-Host nach:
  * code_intel registriert seine 7 Namespace-Dispatcher (echte Handler),
  * die alten Einzelnamen (``code_symbols`` …) existieren nicht,
  * Scout haengt am Host und ruft seine Analysis-Handler auf.

Ohne Fix: ``Unknown tool: code_symbols`` → 0 Symbole, 0 Findings.
Mit Fix:  echte Symbol-/Finding-Zahlen.

Aufruf:
  PY=/home/jo/.hermes/tools/python-3.14.9+20261021-linux-x64/bin/python3
  $PY scripts/e2e_code_intel_probe.py [zielpfad]
"""
from __future__ import annotations

import json
import sys
import time
import traceback

sys.path.insert(0, "/home/jo/.hermes/plugins")

TARGET = sys.argv[1] if len(sys.argv) > 1 else "/home/jo/.hermes/plugins/scout/shared"


# ── 1. code_intel als Host aufbauen ─────────────────────────────────
def build_code_intel_host():
    from code_intel import namespaces as ci_ns

    class Collector:
        def __init__(self):
            self.tools = {}

        def register_tool(self, name, toolset=None, schema=None, handler=None,
                          description="", **_kw):
            self.tools[name] = {"schema": schema, "handler": handler,
                                "description": description}

    col = Collector()
    try:
        from code_intel.__init__ import _register_ast_tools
    except Exception:
        from code_intel import _register_ast_tools  # type: ignore
    try:
        from code_intel.lsp_bridge import register_lsp_tools
    except Exception as exc:
        print(f"  (LSP-Tools nicht ladbar: {exc})")
        register_lsp_tools = lambda _t: None  # noqa: E731

    catalog = ci_ns.build_catalog(_register_ast_tools, register_lsp_tools)
    specs = ci_ns.build_tool_specs(catalog)
    for spec in specs:
        col.register_tool(spec["name"], spec["name"], spec["schema"], spec["handler"],
                          spec.get("description", ""))
    return col.tools


# ── 2. Host-Adapter wie Hermes ──────────────────────────────────────
class HostAdapter:
    def __init__(self, tools):
        self.tools = tools
        self.calls = []

    def dispatch_tool(self, name, args, **kwargs):
        self.calls.append(name)
        entry = self.tools.get(name)
        if entry is None:
            return json.dumps({"error": f"Unknown tool: {name}"})
        try:
            return entry["handler"](dict(args or {}), **kwargs)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": f"{type(exc).__name__}: {exc}"})


class HostRegistryView:
    """Was ``hermes_has_tool`` sieht: nur registrierte Namen."""

    def __init__(self, tools):
        self._names = set(tools)

    def get_entry(self, name, **_kw):
        return {"name": name} if name in self._names else None


def main():
    print(f"Ziel: {TARGET}\n")
    tools = build_code_intel_host()
    print(f"code_intel-Tools beim Host: {len(tools)} → {sorted(tools)}")

    from scout.shared import registry as reg_mod

    host = HostAdapter(tools)
    reg_mod.hermes_registry = lambda: HostRegistryView(tools)  # type: ignore[assignment]
    reg_mod.registry.bind_context(host)

    from scout.analysis.tools.arch_deadcode import (
        analysis_architecture_tool,
        analysis_deadcode_tool,
    )
    from scout.analysis.tools.inspect import analysis_inspect_tool
    from scout.analysis.tools.perf_sec import analysis_performance_tool, analysis_security_tool

    cases = [
        ("analysis_inspect", analysis_inspect_tool, {"path": TARGET, "depth": 1, "persist": False}),
        ("analysis_deadcode", analysis_deadcode_tool,
         {"path": TARGET, "kinds": ["imports"], "persist": False, "max_files": 50}),
        ("analysis_security", analysis_security_tool, {"path": TARGET, "persist": False}),
        ("analysis_architecture", analysis_architecture_tool,
         {"path": TARGET, "format": "text", "depth": 1}),
        ("analysis_performance", analysis_performance_tool, {"path": TARGET, "persist": False}),
    ]

    failures = 0
    for name, fn, args in cases:
        t0 = time.time()
        try:
            raw = fn(dict(args))
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            print(f"  ✗ {name}: {traceback.format_exc(limit=2)}")
            failures += 1
            continue
        ms = int((time.time() - t0) * 1000)
        verdict = check(name, data)
        if verdict is None:
            print(f"  ✓ {name:<24} {ms:>6}ms  {summarize(name, data)}")
        else:
            print(f"  ✗ {name:<24} {ms:>6}ms  {verdict}")
            failures += 1

    print(f"\nHost-Dispatches: {sorted(set(host.calls))}")
    print(f"Fehler: {failures}")
    return 1 if failures else 0


def check(name, data):
    """None = gut, sonst Fehlertext."""
    if not isinstance(data, dict):
        return f"kein dict: {type(data)}"
    text = json.dumps(data, ensure_ascii=False)
    if "Unknown tool" in text:
        return "Unknown tool im Ergebnis — Alias griff nicht"
    if name == "analysis_inspect":
        n = (data.get("summary") or {}).get("symbols", 0)
        return None if n else "0 Symbole — code_intel lieferte nichts"
    if name == "analysis_deadcode":
        findings = data.get("findings") or {}
        if isinstance(findings, dict) and "_error" in json.dumps(findings):
            return "Fehler im findings-Block"
        blocks = findings.get("unused_imports") if isinstance(findings, dict) else None
        if isinstance(blocks, dict) and blocks.get("error"):
            return blocks["error"]
        return None
    if name == "analysis_security":
        summary = data.get("summary") or {}
        if not summary:
            return "kein summary"
        return None
    return None


def summarize(name, data):
    if name == "analysis_inspect":
        s = data.get("summary") or {}
        layers = data.get("layers") or {}
        return f"symbols={s.get('symbols')} diagnostics={(s.get('diagnostics') or {}).get('total')} layers={len(layers)}"
    if name == "analysis_deadcode":
        f = data.get("findings") or {}
        return f"finding-blocks={list(f)[:4]}"
    if name == "analysis_security":
        return f"summary={data.get('summary')}"
    if name == "analysis_architecture":
        secs = data.get("sections") or {}
        filled = [k for k, v in secs.items() if v]
        return f"sections={len(filled)}/{len(secs)} gefüllt"
    if name == "analysis_performance":
        secs = data.get("sections") or {}
        filled = [k for k, v in secs.items() if v]
        return f"sections={len(filled)}/{len(secs)} gefüllt"
    return "ok"


if __name__ == "__main__":
    sys.exit(main())
