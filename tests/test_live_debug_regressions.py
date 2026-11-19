"""Regressionstests fuer die Bugs aus dem Live-Debug aller Scout-Tools.

Jeder Test nennt den beobachteten Fehler, nicht nur die Funktion — die Bugs
kamen alle als "✅ success mit leeren Feldern" zurueck und waren deshalb in der
normalen Suite unsichtbar.
"""

from __future__ import annotations

import json


# ── analysis_watch: action=list/remove braucht keinen Pfad ──────────────
def test_watch_list_without_path():
    from scout.analysis.tools.diff_trend_watch import analysis_watch_tool

    data = json.loads(analysis_watch_tool({"action": "list"}))
    assert data.get("status") != "error", data
    assert data["action"] == "list"


def test_watch_remove_without_path():
    from scout.analysis.tools.diff_trend_watch import analysis_watch_tool

    data = json.loads(analysis_watch_tool({"action": "remove", "name": "x"}))
    assert data.get("status") != "error", data
    assert data["action"] == "remove"


def test_watch_create_still_requires_path():
    from scout.analysis.tools.diff_trend_watch import analysis_watch_tool

    data = json.loads(analysis_watch_tool({"action": "create"}))
    assert data.get("status") == "error"


# ── _summarize_symbols: Verzeichnis-Scans liefern results[] ─────────────
def test_summarize_symbols_directory_shape():
    from scout.analysis.tools.base import _summarize_symbols

    directory_payload = {
        "path": "/tmp/x",
        "file_count": 2,
        "total_symbols": 3,
        "results": [
            {"path": "/tmp/x/a.py", "symbols": [{"name": "a", "kind": "function", "line": 1}]},
            {"path": "/tmp/x/b.py", "symbols": [{"name": "b", "kind": "class", "line": 5},
                                               {"name": "c", "kind": "function", "line": 9}]},
        ],
    }
    summarised = _summarize_symbols(directory_payload)
    assert [s["name"] for s in summarised] == ["a", "b", "c"]
    assert summarised[0]["file"] == "/tmp/x/a.py"


def test_summarize_symbols_flat_and_dict_shapes():
    from scout.analysis.tools.base import _summarize_symbols

    assert _summarize_symbols([{"name": "x", "kind": "function", "line": 3}])[0]["name"] == "x"
    assert _summarize_symbols({"symbols": [{"name": "y"}]})[0]["name"] == "y"
    assert _summarize_symbols("panel-text") == []


# ── graph_patterns: q2 war im except-Block definiert ────────────────────
def test_pattern_discovery_has_no_unbound_local(tmp_path):
    """Der Aufruf lief live in 'cannot access local variable q2'."""
    (tmp_path / "a.py").write_text("def f(x=[]):\n    return x\n" * 3)
    from scout.analysis.tools.graph_patterns import _discover_python_patterns

    candidates: list = []
    _discover_python_patterns(str(tmp_path), candidates, set(), 1)
    assert isinstance(candidates, list)


# ── research_save: title/detail wurden zu leeren Findings ───────────────
def test_research_findings_accept_title_and_detail():
    from scout.research.tools.crud import _normalize_findings

    normalized = _normalize_findings([
        {"title": "Titel", "detail": "Detail"},       # so schickt es ein Modell
        {"finding": "explizit", "sources": ["https://a"]},
        "nur ein String",
    ])
    assert normalized[0]["finding"] == "Titel"
    assert normalized[1]["finding"] == "explizit"
    assert normalized[1]["sources"] == ["https://a"]
    assert normalized[2]["finding"] == "nur ein String"


# ── bug_hunt_pattern list: 69 KB Vollform war unbenutzbar ───────────────
def test_pattern_list_is_compact_by_default(monkeypatch):
    from scout.bughunt import bughunt_core as core_mod
    from scout.bughunt.tools.patterns import bug_hunt_pattern

    core_mod.init_patterns()
    raw = bug_hunt_pattern({"action": "list"})
    compact = json.loads(raw)
    assert compact["count"] >= 20
    assert set(compact["patterns"][0]) == {"pattern_id", "name", "category",
                                           "severity", "description"}
    assert len(raw) < 20_000, f"Liste zu gross: {len(raw)} Zeichen"

    full = json.loads(bug_hunt_pattern({"action": "list", "full": True}))
    assert "scan_query" in full["patterns"][0]
    assert len(json.dumps(full)) > len(raw)


# ── Dispatcher: op aus kwargs ───────────────────────────────────────────
def test_dispatcher_accepts_op_as_keyword():
    import importlib

    from scout import namespaces
    from scout.shared.tool_registry import collect

    def resolve(tool):
        if tool.handler:
            return tool.handler
        return getattr(importlib.import_module(tool.handler_module), tool.handler_name)

    catalog: dict[str, list] = {}
    for tool in collect():
        catalog.setdefault(tool.domain, []).append(tool)
    specs = namespaces.build_tool_specs(catalog, resolve)
    bughunt = next(s for s in specs if s["name"] == "bughunt")

    positional = json.loads(bughunt["handler"]({"op": "history", "limit": 1}))
    keyword = json.loads(bughunt["handler"](None, op="history", limit=1))
    assert positional["count"] == keyword["count"], (positional, keyword)
