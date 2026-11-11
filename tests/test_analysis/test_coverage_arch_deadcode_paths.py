"""Coverage-Ergaenzung fuer analysis/tools/arch_deadcode.py.

Deckt die Sammel-/Fehlerpfade von analysis_architecture, analysis_deadcode,
analysis_dependency_risk und analysis_risk ab. Alle Tool-Aufrufe sind gemockt.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scout.analysis.tools import arch_deadcode as ad
from scout.analysis.tools.arch_deadcode import (
    analysis_architecture_tool,
    analysis_deadcode_tool,
    analysis_dependency_risk_tool,
    analysis_risk_tool,
)

MOD = "scout.analysis.tools.arch_deadcode"


def _fake_call_tool(mapping: dict, raise_for: set[str] | tuple[str, ...] = ()):
    def fake(name, timeout=0, **kwargs):
        if name in raise_for:
            raise RuntimeError(f"{name} nicht verfuegbar")
        # Unbekannte Tools liefern None (wie ein nicht installiertes Plugin)
        return mapping.get(name)

    return fake


def _fake_direct(mapping: dict, raise_for: set[str] | tuple[str, ...] = ()):
    def fake(name, **kwargs):
        if name in raise_for:
            raise RuntimeError(f"{name} direkt kaputt")
        return mapping.get(name)

    return fake


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "mod.py").write_text("def foo():\n    return 1\n")
    return tmp_path


# ── analysis_architecture ────────────────────────────────────────────


class TestArchitectureTool:
    def test_cycles_create_bughunt_finding(self, project: Path) -> None:
        sections = {
            "cycles": {"cycles": [[1, 2], [3, 4]]},
            "hot_paths": {"hot_paths": []},
        }
        with (
            patch(f"{MOD}._parallel_dispatch", return_value=sections),
            patch(f"{MOD}._persist_analysis"),
            patch(f"{MOD}._try_create_plan_follow_plan"),
            patch(f"{MOD}._try_create_bughunt_finding") as finding,
        ):
            data = json.loads(analysis_architecture_tool({"path": str(project)}))

        assert data["status"] == "ok"
        finding.assert_called_once()
        kwargs = finding.call_args.kwargs
        assert kwargs["severity"] == "high"
        assert "2 zirkuläre" in kwargs["title"]
        assert kwargs["details"]["cycles"] == 2

    def test_cycles_data_fallback_key(self, project: Path) -> None:
        sections = {"cycles": {"data": [[1, 2]]}}
        with (
            patch(f"{MOD}._parallel_dispatch", return_value=sections),
            patch(f"{MOD}._persist_analysis"),
            patch(f"{MOD}._try_create_plan_follow_plan"),
            patch(f"{MOD}._try_create_bughunt_finding") as finding,
        ):
            json.loads(analysis_architecture_tool({"path": str(project)}))

        finding.assert_called_once()

    def test_cycles_non_list_creates_no_finding(self, project: Path) -> None:
        sections = {"cycles": {"data": "keine liste"}}
        with (
            patch(f"{MOD}._parallel_dispatch", return_value=sections),
            patch(f"{MOD}._persist_analysis"),
            patch(f"{MOD}._try_create_plan_follow_plan"),
            patch(f"{MOD}._try_create_bughunt_finding") as finding,
        ):
            json.loads(analysis_architecture_tool({"path": str(project)}))

        finding.assert_not_called()

    def test_cycles_section_non_dict_creates_no_finding(self, project: Path) -> None:
        sections = {"cycles": [1, 2, 3]}
        with (
            patch(f"{MOD}._parallel_dispatch", return_value=sections),
            patch(f"{MOD}._persist_analysis"),
            patch(f"{MOD}._try_create_plan_follow_plan"),
            patch(f"{MOD}._try_create_bughunt_finding") as finding,
        ):
            json.loads(analysis_architecture_tool({"path": str(project)}))

        finding.assert_not_called()

    def test_persist_failure_is_logged(self, project: Path) -> None:
        with (
            patch(f"{MOD}._parallel_dispatch", return_value={}),
            patch(
                f"{MOD}._persist_analysis", side_effect=RuntimeError("kein honcho")
            ),
            patch(f"{MOD}._try_create_plan_follow_plan"),
            patch.object(ad.logger, "info") as log,
        ):
            data = json.loads(analysis_architecture_tool({"path": str(project)}))

        assert data["status"] == "ok"
        assert log.called

    def test_depth_controls_section_count(self, project: Path) -> None:
        seen: list[list[str]] = []

        def fake_dispatch(call_list, timeout=120):
            seen.append([c["key"] for c in call_list])
            return {c["key"]: {} for c in call_list}

        with (
            patch(f"{MOD}._parallel_dispatch", side_effect=fake_dispatch),
            patch(f"{MOD}._persist_analysis"),
            patch(f"{MOD}._try_create_plan_follow_plan"),
        ):
            json.loads(analysis_architecture_tool({"path": str(project), "depth": 1}))
            json.loads(analysis_architecture_tool({"path": str(project), "depth": 3}))
            json.loads(analysis_architecture_tool({"path": str(project), "depth": 99}))

        assert "cycles" not in seen[0]
        assert "cycles" in seen[1] and "unused_code" in seen[1]
        # depth wird auf 3 begrenzt
        assert seen[2] == seen[1]

    def test_missing_directory_returns_error(self, tmp_path: Path) -> None:
        data = json.loads(
            analysis_architecture_tool({"path": str(tmp_path / "gibtsnicht")})
        )
        assert data["status"] == "error"
        assert "Directory not found" in data["error"]

    def test_file_path_is_not_a_directory(self, project: Path) -> None:
        data = json.loads(
            analysis_architecture_tool({"path": str(project / "mod.py")})
        )
        assert data["status"] == "error"

    def test_invalid_path_returns_error(self) -> None:
        data = json.loads(analysis_architecture_tool({"path": "../escape"}))
        assert data["status"] == "error"


# ── analysis_deadcode ────────────────────────────────────────────────


class TestDeadcodeTool:
    def test_unused_imports_and_functions_are_summed(self, project: Path) -> None:
        direct = _fake_direct(
            {
                "code_unused_finder": {"unused": [{"name": "a"}, {"name": "b"}]},
            }
        )
        with (
            patch(f"{MOD}._call_tool_direct", side_effect=direct),
            patch(f"{MOD}._call_tool", side_effect=_fake_call_tool({})),
            patch(
                "scout.analysis.tools.base._run_shared_pattern_scans",
                return_value={},
            ),
            patch(f"{MOD}._persist_analysis"),
            patch(f"{MOD}._try_create_plan_follow_plan"),
            patch(f"{MOD}._try_create_bughunt_finding") as finding,
        ):
            data = json.loads(
                analysis_deadcode_tool(
                    {"path": str(project), "kinds": ["imports", "functions"]}
                )
            )

        assert data["summary"]["total_unused"] == 4
        assert "unused_imports" in data["findings"]
        assert "unused_functions" in data["findings"]
        finding.assert_called_once()
        assert finding.call_args.kwargs["severity"] == "medium"

    def test_unused_finder_errors_are_captured(self, project: Path) -> None:
        with (
            patch(
                f"{MOD}._call_tool_direct",
                side_effect=_fake_direct({}, raise_for={"code_unused_finder"}),
            ),
            patch(f"{MOD}._call_tool", side_effect=_fake_call_tool({})),
            patch(
                "scout.analysis.tools.base._run_shared_pattern_scans",
                return_value={},
            ),
            patch(f"{MOD}._persist_analysis"),
            patch(f"{MOD}._try_create_plan_follow_plan"),
            patch(f"{MOD}._try_create_bughunt_finding"),
        ):
            data = json.loads(
                analysis_deadcode_tool(
                    {"path": str(project), "kinds": ["imports", "functions"]}
                )
            )

        assert "direkt kaputt" in data["findings"]["unused_imports_error"]
        assert "direkt kaputt" in data["findings"]["unused_functions_error"]
        assert data["summary"]["total_unused"] == 0

    def test_orphaned_errors_are_collected(self, project: Path) -> None:
        with (
            patch(f"{MOD}._call_tool_direct", side_effect=_fake_direct({})),
            patch(
                f"{MOD}._call_tool",
                side_effect=_fake_call_tool(
                    {"code_search_by_error": {"errors": [{"file": "a.py"}]}}
                ),
            ),
            patch(
                "scout.analysis.tools.base._run_shared_pattern_scans",
                return_value={},
            ),
            patch(f"{MOD}._persist_analysis"),
            patch(f"{MOD}._try_create_plan_follow_plan"),
            patch(f"{MOD}._try_create_bughunt_finding"),
        ):
            data = json.loads(
                analysis_deadcode_tool({"path": str(project), "kinds": ["errors"]})
            )

        assert data["findings"]["orphaned_errors"] == {"errors": [{"file": "a.py"}]}

    def test_orphaned_error_scan_failure_is_captured(self, project: Path) -> None:
        with (
            patch(f"{MOD}._call_tool_direct", side_effect=_fake_direct({})),
            patch(
                f"{MOD}._call_tool",
                side_effect=_fake_call_tool({}, raise_for={"code_search_by_error"}),
            ),
            patch(
                "scout.analysis.tools.base._run_shared_pattern_scans",
                return_value={},
            ),
            patch(f"{MOD}._persist_analysis"),
            patch(f"{MOD}._try_create_plan_follow_plan"),
            patch(f"{MOD}._try_create_bughunt_finding"),
        ):
            data = json.loads(
                analysis_deadcode_tool({"path": str(project), "kinds": ["errors"]})
            )

        assert "nicht verfuegbar" in data["findings"]["orphaned_errors_error"]

    def test_shared_patterns_are_reported(self, project: Path) -> None:
        shared = {
            "pattern_matches": [{"pattern_id": "p1"}, {"pattern_id": "p2"}],
            "patterns_scanned": 12,
        }
        with (
            patch(f"{MOD}._call_tool_direct", side_effect=_fake_direct({})),
            patch(f"{MOD}._call_tool", side_effect=_fake_call_tool({})),
            patch(
                "scout.analysis.tools.base._run_shared_pattern_scans",
                return_value=shared,
            ),
            patch(f"{MOD}._persist_analysis"),
            patch(f"{MOD}._try_create_plan_follow_plan"),
            patch(f"{MOD}._try_create_bughunt_finding"),
        ):
            data = json.loads(
                analysis_deadcode_tool({"path": str(project), "kinds": ["imports"]})
            )

        assert data["findings"]["shared_patterns"] == shared["pattern_matches"]
        assert data["summary"]["shared_patterns_count"] == 2
        assert data["summary"]["patterns_scanned"] == 12

    def test_shared_pattern_failure_is_swallowed(self, project: Path) -> None:
        with (
            patch(f"{MOD}._call_tool_direct", side_effect=_fake_direct({})),
            patch(f"{MOD}._call_tool", side_effect=_fake_call_tool({})),
            patch(
                "scout.analysis.tools.base._run_shared_pattern_scans",
                side_effect=RuntimeError("keine patterns"),
            ),
            patch(f"{MOD}._persist_analysis"),
            patch(f"{MOD}._try_create_plan_follow_plan"),
            patch(f"{MOD}._try_create_bughunt_finding"),
        ):
            data = json.loads(
                analysis_deadcode_tool({"path": str(project), "kinds": ["imports"]})
            )

        assert data["status"] == "ok"
        assert "shared_patterns" not in data["findings"]

    def test_duplicates_are_collected(self, project: Path) -> None:
        with (
            patch(f"{MOD}._call_tool_direct", side_effect=_fake_direct({})),
            patch(
                f"{MOD}._call_tool",
                side_effect=_fake_call_tool({"code_duplicates": {"duplicates": [1]}}),
            ),
            patch(
                "scout.analysis.tools.base._run_shared_pattern_scans",
                return_value={},
            ),
            patch(f"{MOD}._persist_analysis"),
            patch(f"{MOD}._try_create_plan_follow_plan"),
            patch(f"{MOD}._try_create_bughunt_finding"),
        ):
            data = json.loads(
                analysis_deadcode_tool({"path": str(project), "kinds": ["all"]})
            )

        assert data["findings"]["duplicates"] == {"duplicates": [1]}

    def test_duplicate_scan_failure_is_captured(self, project: Path) -> None:
        with (
            patch(f"{MOD}._call_tool_direct", side_effect=_fake_direct({})),
            patch(
                f"{MOD}._call_tool",
                side_effect=_fake_call_tool({}, raise_for={"code_duplicates"}),
            ),
            patch(
                "scout.analysis.tools.base._run_shared_pattern_scans",
                return_value={},
            ),
            patch(f"{MOD}._persist_analysis"),
            patch(f"{MOD}._try_create_plan_follow_plan"),
            patch(f"{MOD}._try_create_bughunt_finding"),
        ):
            data = json.loads(
                analysis_deadcode_tool({"path": str(project), "kinds": ["all"]})
            )

        assert "nicht verfuegbar" in data["findings"]["duplicates_error"]

    def test_persist_failure_is_logged(self, project: Path) -> None:
        with (
            patch(f"{MOD}._call_tool_direct", side_effect=_fake_direct({})),
            patch(f"{MOD}._call_tool", side_effect=_fake_call_tool({})),
            patch(
                "scout.analysis.tools.base._run_shared_pattern_scans",
                return_value={},
            ),
            patch(f"{MOD}._persist_analysis", side_effect=RuntimeError("kein honcho")),
            patch(f"{MOD}._try_create_plan_follow_plan"),
            patch(f"{MOD}._try_create_bughunt_finding"),
            patch.object(ad.logger, "info") as log,
        ):
            data = json.loads(
                analysis_deadcode_tool({"path": str(project), "kinds": ["imports"]})
            )

        assert data["status"] == "ok"
        assert log.called

    def test_persist_false_skips_persist(self, project: Path) -> None:
        with (
            patch(f"{MOD}._call_tool_direct", side_effect=_fake_direct({})),
            patch(f"{MOD}._call_tool", side_effect=_fake_call_tool({})),
            patch(
                "scout.analysis.tools.base._run_shared_pattern_scans",
                return_value={},
            ),
            patch(f"{MOD}._persist_analysis") as persist,
            patch(f"{MOD}._try_create_plan_follow_plan"),
            patch(f"{MOD}._try_create_bughunt_finding"),
        ):
            json.loads(
                analysis_deadcode_tool(
                    {"path": str(project), "kinds": ["imports"], "persist": False}
                )
            )

        persist.assert_not_called()

    def test_limits_are_clamped(self, project: Path) -> None:
        seen: dict = {}

        def direct(name, **kwargs):
            seen.update(kwargs)
            return {}

        with (
            patch(f"{MOD}._call_tool_direct", side_effect=direct),
            patch(f"{MOD}._call_tool", side_effect=_fake_call_tool({})),
            patch(
                "scout.analysis.tools.base._run_shared_pattern_scans",
                return_value={},
            ),
            patch(f"{MOD}._persist_analysis"),
            patch(f"{MOD}._try_create_plan_follow_plan"),
            patch(f"{MOD}._try_create_bughunt_finding"),
        ):
            json.loads(
                analysis_deadcode_tool(
                    {"path": str(project), "kinds": ["imports"], "max_files": 5000, "timeout": 999}
                )
            )

        assert seen["max_files"] == 1000
        assert seen["timeout"] == 300

    def test_missing_path_returns_error(self, tmp_path: Path) -> None:
        data = json.loads(
            analysis_deadcode_tool({"path": str(tmp_path / "gibtsnicht")})
        )
        assert data["status"] == "error"
        assert "Path not found" in data["error"]

    def test_invalid_path_returns_error(self) -> None:
        assert json.loads(analysis_deadcode_tool({"path": "../x"}))["status"] == "error"


# ── analysis_dependency_risk ─────────────────────────────────────────


class TestDependencyRiskTool:
    def test_resolve_error_returns_error(self, project: Path) -> None:
        with patch(f"{MOD}._validate_and_resolve_path", return_value=("kaputt", "")):
            data = json.loads(
                analysis_dependency_risk_tool({"path": str(project)})
            )

        assert data["status"] == "error"
        assert "kaputt" in data["error"]

    def test_all_components_are_merged(self, project: Path) -> None:
        fake = _fake_call_tool(
            {
                "code_dependency_risk": {"risk_score": 3.0, "risk_level": "medium"},
                "code_complexity": {
                    "average_complexity": 4,
                    "max_complexity": 40,
                },
                "code_hot_paths": {
                    "hot_paths": [
                        {"file": "a.py", "callers": 9},
                        {"path": "b.py"},
                    ]
                },
            }
        )
        with patch(f"{MOD}._call_tool", side_effect=fake):
            data = json.loads(
                analysis_dependency_risk_tool(
                    {"path": str(project), "detail_level": "detailed"}
                )
            )

        # (3.0 + 2.0) / 2 = 2.5 -> low
        assert data["risk_score"] == 2.5
        assert data["risk_level"] == "low"
        assert data["components"]["complexity"] == {"average": 4.0, "max": 40.0, "score": 2.0}
        hot = data["components"]["hot_paths"]
        assert hot["count"] == 2
        assert hot["top"][0] == {"file": "a.py", "callers": 9}
        assert hot["top"][1] == {"file": "b.py", "callers": 0}
        assert "Risk Score: 2.5/10" in data["summary"]
        assert "complexity: 2.0/10" in data["summary"]
        assert "hot_paths: 2 Hotspots" in data["summary"]

    def test_summary_detail_strips_components(self, project: Path) -> None:
        fake = _fake_call_tool({"code_dependency_risk": {"risk_score": 7}})
        with patch(f"{MOD}._call_tool", side_effect=fake):
            data = json.loads(
                analysis_dependency_risk_tool({"path": str(project)})
            )

        assert data["risk_level"] == "high"
        # summary-Detail: nur Score/Count pro Komponente
        assert data["components"] == {"dependency_risk": 7}

    def test_risk_level_medium_threshold(self, project: Path) -> None:
        fake = _fake_call_tool(
            {
                "code_dependency_risk": {"risk_score": 2},
                "code_complexity": {"max_complexity": 100},
            }
        )
        with patch(f"{MOD}._call_tool", side_effect=fake):
            data = json.loads(analysis_dependency_risk_tool({"path": str(project)}))

        # (2 + 5) / 2 = 3.5 -> medium
        assert data["risk_score"] == 3.5
        assert data["risk_level"] == "medium"

    def test_non_dict_results_are_ignored(self, project: Path) -> None:
        fake = _fake_call_tool(
            {
                "code_dependency_risk": ["kein dict"],
                "code_complexity": "auch kein dict",
                "code_hot_paths": "keine liste",
            }
        )
        with patch(f"{MOD}._call_tool", side_effect=fake):
            data = json.loads(analysis_dependency_risk_tool({"path": str(project)}))

        assert data["risk_score"] == 0
        assert data["risk_level"] == "unknown"
        assert data["components"] == {}

    def test_component_errors_do_not_abort(self, project: Path) -> None:
        with patch(
            f"{MOD}._call_tool",
            side_effect=_fake_call_tool(
                {}, raise_for={"code_dependency_risk", "code_complexity", "code_hot_paths"}
            ),
        ):
            data = json.loads(analysis_dependency_risk_tool({"path": str(project)}))

        assert data["status"] == "ok"
        assert data["risk_score"] == 0

    def test_hot_paths_skipped_for_files(self, tmp_path: Path) -> None:
        file_path = tmp_path / "a.py"
        file_path.write_text("x = 1\n")
        seen: list[str] = []

        def fake(name, timeout=0, **kwargs):
            seen.append(name)
            return {}

        with patch(f"{MOD}._call_tool", side_effect=fake):
            json.loads(analysis_dependency_risk_tool({"path": str(file_path)}))

        assert "code_hot_paths" not in seen

    def test_hot_paths_without_entries_adds_no_component(self, project: Path) -> None:
        fake = _fake_call_tool({"code_hot_paths": {"hot_paths": []}})
        with patch(f"{MOD}._call_tool", side_effect=fake):
            data = json.loads(analysis_dependency_risk_tool({"path": str(project)}))

        assert "hot_paths" not in data["components"]

    def test_complexity_uses_avg_fallback_keys(self, project: Path) -> None:
        fake = _fake_call_tool({"code_complexity": {"avg": 2, "max": 8}})
        with patch(f"{MOD}._call_tool", side_effect=fake):
            data = json.loads(
                analysis_dependency_risk_tool(
                    {"path": str(project), "detail_level": "detailed"}
                )
            )

        assert data["components"]["complexity"] == {"average": 2.0, "max": 8.0, "score": 0.4}


# ── analysis_risk ────────────────────────────────────────────────────


class TestRiskTool:
    def test_requires_directory(self, project: Path) -> None:
        data = json.loads(analysis_risk_tool({"path": str(project / "mod.py")}))
        assert data["status"] == "error"
        assert "Not a directory" in data["error"]

    def test_invalid_path_returns_error(self) -> None:
        assert json.loads(analysis_risk_tool({"path": "../escape"}))["status"] == "error"

    def test_all_checks_are_aggregated(self, project: Path) -> None:
        fake = _fake_call_tool(
            {
                "code_dependency_risk": {"risk_score": 5, "risk_level": "medium"},
                "code_complexity": {"max_complexity": 40},
                "code_unused_finder": {"unused": [1, 2]},
                "code_security_scan": {"findings": [1, 2, 3]},
                "code_hot_paths": {"hot_paths": [1]},
                "code_duplicates": {"duplicates": ["a", "b"]},
            }
        )
        with patch(f"{MOD}._call_tool", side_effect=fake):
            data = json.loads(analysis_risk_tool({"path": str(project)}))

        # (5 + 2 + 2 + 6 + 2 + 2) / 6 = 3.166 -> 3.2 -> medium
        assert data["risk_score"] == 3.2
        assert data["risk_level"] == "medium"
        assert data["components"]["dependencies"] == {"score": 5.0, "level": "medium"}
        assert data["components"]["complexity"] == {"score": 2.0, "max": 40}
        assert data["components"]["deadcode"]["unused_count"] == 2
        assert data["components"]["security"]["findings"] == 3
        assert data["components"]["hotspots"]["count"] == 1
        assert data["components"]["duplicates"]["count"] == 2
        assert "Multi-Faktor Risk Score: 3.2/10" in data["summary"]
        assert "dependencies: 5.0/10" in data["summary"]

    def test_high_risk_level(self, project: Path) -> None:
        fake = _fake_call_tool(
            {"code_dependency_risk": {"score": 9}, "code_complexity": {"max": 200}}
        )
        with patch(f"{MOD}._call_tool", side_effect=fake):
            data = json.loads(analysis_risk_tool({"path": str(project)}))

        # (9 + 10) / 2 = 9.5 -> high
        assert data["risk_score"] == 9.5
        assert data["risk_level"] == "high"

    def test_category_filter_limits_checks(self, project: Path) -> None:
        seen: list[str] = []

        def fake(name, timeout=0, **kwargs):
            seen.append(name)
            return {"risk_score": 0}

        with patch(f"{MOD}._call_tool", side_effect=fake):
            data = json.loads(
                analysis_risk_tool({"path": str(project), "categories": ["dependencies"]})
            )

        assert seen == ["code_dependency_risk"]
        assert data["risk_level"] == "low"

    def test_failing_check_is_skipped(self, project: Path) -> None:
        with patch(
            f"{MOD}._call_tool",
            side_effect=_fake_call_tool(
                {"code_complexity": {"max_complexity": 20}},
                raise_for={"code_dependency_risk"},
            ),
        ):
            data = json.loads(
                analysis_risk_tool(
                    {"path": str(project), "categories": ["dependencies", "complexity"]}
                )
            )

        assert "dependencies" not in data["components"]
        assert data["components"]["complexity"]["score"] == 1.0
        assert data["risk_level"] == "low"

    def test_non_dict_results_are_ignored(self, project: Path) -> None:
        with patch(f"{MOD}._call_tool", side_effect=_fake_call_tool({})):
            data = json.loads(analysis_risk_tool({"path": str(project)}))

        assert data["components"] == {}
        assert data["risk_level"] == "unknown"
        assert data["summary"] == "⚠️ Multi-Faktor Risk Score: 0/10 (unknown)"

    def test_non_list_findings_are_counted_as_zero(self, project: Path) -> None:
        fake = _fake_call_tool(
            {
                "code_security_scan": {"findings": "kaputt"},
                "code_duplicates": {"duplicates": {"kein": "list"}},
                "code_hot_paths": {"hot_paths": None},
            }
        )
        with patch(f"{MOD}._call_tool", side_effect=fake):
            data = json.loads(
                analysis_risk_tool(
                    {
                        "path": str(project),
                        "categories": ["security", "duplicates", "hotspots"],
                    }
                )
            )

        assert data["components"]["security"]["score"] == 0.0
        assert data["components"]["duplicates"]["score"] == 0.0
        assert data["components"]["hotspots"]["score"] == 0.0
