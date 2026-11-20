"""grep-Scans übergeben das Muster als ``-e <pattern>`` (Review #157391, Empfehlung).

Ohne ``-e`` liest grep ein Muster, das mit ``-`` beginnt, als Option — ein
gespeichertes Pattern wie ``--include=*`` hätte den Scan verbogen.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path
from unittest.mock import patch

from scout.bughunt import bughunt_scanrunner


def test_pattern_is_passed_with_dash_e(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    with patch.object(subprocess, "run") as run:
        run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
        bughunt_scanrunner.run_grep_scan("TODO", "*.py", str(tmp_path))

    cmd = run.call_args[0][0]
    assert "-e" in cmd, cmd
    assert cmd[cmd.index("-e") + 1] == "TODO"
    # Pfad kommt nach "--", damit er nicht als Option gilt
    assert cmd[-2:] == ["--", str(tmp_path)] or (cmd[-1] == str(tmp_path) and "--" in cmd)


def test_pattern_starting_with_dash_is_not_an_option(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    dangerous = "--include=/etc/passwd"
    with patch.object(subprocess, "run") as run:
        run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
        bughunt_scanrunner.run_grep_scan(dangerous, "*.py", str(tmp_path))

    cmd = run.call_args[0][0]
    assert cmd[cmd.index("-e") + 1] == dangerous
    assert cmd.index("-e") < cmd.index(dangerous)


def test_pyproject_bounds_match_manifest():
    root = Path(__file__).resolve().parent.parent
    deps = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    spec = " ".join(deps["project"]["dependencies"])
    assert "PyYAML>=6.0,<7" in spec
    assert "packaging>=23.0,<27" in spec

    manifest = (root / "plugin.yaml").read_text(encoding="utf-8")
    assert "PyYAML>=6.0,<7" in manifest
    assert "packaging>=23.0,<27" in manifest
