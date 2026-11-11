#!/usr/bin/env python3
"""Golden-Task evaluation harness for the scout plugin.

Measures whether the plugin's own tool contracts still work: can every golden
workflow be executed end-to-end through the *real* handlers, with the *
real* registry wiring, without errors?

This is deliberately deterministic. It does not call an LLM. It answers one
question that no unit test answers: "does the tool surface a user actually
touches still work as a whole?"

Usage:
    python3 scripts/run_evals.py                          # run, human summary
    python3 scripts/run_evals.py --json                   # machine-readable
    python3 scripts/run_evals.py --baseline --out base.json
    python3 scripts/run_evals.py --tier local             # skip code_intel tasks
    python3 scripts/run_evals.py --only rs-lifecycle
    python3 scripts/run_evals.py --verbose

Exit code: 0 = every task passed or was legitimately skipped, 1 = failure.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PLUGIN_DIR = Path(__file__).resolve().parent.parent
GOLDEN_TASKS = PLUGIN_DIR / "tests" / "evals" / "golden_tasks.json"

HandlerMap = dict[str, Callable[[dict], Any]]

# Pfade kommen seit P1 aus scout.shared.paths (Nutzdaten ausserhalb des Repos).
# Umschaltung fuer Tests/Evals laeuft ueber SCOUT_DATA_DIR, nicht ueber
# Modul-Patching — siehe isolate_data_dirs().


# ---------------------------------------------------------------------------
# Plugin import (works both inside Hermes and standalone)
# ---------------------------------------------------------------------------


def _bootstrap_import_path() -> None:
    plugins_root = str(PLUGIN_DIR.parent)
    for p in (str(PLUGIN_DIR), plugins_root):
        if p not in sys.path:
            sys.path.insert(0, p)


def plugin_version() -> str:
    try:
        return (PLUGIN_DIR / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


# ---------------------------------------------------------------------------
# Isolation: never touch real plugin data
# ---------------------------------------------------------------------------


def isolate_data_dirs(root: Path) -> dict[str, str]:
    """Alle Nutzdatenpfade auf ``root`` umbiegen.

    Seit Nutzdaten in ``~/.hermes/data/scout`` liegen (shared/paths.py), gibt es
    genau eine Quelle. Die Umschaltung passiert deshalb ueber die dokumentierte
    Env-Variable ``SCOUT_DATA_DIR`` — kein Pfad-Patching quer durch die Module.
    Module, die die Konstanten per ``from x import y`` kopiert haben, werden
    anschliessend nachgezogen.

    Returns a mapping of "module.ATTR" -> new path, so the caller can report
    what was moved (and so the effect is auditable rather than magic).
    """
    from scout.shared import paths as paths_mod

    root = Path(root).resolve()
    os.environ[paths_mod.ENV_DATA_DIR] = str(root)
    fresh = paths_mod.reload_paths()
    moved: dict[str, str] = {}

    # Module, die die Konstanten kopiert haben (from scout.shared.paths import ...)
    for modname, mod in list(sys.modules.items()):
        if mod is None or not modname.startswith("scout"):
            continue
        if modname == paths_mod.__name__:
            continue
        for attr, new_path in fresh.items():
            if hasattr(mod, attr):
                setattr(mod, attr, new_path)
                moved[f"{modname}.{attr}"] = str(new_path)

    # Verzeichnisse im neuen Wurzelverzeichnis anlegen
    paths_mod.ensure_dirs()

    for attr, new_path in fresh.items():
        moved[f"scout.shared.paths.{attr}"] = str(new_path)
    return moved


# ---------------------------------------------------------------------------
# Handler resolution — use the same wiring Hermes uses
# ---------------------------------------------------------------------------


def build_handler_map() -> tuple[HandlerMap, list[str]]:
    """Resolve tool name -> callable from the plugin's own registries."""
    handlers: HandlerMap = {}
    problems: list[str] = []

    # analysis: Python TOOL_HANDLERS (schema, handler) tuples
    try:
        from scout.analysis.analysis_tools import TOOL_HANDLERS  # type: ignore[import-not-found]

        for name, entry in TOOL_HANDLERS.items():
            handler = entry[1] if isinstance(entry, (tuple, list)) else entry
            if callable(handler):
                handlers[name] = handler
    except Exception as exc:  # pragma: no cover - reported, not raised
        problems.append(f"analysis: TOOL_HANDLERS nicht ladbar: {exc}")

    # bughunt + research: scout_tool_registry.json
    registry_file = PLUGIN_DIR / "scout_tool_registry.json"
    try:
        registry = json.loads(registry_file.read_text(encoding="utf-8"))
    except Exception as exc:
        problems.append(f"registry: {registry_file.name} nicht ladbar: {exc}")
        registry = {}

    for _domain, tools in registry.items():
        for tool in tools:
            name = tool.get("name")
            modname = tool.get("handler_module")
            fname = tool.get("handler_name")
            if not (name and modname and fname):
                continue
            try:
                mod = importlib.import_module(modname)
                handler = getattr(mod, fname)
            except Exception as exc:
                problems.append(f"{name}: Handler {modname}.{fname} nicht ladbar: {exc}")
                continue
            if callable(handler):
                handlers[name] = handler

    return handlers, problems


