"""Die Nutzungs-Messung schreibt eine Zeile pro Scout-Aufruf und nie eine für Fremd-Tools."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from scout.shared import usage  # noqa: E402


@pytest.fixture()
def logfile(tmp_path, monkeypatch):
    target = tmp_path / "plugin-usage.jsonl"
    monkeypatch.setenv(usage.LOG_ENV, str(target))
    return target


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_records_dispatcher_call_with_op(logfile):
    usage.on_post_tool_call(tool_name="bughunt", arguments={"op": "scan", "patterns": ["x"]},
                            session_id="s1")
    (row,) = _rows(logfile)
    assert row["plugin"] == "scout"
    assert row["tool"] == "bughunt"
    assert row["op"] == "scan"
    assert row["session_id"] == "s1"
    assert row["error"] is False
    assert row["ts"].endswith("+00:00")


def test_accepts_json_string_arguments(logfile):
    usage.on_post_tool_call(tool_name="analysis", arguments='{"op": "deadcode", "path": "."}')
    assert _rows(logfile)[0]["op"] == "deadcode"


def test_counts_legacy_tool_names(logfile):
    usage.on_post_tool_call(tool_name="analysis_deadcode")
    usage.on_post_tool_call(tool_name="bug_hunt_scan")
    assert [r["tool"] for r in _rows(logfile)] == ["analysis_deadcode", "bug_hunt_scan"]


def test_ignores_foreign_tools(logfile):
    for name in ("read_file", "terminal", "code_search", "plan_create"):
        usage.on_post_tool_call(tool_name=name, arguments={"op": "x"})
    assert not logfile.exists() or _rows(logfile) == []


def test_never_raises_on_bad_payload(logfile):
    usage.on_post_tool_call(tool_name="analysis", arguments="{kein json")
    usage.on_post_tool_call()  # ohne tool_name
    (row,) = _rows(logfile)
    assert row["op"] is None
