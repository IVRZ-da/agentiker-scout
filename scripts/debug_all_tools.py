#!/usr/bin/env python3
"""debug_all_tools.py — Ruft JEDEN Scout-Tool-Handler real auf und protokolliert das Ergebnis.

Zweck: Die Unit-Tests laufen gegen Mocks. Dieses Skript geht ueber den echten
Registrierungs-Katalog (shared.tool_registry.collect()), loest jeden Handler auf und
ruft ihn mit realistischen Argumenten auf. Damit fallen Dispatch-, Pfad-, Schema- und
Serialisierungsfehler auf, die Mocks verdecken.

Aufruf (Hermes-Interpreter):
  PY=/home/jo/.hermes/tools/python-3.14.9+20261021-linux-x64/bin/python3
  $PY /home/jo/.hermes/plugins/scout/scripts/debug_all_tools.py

Output: /tmp/scout_debug_report.json + kompakte Tabelle auf stdout.
"""
from __future__ import annotations

import importlib
import json
import os
import re
import signal
import sys
import time
import traceback

PLUGIN_PARENT = "/home/jo/.hermes/plugins"
sys.path.insert(0, PLUGIN_PARENT)

from scout.shared.tool_registry import collect  # noqa: E402

TARGET = os.environ.get("SCOUT_TARGET", "/home/jo/.hermes/plugins/scout")
URL = os.environ.get("SCOUT_URL", "http://127.0.0.1:8081/")
REPORT = "/tmp/scout_debug_report.json"
DEFAULT_TIMEOUT = int(os.environ.get("SCOUT_TIMEOUT", "180"))

# Fehlermuster in einem zurueckgegebenen String (Tools melden Fehler oft als Text)
SUSPECT = re.compile(
    r"(?i)(^❌|\btraceback\b|\binternal error\b|\bunhandled\b|unknown action|"
    r"unknown op\b|not supported|nicht unterstuetzt|nicht unterstützt|"
    r"failed to (import|load|resolve)|\bModuleNotFoundError\b|\bAttributeError\b|"
    r"\bTypeError\b|\bKeyError\b|\bValueError\b)"
)


class Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise Timeout("timeout")


signal.signal(signal.SIGALRM, _alarm)


def resolve(tool):
    h = tool.handler
    if h is not None:
        return h
    mod = importlib.import_module(tool.handler_module)
    return getattr(mod, tool.handler_name)


TOOLS = {t.name: t for t in collect()}


def call(name, args, timeout=DEFAULT_TIMEOUT, note=""):
    """Ruft einen Handler auf, protokolliert Ergebnis."""
    entry = {"tool": name, "args": args, "status": "?", "ms": 0,
             "out_len": 0, "preview": "", "error": "", "note": note}
    t0 = time.time()
    try:
        handler = resolve(TOOLS[name])
    except Exception:
        entry.update(status="resolve_error", error=traceback.format_exc(limit=3))
        entry["ms"] = int((time.time() - t0) * 1000)
        RESULTS.append(entry)
        print(f"  ✗ {name:<26} resolve_error")
        return None
    signal.alarm(timeout)
    try:
        out = handler(dict(args))
        entry["status"] = "ok" if (out is not None and str(out).strip()) else "empty"
        entry["out_len"] = len(str(out or ""))
        entry["preview"] = str(out)[:400].replace("\n", " ⏎ ")
        if entry["status"] == "ok" and SUSPECT.search(str(out)[:4000]):
            entry["status"] = "suspect"
    except Timeout:
        entry.update(status="timeout", error=f">{timeout}s")
    except Exception as e:
        entry.update(status="error", error=f"{type(e).__name__}: {e}",
                     preview=traceback.format_exc(limit=4).replace("\n", " ⏎ ")[-500:])
    finally:
        signal.alarm(0)
    entry["ms"] = int((time.time() - t0) * 1000)
    RESULTS.append(entry)
    mark = {"ok": "✓", "empty": "∅", "suspect": "⚠", "error": "✗", "timeout": "⏱"}[entry["status"]]
    print(f"  {mark} {name:<26} {entry['status']:<8} {entry['ms']:>6}ms  {entry['error'][:90]}")
    return out