# ---------------------------------------------------------------------------
# Task execution
# ---------------------------------------------------------------------------


def _subst(value, variables: dict[str, str]):
    """Replace "$name" placeholders (also inside lists) with captured values."""
    if isinstance(value, str):
        if value.startswith("$"):
            key = value[1:]
            if key not in variables:
                raise KeyError(f"Platzhalter ${key} wurde von keinem Schritt gesetzt")
            return variables[key]
        return value
    if isinstance(value, list):
        return [_subst(v, variables) for v in value]
    if isinstance(value, dict):
        return {k: _subst(v, variables) for k, v in value.items()}
    return value


def _parse_response(raw):
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"status": "ok", "raw": raw}
    if isinstance(raw, dict):
        return raw
    return {"status": "ok", "raw": raw}


def run_task(task: dict, handlers: HandlerMap) -> dict:
    variables: dict[str, str] = {}
    steps_out: list[dict] = []
    started = time.perf_counter()

    for step in task.get("steps", []):
        tool = step["tool"]
        t0 = time.perf_counter()
        record = {"tool": tool, "status": "ok", "ms": 0}
        try:
            handler = handlers.get(tool)
            if handler is None:
                raise LookupError(f"Tool '{tool}' ist nicht registriert/aufloesbar")
            args = _subst(step.get("args", {}), variables)
            payload = _parse_response(handler(args))
            # Fehler NUR am expliziten Response-Status erkennen. Viele Handler
            # nutzen "status" als Domaenenfeld ("open" bei Sessions, "planned"
            # bei Recherchen) — das ist kein Fehler.
            status = str(payload.get("status", "ok"))
            if status == "error" or payload.get("error"):
                raise RuntimeError(
                    f"{tool} meldete einen Fehler: {payload.get('message') or payload.get('error')}"
                )
            capture = step.get("capture")
            if capture:
                value = _first_id(payload)
                if not value:
                    raise RuntimeError(f"{tool} hat '{capture}' nicht geliefert")
                variables[capture] = value
                record["captured"] = capture
            record["status"] = status
        except Exception as exc:
            record["status"] = "error"
            record["error"] = f"{type(exc).__name__}: {exc}"
            record["ms"] = round((time.perf_counter() - t0) * 1000, 2)
            steps_out.append(record)
            return {
                "id": task["id"],
                "domain": task.get("domain", ""),
                "tier": task.get("tier", "local"),
                "status": "failed",
                "attempts": 0,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "steps": steps_out,
                "error": record["error"],
                "traceback": traceback.format_exc(limit=3) if os.environ.get("EVAL_DEBUG") else "",
            }
        record["ms"] = round((time.perf_counter() - t0) * 1000, 2)
        steps_out.append(record)

    return {
        "id": task["id"],
        "domain": task.get("domain", ""),
        "tier": task.get("tier", "local"),
        "status": "passed",
        "attempts": 1,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "steps": steps_out,
    }


