"""response_format: concise verdichtet messbar, detailed bleibt vollstaendig.

Der Test prueft die Verdichtung selbst UND die Wirkung am echten Handler —
sonst waere ``response_format`` nur ein Versprechen im Schema.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR.parent) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR.parent))

from scout._fmt import condense, condense_json, wants_concise  # noqa: E402

# ---------------------------------------------------------------------------
# condense
# ---------------------------------------------------------------------------


def test_short_values_untouched():
    assert condense("kurz") == "kurz"
    assert condense(42) == 42
    assert condense(True) is True
    assert condense(None) is None


def test_long_string_is_cut():
    out = condense("x" * 500)
    assert len(out) == 240
    assert out.endswith("\u2026")


def test_long_list_is_cut_and_counted():
    out = condense({"items": list(range(12))})
    assert out["items"] == [0, 1, 2, 3, 4]
    assert out["items_truncated"] == 7


def test_short_list_kept_whole():
    out = condense({"items": [1, 2]})
    assert out["items"] == [1, 2]
    assert "items_truncated" not in out


def test_aggregates_survive():
    """count/total muessen stimmen, sonst luegt die concise-Ausgabe."""
    out = condense({"count": 99, "items": list(range(20))})
    assert out["count"] == 99
    assert len(out["items"]) == 5


def test_nested_structures_condensed():
    payload = {"a": {"b": [{"deep": "y" * 400}]}}
    out = condense(payload)
    assert len(out["a"]["b"][0]["deep"]) == 240


# ---------------------------------------------------------------------------
# condense_json
# ---------------------------------------------------------------------------


def test_condense_json_on_json_payload():
    payload = json.dumps({"items": list(range(10)), "count": 10})
    out = json.loads(condense_json(payload))
    assert len(out["items"]) == 5
    assert out["count"] == 10


def test_condense_json_leaves_markdown_alone():
    md = "# Report\n\n" + "Zeile\n" * 200
    assert condense_json(md) == md


def test_condense_json_on_plain_text_alone():
    assert condense_json("kein json") == "kein json"


def test_condense_json_survives_broken_json():
    broken = '{"a": '
    assert condense_json(broken) == broken


# ---------------------------------------------------------------------------
# wants_concise
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "args,expected",
    [
        ({"response_format": "concise"}, True),
        ({"response_format": "CONCISE"}, True),
        ({"response_format": "detailed"}, False),
        ({}, False),
        (None, False),
    ],
)
def test_wants_concise(args, expected):
    assert wants_concise(args) is expected


# ---------------------------------------------------------------------------
# Wirkung am echten Handler
# ---------------------------------------------------------------------------


def test_bug_hunt_list_concise_is_smaller():
    """Der registrierte Wrapper liefert mit concise weniger Bytes als detailed."""
    from scout import _wrap_response_format
    from scout.bughunt.tools.base import _get_core
    from scout.bughunt.tools.session import bug_hunt_finding, bug_hunt_list

    core = _get_core()
    session = core.BugHuntSession(project="fixture/concise", scope="quick")
    core.save_session(session)

    for i in range(12):
        bug_hunt_finding(
            {
                "session_id": session.session_id,
                "title": f"Finding Nummer {i} mit einem laengeren Titel",
                "severity": "P2",
                "file": f"/src/file_{i}.py",
                "line": i,
                "description": "Beschreibung " * 20,
            }
        )

    # Schema wie im Registry: nur mit response_format greift der Wrapper
    schema = json.loads((PLUGIN_DIR / "scout_tool_registry.json").read_text(encoding="utf-8"))
    list_schema = next(e["schema"] for e in schema["bughunt"] if e["name"] == "bug_hunt_list")
    wrapped = _wrap_response_format(bug_hunt_list, list_schema)

    detailed = wrapped({"session_id": session.session_id, "response_format": "detailed"})
    concise = wrapped({"session_id": session.session_id, "response_format": "concise"})

    assert len(concise) < len(detailed), (len(concise), len(detailed))

    d_payload = json.loads(detailed)
    c_payload = json.loads(concise)
    # Aggregate bleiben gleich, nur die Liste ist gekuerzt
    assert c_payload.get("count") == d_payload.get("count")
    assert len(c_payload.get("findings", [])) <= 5
    assert c_payload.get("findings_truncated") == len(d_payload["findings"]) - 5
