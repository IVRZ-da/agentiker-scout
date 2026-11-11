"""Contract tests for the golden-task eval harness itself.

These do not run the tasks (that is scripts/run_evals.py); they guarantee that
the task catalogue stays truthful:

* every task is well formed,
* all three domains are covered,
* every referenced tool actually exists in plugin.yaml (no phantom tools),
* placeholders only reference captures that an earlier step sets,
* the harness is isolated (no writes into the plugin's data dirs).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml

PLUGIN_DIR = Path(__file__).resolve().parents[2]
GOLDEN = PLUGIN_DIR / "tests" / "evals" / "golden_tasks.json"
MANIFEST = PLUGIN_DIR / "plugin.yaml"
HARNESS = PLUGIN_DIR / "scripts" / "run_evals.py"

MIN_TASKS = 12
DOMAINS = {"bughunt", "research", "analysis"}
TIERS = {"local", "requires_code_intel", "requires_firecrawl"}


@pytest.fixture(scope="module")
def spec() -> dict:
    assert GOLDEN.exists(), f"golden_tasks.json fehlt: {GOLDEN}"
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def provided_tools() -> set[str]:
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    return set(manifest.get("provides_tools") or [])


@pytest.fixture(scope="module")
def harness():
    """Das Harness-Modul OHNE ``isolate_data_dirs()`` aufzurufen.

    ``exec_module`` importiert nur die Standardbibliothek; erst
    ``isolate_data_dirs()`` zieht die scout-Module und friert damit globalen
    Pattern-Zustand ein. Deshalb wird hier nur das Modul geladen, die
    Isolation separat im Subprozess geprueft.
    """
    assert HARNESS.exists(), "scripts/run_evals.py fehlt"
    s = importlib.util.spec_from_file_location("scout_run_evals_helpers", HARNESS)
    assert s and s.loader
    module = importlib.util.module_from_spec(s)
    s.loader.exec_module(module)
    return module


def test_enough_tasks(spec: dict) -> None:
    tasks = spec.get("tasks", [])
    assert len(tasks) >= MIN_TASKS, f"nur {len(tasks)} Tasks, mindestens {MIN_TASKS} erwartet"


def test_all_domains_covered(spec: dict) -> None:
    domains = {t.get("domain") for t in spec["tasks"]}
    missing = DOMAINS - domains
    assert not missing, f"Domains ohne Golden-Task: {sorted(missing)}"


def test_task_ids_unique(spec: dict) -> None:
    ids = [t["id"] for t in spec["tasks"]]
    dupes = {i for i in ids if ids.count(i) > 1}
    assert not dupes, f"doppelte Task-IDs: {sorted(dupes)}"


def test_every_task_has_steps_and_tier(spec: dict) -> None:
    for task in spec["tasks"]:
        assert task.get("tier") in TIERS, f"{task['id']}: ungueltiger tier {task.get('tier')!r}"
        steps = task.get("steps")
        assert steps, f"{task['id']}: keine steps"
        for step in steps:
            assert isinstance(step.get("tool"), str) and step["tool"], (
                f"{task['id']}: step ohne tool"
            )
            assert isinstance(step.get("args", {}), dict), (
                f"{task['id']}/{step['tool']}: args muss ein Objekt sein"
            )


def test_referenced_tools_are_provided(spec: dict, provided_tools: set[str]) -> None:
    """Kein Golden-Task darf ein Tool aufrufen, das das Manifest nicht anbietet."""
    phantom: list[str] = []
    for task in spec["tasks"]:
        for step in task["steps"]:
            if step["tool"] not in provided_tools:
                phantom.append(f"{task['id']} -> {step['tool']}")
    assert not phantom, f"Tools nicht im Manifest: {phantom}"


def test_placeholders_have_capture_source(spec: dict) -> None:
    """Jedes $var muss von einem frueheren Schritt per capture gesetzt werden."""
    problems: list[str] = []
    for task in spec["tasks"]:
        available: set[str] = set()

        def walk(value, tid: str) -> None:
            if isinstance(value, str) and value.startswith("$"):
                var = value[1:]
                if var not in available:
                    problems.append(f"{tid}: ${var} ohne vorheriges capture")
            elif isinstance(value, list):
                for v in value:
                    walk(v, tid)
            elif isinstance(value, dict):
                for v in value.values():
                    walk(v, tid)

        for step in task["steps"]:
            walk(step.get("args", {}), task["id"])
            if step.get("capture"):
                available.add(step["capture"])
    assert not problems, problems


def test_local_tier_tasks_exist(spec: dict) -> None:
    """Mindestens 10 Tasks muessen ohne externe Abhaengigkeit laufen."""
    local = [t for t in spec["tasks"] if t.get("tier") == "local"]
    assert len(local) >= 10, f"nur {len(local)} lokale Tasks"


# ---------------------------------------------------------------------------
# Harness-Helfer (reine Logik, ohne scout-Import)
# ---------------------------------------------------------------------------


def test_subst_replaces_placeholder(harness) -> None:
    assert harness._subst("$sid", {"sid": "abc"}) == "abc"


def test_subst_keeps_plain_strings(harness) -> None:
    assert harness._subst("plain", {}) == "plain"


def test_subst_walks_lists(harness) -> None:
    assert harness._subst(["$a", "x", "$b"], {"a": "1", "b": "2"}) == ["1", "x", "2"]


def test_subst_walks_nested_dicts(harness) -> None:
    result = harness._subst({"ids": ["$a"], "meta": {"id": "$b"}}, {"a": "1", "b": "2"})
    assert result == {"ids": ["1"], "meta": {"id": "2"}}


def test_subst_missing_placeholder_raises(harness) -> None:
    with pytest.raises(KeyError, match="nope"):
        harness._subst("$nope", {})


def test_parse_response_json(harness) -> None:
    assert harness._parse_response('{"status": "ok"}') == {"status": "ok"}


def test_parse_response_plain_text_wrapped(harness) -> None:
    payload = harness._parse_response("kein json")
    assert payload["status"] == "ok"
    assert payload["raw"] == "kein json"


def test_parse_response_passes_dicts_through(harness) -> None:
    assert harness._parse_response({"status": "x"}) == {"status": "x"}


def test_first_id_prefers_session_id(harness) -> None:
    payload = {"research_id": "r", "session_id": "s", "id": "i"}
    assert harness._first_id(payload) == "s"


def test_first_id_finds_nested(harness) -> None:
    assert harness._first_id({"outer": {"research_id": "r1"}}) == "r1"


def test_first_id_returns_none_when_absent(harness) -> None:
    assert harness._first_id({"message": "nix"}) is None


# ---------------------------------------------------------------------------
# run_task: Fehlerpfade und Capture-Kette (ohne scout-Import)
# ---------------------------------------------------------------------------


def _fake_handlers(responses: dict[str, object]) -> dict:
    """Baut eine Handler-Map aus {tool: response | Exception}."""

    def make(value):
        def handler(args):
            if isinstance(value, Exception):
                raise value
            return value

        return handler

    return {name: make(value) for name, value in responses.items()}


def test_run_task_passes_and_captures(harness) -> None:
    handlers = _fake_handlers(
        {
            "t_start": '{"status": "open", "session_id": "s-1"}',
            "t_list": '{"status": "ok", "items": []}',
        }
    )
    task = {
        "id": "t",
        "domain": "bughunt",
        "tier": "local",
        "steps": [
            {"tool": "t_start", "args": {"p": 1}, "capture": "sid"},
            {"tool": "t_list", "args": {"session_id": "$sid"}},
        ],
    }
    result = harness.run_task(task, handlers)
    assert result["status"] == "passed"
    assert result["attempts"] == 1
    assert [s["tool"] for s in result["steps"]] == ["t_start", "t_list"]
    assert result["steps"][0]["captured"] == "sid"


def test_run_task_accepts_domain_status(harness) -> None:
    """Domänenstatus wie 'open' oder 'planned' ist kein Fehler."""
    handlers = _fake_handlers({"t": '{"status": "planned"}'})
    task = {"id": "t", "steps": [{"tool": "t", "args": {}}]}
    assert harness.run_task(task, handlers)["status"] == "passed"


def test_run_task_fails_on_unknown_tool(harness) -> None:
    task = {"id": "t", "steps": [{"tool": "gibt_es_nicht", "args": {}}]}
    result = harness.run_task(task, {})
    assert result["status"] == "failed"
    assert "nicht registriert" in result["error"]


def test_run_task_fails_on_error_status(harness) -> None:
    handlers = _fake_handlers({"t": '{"status": "error", "message": "kaputt"}'})
    task = {"id": "t", "steps": [{"tool": "t", "args": {}}]}
    result = harness.run_task(task, handlers)
    assert result["status"] == "failed"
    assert "kaputt" in result["error"]


def test_run_task_fails_when_handler_raises(harness) -> None:
    handlers = _fake_handlers({"t": ValueError("boom")})
    task = {"id": "t", "steps": [{"tool": "t", "args": {}}]}
    result = harness.run_task(task, handlers)
    assert result["status"] == "failed"
    assert "ValueError" in result["error"]


def test_run_task_fails_when_capture_missing(harness) -> None:
    handlers = _fake_handlers({"t": '{"status": "ok", "message": "keine id"}'})
    task = {"id": "t", "steps": [{"tool": "t", "args": {}, "capture": "sid"}]}
    result = harness.run_task(task, handlers)
    assert result["status"] == "failed"
    assert "sid" in result["error"]


def test_run_task_stops_at_first_failure(harness) -> None:
    handlers = _fake_handlers({"a": "{}", "b": '{"status": "error"}'})
    task = {
        "id": "t",
        "steps": [{"tool": "a", "args": {}}, {"tool": "b", "args": {}}, {"tool": "a", "args": {}}],
    }
    result = harness.run_task(task, handlers)
    assert result["status"] == "failed"
    assert len(result["steps"]) == 2  # dritter Schritt wurde nicht mehr versucht


def test_harness_is_isolated() -> None:
    """run_evals muss Datenpfade umbiegen koennen, ohne das Plugin-Dir zu beruehren.

    Laeuft in einem SUBPROZESS: ``run_evals`` importiert die scout-Module, und
    ein Import im Testprozess friert modul-globalen Zustand (Pattern-Registry)
    ein, bevor andere Tests ihn aufbauen — das kippte 6 reihenfolgeabhaengige
    Pattern-Tests. Ein Subprozess prueft dasselbe ohne diesen Nebeneffekt.
    """
    import subprocess
    import sys

    harness = PLUGIN_DIR / "scripts" / "run_evals.py"
    assert harness.exists(), "scripts/run_evals.py fehlt"

    probe = (
        "import importlib.util, sys, tempfile\n"
        "from pathlib import Path\n"
        f"harness = Path({str(harness)!r})\n"
        "spec = importlib.util.spec_from_file_location('_h', harness)\n"
        "m = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(m)\n"
        "m._bootstrap_import_path()\n"
        "tmp = Path(tempfile.mkdtemp())\n"
        "moved = m.isolate_data_dirs(tmp)\n"
        "assert moved, 'isolate_data_dirs hat keine Pfade umgebogen'\n"
        "bad = {k: v for k, v in moved.items() if not v.startswith(str(tmp))}\n"
        "assert not bad, bad\n"
        "leaked = [k for k in moved if k.endswith('.SESSIONS_DIR')]\n"
        "assert leaked, 'kein SESSIONS_DIR umgebogen'\n"
        "print('OK', len(moved))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(PLUGIN_DIR),
    )
    assert result.returncode == 0, f"Probe fehlgeschlagen:\n{result.stdout}\n{result.stderr}"
    assert "OK" in result.stdout