RESULTS: list[dict] = []


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"Target: {TARGET}")
    print(f"Tools:  {len(TOOLS)}\n")

    if not only or only == "analysis":
        print("=== analysis ===")
        rep1 = call("analysis_inspect", {"path": TARGET, "depth": 1, "persist": False})
        rep2 = call("analysis_inspect", {"path": TARGET + "/VERSION", "depth": 1, "persist": False})
        call("analysis_architecture", {"path": TARGET, "format": "text", "depth": 1})
        call("analysis_deadcode", {"path": TARGET, "kinds": ["imports"], "max_files": 40, "persist": False})
        call("analysis_performance", {"path": TARGET, "persist": False})
        call("analysis_security", {"path": TARGET, "persist": False})
        call("analysis_ask", {"question": "Wie wird ein Tool registriert?", "path": TARGET})
        call("analysis_framework", {"path": TARGET, "fast": True})
        call("analysis_dependency_risk", {"path": TARGET})
        call("analysis_diff_analysis", {"path": TARGET, "base": "HEAD~3", "head": "HEAD", "max_files": 20})
        call("analysis_risk", {"path": TARGET})
        call("analysis_review", {"path": TARGET, "base": "HEAD~1", "head": "HEAD", "max_files": 20})
        call("analysis_test_insight", {"path": TARGET})
        call("analysis_pattern_discover", {"path": TARGET, "scan_language": "python", "min_frequency": 4})
        call("analysis_ui_gap", {"path": TARGET, "format": "text"})
        call("analysis_ui_inspect", {"url": URL})
        call("analysis_trend", {"days": 30})
        call("analysis_report", {"scope": "debug", "findings": {"a": 1}, "recommendations": ["x"]})
        if isinstance(rep1, dict) or isinstance(rep2, dict):
            call("analysis_diff", {"report_a": rep1 if isinstance(rep1, dict) else {},
                                   "report_b": rep2 if isinstance(rep2, dict) else {}})
            call("analysis_graph", {"report": rep1 if isinstance(rep1, dict) else {},
                                    "type": "summary"})
        else:
            print("  ⏭ analysis_diff/analysis_graph: keine report-dicts (inspect lieferte str)")
            for nm in ("analysis_diff", "analysis_graph"):
                RESULTS.append({"tool": nm, "args": {}, "status": "skipped",
                                "ms": 0, "out_len": 0, "preview": "", "error": "",
                                "note": "inspect lieferte kein dict"})
        call("analysis_watch", {"action": "list"})
        call("analysis_watch", {"action": "create", "path": TARGET,
                                "frequency": "daily", "name": "debugprobe", "depth": 1})
        call("analysis_watch", {"action": "remove", "name": "debugprobe", "path": TARGET})

    if not only or only == "bughunt":
        print("\n=== bughunt ===")
        start = call("bug_hunt_start", {"project": TARGET, "scope": "quick",
                                        "focus_areas": ["debug"]})
        sid = None
        if isinstance(start, dict):
            sid = start.get("session_id") or start.get("id")
        if not sid:
            m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", str(start))
            sid = m.group(0) if m else None
        print(f"    session_id={sid}")
        if not sid:
            for nm in ("bug_hunt_finding", "bug_hunt_list", "bug_hunt_scan", "bug_hunt_triage",
                       "bug_hunt_verify", "bug_hunt_report", "bug_hunt_export", "bug_hunt_stats",
                       "bug_hunt_close"):
                RESULTS.append({"tool": nm, "args": {}, "status": "skipped", "ms": 0,
                                "out_len": 0, "preview": "", "error": "",
                                "note": "keine session_id aus bug_hunt_start"})
        else:
            f = call("bug_hunt_finding", {"session_id": sid, "title": "Debug-Probe",
                                          "severity": "P3", "file": "debug.py", "line": 1,
                                          "description": "probe", "evidence": "n/a",
                                          "category": "debug"})
            fid = None
            if isinstance(f, dict):
                fid = f.get("finding_id") or f.get("id")
            if not fid:
                m = re.search(r"\bF\d+\b", str(f))
                fid = m.group(0) if m else None
            print(f"    finding_id={fid}")
            call("bug_hunt_list", {"session_id": sid})
            if fid:
                call("bug_hunt_triage", {"session_id": sid, "finding_ids": [fid],
                                         "status": "triaged", "notes": "debug"})
                call("bug_hunt_verify", {"session_id": sid, "finding_id": fid})
            call("bug_hunt_scan", {"session_id": sid, "patterns": ["sql_injection"],
                                   "path": TARGET, "auto_add_findings": False})
            call("bug_hunt_stats", {"session_id": sid})
            call("bug_hunt_report", {"session_id": sid, "format": "markdown"})
            call("bug_hunt_export", {"session_id": sid, "format": "markdown",
                                     "output": "/tmp/scout_debug_export.md"})
            call("bug_hunt_close", {"session_id": sid, "summary": "Debug-Probe beendet"})
        call("bug_hunt_history", {"limit": 3})
        call("bug_hunt_pattern", {"action": "list"})
        RESULTS.append({"tool": "bug_hunt_fix", "args": {}, "status": "skipped", "ms": 0,
                        "out_len": 0, "preview": "", "error": "",
                        "note": "spawnt Subagent — separat testen"})

    if not only or only == "research":
        print("\n=== research ===")
        st = call("research_start", {"query": "Medusa v2 Plugin Registrierung",
                                     "mode": "plan", "depth": 1, "max_sources": 3})
        rid = None
        if isinstance(st, dict):
            rid = st.get("research_id") or st.get("id")
        if not rid:
            m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", str(st))
            rid = m.group(0) if m else None
        print(f"    research_id={rid}")
        if rid:
            call("research_save", {"research_id": rid, "summary": "Debug-Zusammenfassung",
                                   "status": "partial",
                                   "findings": [{"title": "probe", "detail": "x"}],
                                   "sources": [{"url": "https://example.com", "title": "ex"}],
                                   "tags": ["debug"]})
            call("research_update", {"research_id": rid, "action": "tag",
                                     "tags": ["debug2"], "tag_action": "add"})
        else:
            for nm in ("research_save", "research_update"):
                RESULTS.append({"tool": nm, "args": {}, "status": "skipped", "ms": 0,
                                "out_len": 0, "preview": "", "error": "",
                                "note": "keine research_id aus research_start"})
        call("research_status", {})
        call("research_search", {"query": "Debug", "limit": 3})
        call("research_stats", {})
        call("research_export", {"format": "markdown"})
        call("research_synthesize", {"query": "Plugin Registrierung bei Medusa"})
        call("research_cleanup", {"action": "plans"})

    # ---- Auswertung ----
    bad = [r for r in RESULTS if r["status"] in ("error", "suspect", "timeout",
                                                 "resolve_error", "empty")]
    report = {
        "target": TARGET,
        "url": URL,
        "total_tools": len(TOOLS),
        "called": len([r for r in RESULTS if r["status"] not in ("skipped",)]),
        "skipped": len([r for r in RESULTS if r["status"] == "skipped"]),
        "failure_count": len(bad),
        "failures": bad,
        "results": RESULTS,
        "missing_tools": sorted(set(TOOLS) - {r["tool"] for r in RESULTS}),
    }
    with open(REPORT, "w") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    print(f"\n{'='*70}")
    print(f"aufgerufen: {report['called']}/{report['total_tools']}  "
          f"übersprungen: {report['skipped']}  FAILURES: {report['failure_count']}")
    if report["missing_tools"]:
        print(f"nicht getestet: {report['missing_tools']}")
    for r in bad:
        print(f"\n--- {r['tool']} [{r['status']}] {r['ms']}ms ({r['note']})")
        if r["error"]:
            print(f"    {r['error'][:600]}")
        elif r["preview"]:
            print(f"    {r['preview'][:600]}")
    print(f"\nReport: {REPORT}")


if __name__ == "__main__":
    main()
