"""Coverage-Ergaenzung fuer analysis/tools/inspect.py.

Fokus: Fehler- und Randpfade der einzelnen Layer von analysis_inspect_tool
sowie die Layer-Builder direkt. Alle code-intel-Aufrufe sind gemockt.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scout.analysis.tools import inspect as inspect_mod
from scout.analysis.tools.inspect import (
    _build_call_hierarchy_layer,
    _build_capsule_layer,
    _build_complexity_layer,
    _build_deadcode_layer,
    _build_dependency_risk_layer,
    _build_duplicates_layer,
    _build_summary,
    _build_timeline_layer,
    analysis_inspect_tool,
)

CALL_TOOL = "scout.analysis.tools.inspect._call_tool"


def _fake_call_tool(mapping: dict, raise_for: set[str] | tuple[str, ...] = ()):
    """_call_tool-Stub: liefert mapping[name] oder wirft fuer raise_for."""

    def fake(name, timeout=0, **kwargs):
        if name in raise_for:
            raise RuntimeError(f"{name} nicht verfuegbar")
        return mapping.get(name, {})

    return fake


def _run(args: dict) -> dict:
    """Ruft das Tool und parst die fmt_ok-JSON-Antwort."""
    return json.loads(analysis_inspect_tool(args))


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "mod.py").write_text("def foo():\n    return 1\n")
    return tmp_path


# ── Layer-Fehlerpfade im Gesamt-Tool ─────────────────────────────────


class TestInspectLayerErrors:
    def test_layer1_symbols_tool_error(self, project: Path) -> None:
        with patch(CALL_TOOL, side_effect=RuntimeError("code_symbols down")):
            data = _run({"path": str(project), "depth": 0, "persist": False})

        assert data["status"] == "ok"
        assert "code_symbols down" in data["layers"]["1_symbols"]["error"]

    def test_layer2_diagnostics_error(self, project: Path) -> None:
        with patch(CALL_TOOL, side_effect=RuntimeError("diag down")):
            data = _run({"path": str(project), "depth": 1, "persist": False})

        assert "diag down" in data["layers"]["2_diagnostics"]["error"]
        # depth 1 => keine weiteren Layer
        assert "3_overview" not in data["layers"]

    def test_layer3_overview_error(self, project: Path) -> None:
        with patch(CALL_TOOL, side_effect=RuntimeError("overview down")):
            data = _run({"path": str(project), "depth": 2, "persist": False})

        assert "overview down" in data["layers"]["3_overview"]["error"]

    def test_layer3_overview_non_dict_is_wrapped(self, project: Path) -> None:
        fake = _fake_call_tool({"code_overview": "plain text"})
        with patch(CALL_TOOL, side_effect=fake):
            data = _run({"path": str(project), "depth": 2, "persist": False})

        assert data["layers"]["3_overview"] == {"raw": "plain text"}

    def test_layer4_capsule_error(self, project: Path) -> None:
        def fake(name, timeout=0, **kwargs):
            raise RuntimeError(f"{name} down")

        with patch(CALL_TOOL, side_effect=fake):
            data = _run(
                {"path": str(project), "depth": 2, "symbol": "foo", "persist": False}
            )

        assert "code_definition down" in data["layers"]["4_capsule"]["error"]

    def test_layer5_symbol_not_found(self, project: Path) -> None:
        with (
            patch(CALL_TOOL, side_effect=_fake_call_tool({})),
            patch(
                "scout.analysis.tools.inspect._find_symbol_line", return_value=None
            ),
        ):
            data = _run(
                {"path": str(project), "depth": 3, "symbol": "ghost", "persist": False}
            )

        assert data["layers"]["5_call_hierarchy"] == {"note": "symbol not found"}

    def test_layer5_without_symbol(self, project: Path) -> None:
        with patch(CALL_TOOL, side_effect=_fake_call_tool({})):
            data = _run({"path": str(project), "depth": 3, "persist": False})

        assert data["layers"]["5_call_hierarchy"] == {
            "note": "symbol required for call hierarchy"
        }

    def test_layer5_call_hierarchy_error(self, project: Path) -> None:
        with (
            patch(CALL_TOOL, side_effect=RuntimeError("callees down")),
            patch(
                "scout.analysis.tools.inspect._find_symbol_line", return_value=3
            ),
        ):
            data = _run(
                {"path": str(project), "depth": 3, "symbol": "foo", "persist": False}
            )

        assert "callees down" in data["layers"]["5_call_hierarchy"]["error"]

    def test_layer6_deadcode_error(self, project: Path) -> None:
        with patch(CALL_TOOL, side_effect=RuntimeError("unused down")):
            data = _run({"path": str(project), "depth": 4, "persist": False})

        assert "unused down" in data["layers"]["6_deadcode"]["error"]

    def test_layer7_complexity_error(self, project: Path) -> None:
        with patch(CALL_TOOL, side_effect=RuntimeError("complexity down")):
            data = _run({"path": str(project), "depth": 5, "persist": False})

        assert "complexity down" in data["layers"]["7_complexity"]["error"]

    def test_depth5_error_layers_are_collected(self, project: Path) -> None:
        """Bei depth=5 landen Fehler aller Layer 8-10 im Report, kein Abbruch."""
        with patch(CALL_TOOL, side_effect=RuntimeError("alles down")):
            data = _run({"path": str(project), "depth": 5, "persist": False})

        assert "alles down" in data["layers"]["8_timeline"]["diff_error"]
        assert "alles down" in data["layers"]["9_duplicates"]["error"]
        assert "alles down" in data["layers"]["10_dependency_risk"]["error"]
        assert data["status"] == "ok"

    def test_missing_path_returns_error(self, tmp_path: Path) -> None:
        data = _run({"path": str(tmp_path / "gibtsnicht"), "persist": False})
        assert data["status"] == "error"

    def test_invalid_path_returns_error(self) -> None:
        data = _run({"path": "../escape", "persist": False})
        assert data["status"] == "error"
        assert "path" in data.get("error", "").lower() or data["status"] == "error"

    def test_depth_is_clamped_to_five(self, project: Path) -> None:
        with patch(CALL_TOOL, side_effect=_fake_call_tool({})):
            data = _run({"path": str(project), "depth": 99, "persist": False})

        assert data["depth"] == 5
        assert "10_dependency_risk" in data["layers"]


# ── _build_capsule_layer ─────────────────────────────────────────────


class TestCapsuleLayer:
    def test_returns_definition_and_references(self) -> None:
        fake = _fake_call_tool(
            {
                "code_definition": {"name": "foo", "line": 1},
                "code_references": {"references": [1, 2]},
            }
        )
        with patch(CALL_TOOL, side_effect=fake):
            layer = _build_capsule_layer("/tmp/x.py", "foo")

        assert layer["definition"]["name"] == "foo"
        assert layer["references_count"]["references"] == [1, 2]

    def test_error_is_captured(self) -> None:
        with patch(CALL_TOOL, side_effect=RuntimeError("capsule kaputt")):
            assert _build_capsule_layer("/tmp/x.py", "foo") == {
                "error": "capsule kaputt"
            }


# ── _build_call_hierarchy_layer ──────────────────────────────────────


class TestCallHierarchyLayer:
    def test_uses_detected_line(self) -> None:
        seen: dict = {}

        def fake(name, timeout=0, **kwargs):
            seen[name] = kwargs.get("line")
            return {"ok": name}

        with (
            patch(CALL_TOOL, side_effect=fake),
            patch("scout.analysis.tools.inspect._find_symbol_line", return_value=17),
        ):
            layer = _build_call_hierarchy_layer("/tmp/x.py", "foo")

        assert seen == {"code_callees": 17, "code_callers": 17}
        assert layer["callees"] == {"ok": "code_callees"}
        assert layer["callers"] == {"ok": "code_callers"}

    def test_symbol_not_found_note(self) -> None:
        with patch("scout.analysis.tools.inspect._find_symbol_line", return_value=0):
            assert _build_call_hierarchy_layer("/tmp/x.py", "ghost") == {
                "note": "symbol not found"
            }

    def test_symbol_required_note(self) -> None:
        assert _build_call_hierarchy_layer("/tmp/x.py", "") == {
            "note": "symbol required for call hierarchy"
        }


# ── _build_deadcode_layer / _build_complexity_layer ──────────────────


class TestDeadcodeAndComplexityLayers:
    def test_deadcode_queries_imports_and_functions(self) -> None:
        seen: list[list[str]] = []

        def fake(name, timeout=0, **kwargs):
            seen.append(kwargs.get("kinds"))
            return {"unused": kwargs.get("kinds")}

        with patch(CALL_TOOL, side_effect=fake):
            layer = _build_deadcode_layer("/tmp/x.py")

        assert seen == [["imports"], ["functions"]]
        assert layer["unused_imports"] == {"unused": ["imports"]}
        assert layer["unused_functions"] == {"unused": ["functions"]}

    def test_deadcode_error(self) -> None:
        with patch(CALL_TOOL, side_effect=RuntimeError("finder down")):
            assert _build_deadcode_layer("/tmp/x.py") == {"error": "finder down"}

    def test_complexity_requests_directory_scan(self) -> None:
        seen: dict = {}

        def fake(name, timeout=0, **kwargs):
            seen[name] = kwargs
            return {"rank": "A"}

        with patch(CALL_TOOL, side_effect=fake):
            layer = _build_complexity_layer("/tmp/proj")

        assert seen["code_complexity"]["directory"] is True
        assert layer["complexity"] == {"rank": "A"}
        assert layer["metrics"] == {"rank": "A"}

    def test_complexity_error(self) -> None:
        with patch(CALL_TOOL, side_effect=RuntimeError("complexity down")):
            assert _build_complexity_layer("/tmp/proj") == {
                "error": "complexity down"
            }


# ── _build_timeline_layer ────────────────────────────────────────────


class TestTimelineLayer:
    def test_flat_diff_keys(self) -> None:
        fake = _fake_call_tool(
            {
                "code_diff_analysis": {
                    "changed_files": 2,
                    "insertions": 10,
                    "deletions": 4,
                }
            }
        )
        with patch(CALL_TOOL, side_effect=fake):
            layer = _build_timeline_layer("/tmp/x.py")

        assert layer["recent_changes"] == {
            "files": 2,
            "insertions": 10,
            "deletions": 4,
        }

    def test_nested_summary_diff_keys(self) -> None:
        fake = _fake_call_tool(
            {
                "code_diff_analysis": {
                    "summary": {
                        "changed_files": 3,
                        "insertions": 7,
                        "deletions": 1,
                    }
                }
            }
        )
        with patch(CALL_TOOL, side_effect=fake):
            layer = _build_timeline_layer("/tmp/x.py")

        assert layer["recent_changes"] == {"files": 3, "insertions": 7, "deletions": 1}

    def test_empty_diff_yields_no_recent_changes(self) -> None:
        with patch(CALL_TOOL, side_effect=_fake_call_tool({})):
            assert _build_timeline_layer("/tmp/x.py") == {}

    def test_diff_error_is_captured(self) -> None:
        with patch(CALL_TOOL, side_effect=RuntimeError("kein git")):
            assert _build_timeline_layer("/tmp/x.py") == {"diff_error": "kein git"}

    def test_symbol_timeline_uses_matching_line(self) -> None:
        seen: dict = {}

        def fake(name, timeout=0, **kwargs):
            seen[name] = kwargs
            if name == "code_symbols":
                return {
                    "symbols": [
                        {"name": "andere", "line": 9},
                        {"name": "foo", "line": 42},
                    ]
                }
            if name == "code_timeline":
                return {"commits": 3}
            return {}

        with patch(CALL_TOOL, side_effect=fake):
            layer = _build_timeline_layer("/tmp/x.py", "foo")

        assert seen["code_timeline"]["line"] == 42
        assert seen["code_timeline"]["max_commits"] == 5
        assert layer["symbol_timeline"] == {"commits": 3}

    def test_symbol_without_match_falls_back_to_line_one(self) -> None:
        seen: dict = {}

        def fake(name, timeout=0, **kwargs):
            if name == "code_symbols":
                return {"symbols": [{"name": "andere", "line": 9}]}
            seen["line"] = kwargs.get("line")
            return {}

        with patch(CALL_TOOL, side_effect=fake):
            _build_timeline_layer("/tmp/x.py", "foo")

        assert seen["line"] == 1

    def test_symbols_as_list_is_ignored_gracefully(self) -> None:
        """Nicht-dict-Antwort von code_symbols -> Fallback line=1, kein Crash."""
        seen: dict = {}

        def fake(name, timeout=0, **kwargs):
            if name == "code_symbols":
                return [{"name": "foo", "line": 5}]
            seen["line"] = kwargs.get("line")
            return {"commits": 1}

        with patch(CALL_TOOL, side_effect=fake):
            layer = _build_timeline_layer("/tmp/x.py", "foo")

        assert seen["line"] == 1
        assert layer["symbol_timeline"] == {"commits": 1}

    def test_timeline_error_is_captured(self) -> None:
        def fake(name, timeout=0, **kwargs):
            if name == "code_symbols":
                return {"symbols": [{"name": "foo", "line": 3}]}
            raise RuntimeError("timeline kaputt")

        with patch(CALL_TOOL, side_effect=fake):
            layer = _build_timeline_layer("/tmp/x.py", "foo")

        assert layer["timeline_error"] == "timeline kaputt"


# ── _build_duplicates_layer / _build_dependency_risk_layer ───────────


class TestDuplicatesAndDependencyRisk:
    def test_duplicates_key(self) -> None:
        with patch(
            CALL_TOOL, side_effect=_fake_call_tool({"code_duplicates": {"duplicates": [1, 2]}})
        ):
            assert _build_duplicates_layer("/tmp/x.py") == {"duplicate_count": 2}

    def test_duplicates_data_fallback(self) -> None:
        with patch(
            CALL_TOOL, side_effect=_fake_call_tool({"code_duplicates": {"data": [1]}})
        ):
            assert _build_duplicates_layer("/tmp/x.py") == {"duplicate_count": 1}

    def test_duplicates_non_dict(self) -> None:
        with patch(
            CALL_TOOL, side_effect=_fake_call_tool({"code_duplicates": "kein dict"})
        ):
            assert _build_duplicates_layer("/tmp/x.py") == {"duplicate_count": 0}

    def test_duplicates_error(self) -> None:
        with patch(CALL_TOOL, side_effect=RuntimeError("dups down")):
            assert _build_duplicates_layer("/tmp/x.py") == {"error": "dups down"}

    def test_dependency_risk_standard_keys(self) -> None:
        fake = _fake_call_tool(
            {"code_dependency_risk": {"risk_score": 6.5, "risk_level": "high"}}
        )
        with patch(CALL_TOOL, side_effect=fake):
            assert _build_dependency_risk_layer("/tmp/proj") == {
                "risk_score": 6.5,
                "risk_level": "high",
            }

    def test_dependency_risk_score_fallback(self) -> None:
        with patch(
            CALL_TOOL, side_effect=_fake_call_tool({"code_dependency_risk": {"score": 2}})
        ):
            assert _build_dependency_risk_layer("/tmp/proj") == {
                "risk_score": 2,
                "risk_level": "unknown",
            }

    def test_dependency_risk_non_dict(self) -> None:
        with patch(
            CALL_TOOL, side_effect=_fake_call_tool({"code_dependency_risk": [1, 2]})
        ):
            assert _build_dependency_risk_layer("/tmp/proj") == {"risk_score": 0}

    def test_dependency_risk_error(self) -> None:
        with patch(CALL_TOOL, side_effect=RuntimeError("risk down")):
            assert _build_dependency_risk_layer("/tmp/proj") == {"error": "risk down"}


# ── _build_summary ───────────────────────────────────────────────────


class TestBuildSummary:
    def test_collects_all_layers(self) -> None:
        layers = {
            "1_symbols": {"symbols": [], "count": 4},
            "2_diagnostics": {"errors": 2, "warnings": 5},
            "8_timeline": {"recent_changes": {"files": 1}},
            "9_duplicates": {"duplicate_count": 3},
            "10_dependency_risk": {"risk_score": 7.0},
        }
        assert _build_summary(layers) == {
            "symbols": 4,
            "diagnostics": {"errors": 2, "warnings": 5},
            "recent_changes": {"files": 1},
            "duplicates": 3,
            "dependency_risk": 7.0,
        }

    def test_empty_layers(self) -> None:
        assert _build_summary({}) == {}

    def test_layer_without_expected_keys(self) -> None:
        assert _build_summary({"8_timeline": {"diff_error": "x"}, "9_duplicates": {}}) == {}

    def test_depth5_run_exposes_recent_changes_in_summary(self, project: Path) -> None:
        fake = _fake_call_tool(
            {
                "code_diff_analysis": {
                    "changed_files": 1,
                    "insertions": 2,
                    "deletions": 3,
                },
                "code_duplicates": {"duplicates": [{"a": 1}]},
                "code_dependency_risk": {"risk_score": 4.0, "risk_level": "medium"},
            }
        )
        with patch(CALL_TOOL, side_effect=fake):
            data = _run({"path": str(project), "depth": 5, "persist": False})

        assert data["summary"]["recent_changes"]["files"] == 1
        assert data["summary"]["duplicates"] == 1
        assert data["summary"]["dependency_risk"] == 4.0
        assert "Analyse von" in data["instruction"]


# ── Persistenz-Schalter ──────────────────────────────────────────────


class TestPersistence:
    def test_persist_true_calls_persist_analysis(self, project: Path) -> None:
        with (
            patch(CALL_TOOL, side_effect=_fake_call_tool({})),
            patch(
                "scout.analysis.tools.inspect._persist_analysis"
            ) as persist_mock,
        ):
            _run({"path": str(project), "depth": 1, "persist": True})

        persist_mock.assert_called_once()
        assert persist_mock.call_args[0][0] == "analysis_inspect"

    def test_persist_false_skips_persist(self, project: Path) -> None:
        with (
            patch(CALL_TOOL, side_effect=_fake_call_tool({})),
            patch(
                "scout.analysis.tools.inspect._persist_analysis"
            ) as persist_mock,
        ):
            _run({"path": str(project), "depth": 1, "persist": False})

        persist_mock.assert_not_called()

    def test_depth4_triggers_plan_follow(self, project: Path) -> None:
        with (
            patch(CALL_TOOL, side_effect=_fake_call_tool({})),
            patch(
                "scout.analysis.tools.inspect._try_create_plan_follow_plan"
            ) as plan_mock,
        ):
            _run({"path": str(project), "depth": 4, "persist": False})

        plan_mock.assert_called_once()
        assert plan_mock.call_args[0][0] == "analysis_inspect"

    def test_depth3_skips_plan_follow(self, project: Path) -> None:
        with (
            patch(CALL_TOOL, side_effect=_fake_call_tool({})),
            patch(
                "scout.analysis.tools.inspect._try_create_plan_follow_plan"
            ) as plan_mock,
        ):
            _run({"path": str(project), "depth": 3, "persist": False})

        plan_mock.assert_not_called()


def test_module_exposes_logger() -> None:
    assert inspect_mod.logger.name == "analysis"