def _first_id(payload: dict) -> str | None:
    for key in ("session_id", "finding_id", "research_id", "id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    # manche Handler nesten die ID
    for value in payload.values():
        if isinstance(value, dict):
            found = _first_id(value)
            if found:
                return found
    return None


# ---------------------------------------------------------------------------
# Dependency probes
# ---------------------------------------------------------------------------


def code_intel_available(handlers: HandlerMap) -> bool:
    probe = handlers.get("code_symbols")
    if probe is None:
        return False
    try:
        result = _parse_response(probe({"path": str(PLUGIN_DIR / "VERSION")}))
        return str(result.get("status", "")) != "error"
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="Scout golden-task evaluation")
    ap.add_argument("--baseline", action="store_true", help="Als Baseline markieren")
    ap.add_argument("--out", help="Ergebnis als JSON in diese Datei schreiben")
    ap.add_argument("--json", action="store_true", help="Nur JSON nach stdout")
    ap.add_argument(
        "--tier",
        choices=["all", "local"],
        default="all",
        help="local = nur Tasks ohne externe Abhaengigkeit",
    )
    ap.add_argument("--only", help="Nur diese Task-ID ausfuehren")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument(
        "--keep-data", action="store_true", help="Temporaeres Datenverzeichnis behalten (Debug)"
    )
    args = ap.parse_args()

    _bootstrap_import_path()

    if not GOLDEN_TASKS.exists():
        print(f"FEHLER: {GOLDEN_TASKS} fehlt", file=sys.stderr)
        return 1

    spec = json.loads(GOLDEN_TASKS.read_text(encoding="utf-8"))
    tasks = spec.get("tasks", [])
    if args.only:
        tasks = [t for t in tasks if t["id"] == args.only]
        if not tasks:
            print(f"FEHLER: Task '{args.only}' nicht gefunden", file=sys.stderr)
            return 1
    if args.tier == "local":
        tasks = [t for t in tasks if t.get("tier", "local") == "local"]

    tmpdir = Path(tempfile.mkdtemp(prefix="scout-eval-"))
    moved = isolate_data_dirs(tmpdir)

    handlers, problems = build_handler_map()
    ci_ok = code_intel_available(handlers)

    results: list[dict] = []
    for task in tasks:
        tier = task.get("tier", "local")
        if tier == "requires_code_intel" and not ci_ok:
            results.append(
                {
                    "id": task["id"],
                    "domain": task.get("domain", ""),
                    "tier": tier,
                    "status": "skipped",
                    "attempts": 0,
                    "duration_ms": 0,
                    "steps": [],
                    "skip_reason": "code_intel nicht erreichbar",
                }
            )
            continue
        if tier == "requires_firecrawl" and "firecrawl_search" not in handlers:
            results.append(
                {
                    "id": task["id"],
                    "domain": task.get("domain", ""),
                    "tier": tier,
                    "status": "skipped",
                    "attempts": 0,
                    "duration_ms": 0,
                    "steps": [],
                    "skip_reason": "firecrawl nicht erreichbar",
                }
            )
            continue
        results.append(run_task(task, handlers))

    if not args.keep_data:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)

    passed = sum(1 for r in results if r["status"] == "passed")
    failed = sum(1 for r in results if r["status"] == "failed")
    skipped = sum(1 for r in results if r["status"] == "skipped")

    report = {
        "kind": "scout-golden-eval",
        "baseline": bool(args.baseline),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plugin_version": plugin_version(),
        "code_intel_available": ci_ok,
        "isolation_targets": len(moved),
        "registry_problems": problems,
        "totals": {
            "tasks": len(results),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "duration_ms": round(sum(r.get("duration_ms", 0) for r in results), 2),
            "tool_calls": sum(len(r.get("steps", [])) for r in results),
        },
        "tasks": results,
    }

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        t = report["totals"]
        label = "BASELINE" if args.baseline else "EVAL"
        print(f"scout {label} — Version {report['plugin_version']}")
        print(
            f"  tasks    : {t['tasks']} (passed {t['passed']}, failed {t['failed']}, skipped {t['skipped']})"
        )
        print(f"  calls    : {t['tool_calls']}")
        print(f"  duration : {t['duration_ms'] / 1000:.2f} s")
        print(f"  code_intel: {'yes' if ci_ok else 'no'}")
        if problems:
            print("  registry problems:")
            for p in problems:
                print(f"    - {p}")
        print()
        for r in results:
            icon = {"passed": "PASS", "failed": "FAIL", "skipped": "SKIP"}[r["status"]]
            line = f"  [{icon}] {r['id']:26} {r['domain']:9} {r['duration_ms']:8.1f} ms"
            if r["status"] == "skipped":
                line += f"  ({r.get('skip_reason', '')})"
            print(line)
            if r["status"] == "failed":
                print(f"         -> {r.get('error', '')}")
                if args.verbose:
                    for s in r.get("steps", []):
                        print(f"         step {s['tool']}: {s['status']} {s.get('error', '')}")
        if args.out:
            print(f"\n  JSON: {args.out}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
