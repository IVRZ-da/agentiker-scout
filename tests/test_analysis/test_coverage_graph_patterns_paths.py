"""Coverage-Ergaenzung fuer analysis/tools/graph_patterns.py.

Fokus: Pattern-Discovery (Python/TS/Go) mit gemocktem subprocess, Framework-
Erkennung, Confidence-Scoring und Auto-Save der Kandidaten. Es laeuft kein
echter grep und kein Schreibzugriff auf das Pattern-Repository.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scout.analysis.tools import graph_patterns as gp
from scout.analysis.tools.graph_patterns import (
    _discover_go_patterns,
    _discover_python_patterns,
    _discover_ts_patterns,
    analysis_pattern_discover_tool,
)


class _Result:
    """Minimaler subprocess.CompletedProcess-Ersatz."""

    def __init__(self, returncode: int = 0, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout


def _hits(n: int) -> _Result:
    return _Result(0, "".join(f"file{i}.py:{i}: match\n" for i in range(n)))


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "mod.py").write_text("x = 1\n")
    return tmp_path


# ── _discover_* mit gemocktem grep ───────────────────────────────────


class TestDiscoverHelpers:
    def test_python_mutable_defaults_are_found(self, project: Path) -> None:
        candidates: list = []
        with patch("subprocess.run", return_value=_hits(4)):
            _discover_python_patterns(project, candidates, set(), 1)

        names = [c["suggested_name"] for c in candidates]
        assert names == ["Silent Catch (Python)", "Mutable Default Arguments"]
        mutable = candidates[1]
        assert mutable["frequency"] == 4
        assert mutable["scan_language"] == "python"
        assert mutable["scan_file_glob"] == "**/*.py"
        assert mutable["suggested_fix"]

    def test_python_below_min_frequency_adds_nothing(self, project: Path) -> None:
        candidates: list = []
        with patch("subprocess.run", return_value=_hits(2)):
            _discover_python_patterns(project, candidates, set(), 3)

        assert candidates == []

    def test_python_nonzero_returncode_adds_nothing(self, project: Path) -> None:
        candidates: list = []
        with patch("subprocess.run", return_value=_Result(1, "")):
            _discover_python_patterns(project, candidates, set(), 1)

        assert candidates == []

    def test_python_grep_failure_is_logged(self, project: Path) -> None:
        candidates: list = []
        with (
            patch("subprocess.run", side_effect=OSError("grep fehlt")),
            patch.object(gp.logger, "debug") as log,
        ):
            _discover_python_patterns(project, candidates, set(), 1)

        assert candidates == []
        assert log.call_count == 2

    def test_ts_all_three_patterns(self, project: Path) -> None:
        candidates: list = []
        with patch("subprocess.run", return_value=_hits(6)) as run:
            _discover_ts_patterns(project, candidates, set(), 1)

        assert run.call_count == 3
        assert [c["suggested_name"] for c in candidates] == [
            "Console Log",
            "TypeScript 'any' statt 'unknown'",
            "force-dynamic Export",
        ]
        assert candidates[1]["scan_language"] == "typescript"

    def test_ts_grep_failure_is_logged(self, project: Path) -> None:
        candidates: list = []
        with (
            patch("subprocess.run", side_effect=OSError("grep fehlt")),
            patch.object(gp.logger, "debug") as log,
        ):
            _discover_ts_patterns(project, candidates, set(), 1)

        assert candidates == []
        assert log.call_count == 3

    def test_go_error_handling_pattern(self, project: Path) -> None:
        candidates: list = []
        with patch("subprocess.run", return_value=_hits(3)) as run:
            _discover_go_patterns(project, candidates, set(), 1)

        assert run.call_count == 1
        assert candidates[0]["suggested_name"] == "Error ohne Handling"
        assert candidates[0]["scan_language"] == "go"
        assert candidates[0]["frequency"] == 3

    def test_go_grep_failure_is_logged(self, project: Path) -> None:
        candidates: list = []
        with (
            patch("subprocess.run", side_effect=OSError("grep fehlt")),
            patch.object(gp.logger, "debug") as log,
        ):
            _discover_go_patterns(project, candidates, set(), 1)

        assert candidates == []
        assert log.called


# ── analysis_pattern_discover_tool ───────────────────────────────────


class TestPatternDiscoverTool:
    def test_framework_detection_failure_is_logged(self, project: Path) -> None:
        with (
            patch(
                "scout.shared.framework_detector.FrameworkDetector",
                side_effect=RuntimeError("detector kaputt"),
            ),
            patch("subprocess.run", return_value=_Result(1, "")),
            patch(
                "scout.shared.patterns.get_patterns_for_analysis", return_value=[]
            ),
            patch.object(gp.logger, "debug") as log,
        ):
            data = json.loads(
                analysis_pattern_discover_tool({"path": str(project)})
            )

        assert data["status"] == "ok"
        assert "frameworks" not in data
        assert any("framework detection failed" in str(c) for c in log.call_args_list)

    def test_detected_frameworks_are_reported(self, project: Path) -> None:
        fw = type("FW", (), {"name": "fastapi"})()
        profile = type("Profile", (), {"frameworks": {"backend": [fw]}})()

        with (
            patch(
                "scout.shared.framework_detector.FrameworkDetector",
                return_value=type("D", (), {"detect_fast": lambda self: profile})(),
            ),
            patch("subprocess.run", return_value=_Result(1, "")),
            patch(
                "scout.shared.patterns.get_patterns_for_frameworks", return_value=[]
            ) as fw_patterns,
            patch("scout.shared.patterns.get_patterns_for_analysis", return_value=[]),
        ):
            data = json.loads(
                analysis_pattern_discover_tool({"path": str(project)})
            )

        assert data["frameworks"] == {"backend": ["fastapi"]}
        fw_patterns.assert_called_once()
        assert fw_patterns.call_args[0][1] == "python"

    def test_high_confidence_candidates_are_auto_saved(self, project: Path) -> None:
        with (
            patch("subprocess.run", return_value=_hits(12)),
            patch(
                "scout.shared.patterns.get_patterns_for_analysis", return_value=[]
            ),
            patch(
                "scout.shared.patterns.save_pattern", return_value="p_new"
            ) as save,
        ):
            data = json.loads(
                analysis_pattern_discover_tool(
                    {"path": str(project), "frameworks": ["python"]}
                )
            )

        assert data["status"] == "ok"
        assert data["summary"]["gaps_found"] == 2
        assert data["summary"]["patterns_found"] == 2
        assert data["summary"]["auto_saved"] == 2
        assert save.call_count == 2

        payload = save.call_args[0][0]
        assert payload["auto_analysis"] is True
        assert payload["source_plugin"] == "analysis"
        assert payload["scan_query"]
        assert payload["analysis_kinds"]

        # Confidence: 0.5 + 0.3 (freq>10) + 0.1 (desc) + 0.1 (fix) = 1.0
        assert data["candidates"][0]["confidence"] == 1.0

    def test_mid_confidence_candidate_is_not_saved(self, project: Path) -> None:
        """Frequenz 3 -> 0.5+0(doc/fix fehlen nicht) bleibt unter der Schwelle."""
        with (
            patch("subprocess.run", return_value=_hits(3)),
            patch(
                "scout.shared.patterns.get_patterns_for_analysis", return_value=[]
            ),
            patch("scout.shared.patterns.save_pattern") as save,
        ):
            data = json.loads(
                analysis_pattern_discover_tool(
                    {"path": str(project), "frameworks": ["go"]}
                )
            )

        # 0.5 + 0.1 (desc) + 0.1 (fix) = 0.7 -> gespeichert (einziger Kandidat)
        assert data["candidates"][0]["confidence"] == 0.7
        assert save.call_count == 1

    def test_save_failure_is_swallowed(self, project: Path) -> None:
        with (
            patch("subprocess.run", return_value=_hits(12)),
            patch(
                "scout.shared.patterns.get_patterns_for_analysis", return_value=[]
            ),
            patch(
                "scout.shared.patterns.save_pattern",
                side_effect=RuntimeError("repo readonly"),
            ),
            patch.object(gp.logger, "debug") as log,
        ):
            data = json.loads(
                analysis_pattern_discover_tool(
                    {"path": str(project), "frameworks": ["python"]}
                )
            )

        assert data["status"] == "ok"
        assert data["summary"]["auto_saved"] == 0
        assert data["summary"]["patterns_found"] == 2
        assert any("auto-save failed" in str(c) for c in log.call_args_list)

    def test_scan_language_limits_discovery(self, project: Path) -> None:
        with (
            patch("subprocess.run", return_value=_Result(1, "")) as run,
            patch(
                "scout.shared.patterns.get_patterns_for_analysis", return_value=[]
            ),
        ):
            json.loads(
                analysis_pattern_discover_tool(
                    {"path": str(project), "scan_language": "go"}
                )
            )

        assert run.call_count == 1

    def test_patterns_without_query_are_ignored_for_dedup(self, project: Path) -> None:
        existing = [{"name": "ohne query"}]
        with (
            patch("subprocess.run", return_value=_Result(1, "")) as run,
            patch(
                "scout.shared.patterns.get_patterns_for_analysis",
                return_value=existing,
            ),
        ):
            json.loads(
                analysis_pattern_discover_tool(
                    {"path": str(project), "scan_language": "python"}
                )
            )

        assert run.call_count == 2

    def test_min_frequency_is_forwarded(self, project: Path) -> None:
        with (
            patch("subprocess.run", return_value=_hits(2)) as run,
            patch(
                "scout.shared.patterns.get_patterns_for_analysis", return_value=[]
            ),
        ):
            data = json.loads(
                analysis_pattern_discover_tool(
                    {
                        "path": str(project),
                        "scan_language": "python",
                        "min_frequency": 5,
                    }
                )
            )

        assert run.call_count == 2
        assert data["summary"]["gaps_found"] == 0

    def test_top_ten_limit(self, project: Path) -> None:
        many = [
            {
                "suggested_name": f"p{i}",
                "category": "code-quality",
                "frequency": 1,
                "description": "",
                "suggested_fix": "",
            }
            for i in range(15)
        ]

        def fake_python(path, candidates, existing, min_freq):
            candidates.extend(many)

        with (
            patch(
                "scout.analysis.tools.graph_patterns._discover_python_patterns",
                side_effect=fake_python,
            ),
            patch(
                "scout.shared.patterns.get_patterns_for_analysis", return_value=[]
            ),
            patch("scout.shared.patterns.save_pattern"),
        ):
            data = json.loads(
                analysis_pattern_discover_tool(
                    {"path": str(project), "frameworks": ["python"]}
                )
            )

        assert len(data["candidates"]) == 10
        assert data["summary"]["gaps_found"] == 15
        assert data["summary"]["patterns_found"] == 0

    def test_missing_path_returns_error(self) -> None:
        data = json.loads(analysis_pattern_discover_tool({"path": ""}))
        assert data["status"] == "error"
