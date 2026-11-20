"""bug_hunt_export schreibt nur unter das Export-Verzeichnis (Review #157391 Punkt 2).

Vorher kam der Pfad vom Modell und wurde ohne Grenze angelegt — inklusive
Shell-RCs und Hermes-Config. Wer woanders speichern will, bekommt den Inhalt
in der Antwort und nimmt `write_file`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scout.bughunt.tools.session import bug_hunt_export, bug_hunt_start
from scout.shared import paths as _paths


@pytest.fixture
def session_id() -> str:
    payload = json.loads(bug_hunt_start({"project": "demo", "scope": "quick"}))
    assert "session_id" in payload, payload
    return payload["session_id"]


def _export(session_id: str, **kwargs) -> dict:
    return json.loads(bug_hunt_export({"session_id": session_id, **kwargs}))


def test_relative_output_lands_in_exports_dir(session_id):
    result = _export(session_id, output="report.json")
    assert result.get("output_path"), result
    written = Path(result["output_path"])
    assert written.parent == _paths.EXPORTS_DIR.resolve()
    assert written.exists()


def test_nested_relative_output_is_allowed(session_id):
    result = _export(session_id, output="2026/11/report.json")
    assert result.get("output_path"), result
    assert _paths.EXPORTS_DIR.resolve() in Path(result["output_path"]).parents


def test_absolute_path_outside_is_refused(session_id, tmp_path):
    target = tmp_path / "evil.json"
    result = _export(session_id, output=str(target))
    assert "error" in result, result
    assert "liegen" in result["error"] or "write_file" in result["error"]
    assert not target.exists()


@pytest.mark.parametrize("bad", ["../escape.json", "../../etc/passwd", "sub/../../escape.json"])
def test_traversal_is_refused(session_id, bad):
    result = _export(session_id, output=bad)
    if "error" in result:
        assert not (Path(_paths.DATA_ROOT) / "escape.json").exists()
    else:  # aufgeloest innerhalb des Exports-Verzeichnisses ist ok
        assert _paths.EXPORTS_DIR.resolve() in Path(result["output_path"]).parents


def test_shell_rc_path_is_refused(session_id):
    result = _export(session_id, output="~/.bashrc")
    assert "error" in result, result


def test_without_output_content_is_returned(session_id):
    result = _export(session_id)
    assert "content" in result
    assert "output_path" not in result
