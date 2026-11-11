"""Coverage-Ergänzung für scout/analysis/tools/ui_gap.py.

Fokus: plan_follow-Integration (alle Rückgabe-/Fehlerformen), leere Projekte,
nicht-listige `_gaps` und der Exception-Pfad des Tool-Handlers.

`discover_uis`/`build_coverage_matrix` werden im Tool-Handler gepatcht, damit
kein echtes Projekt-Layout nötig ist.
"""

from __future__ import annotations

import json
import types

import pytest

from scout.analysis.tools import ui_gap
from scout.shared.registry import registry

# ---------------------------------------------------------------------------
# Helfer
# ---------------------------------------------------------------------------


def _gap(gap_type: str, module: str = "product") -> dict:
    return {"type": gap_type, "module": module, "detail": f"{module} Lücke"}


def _entry(handler=None, *, callable_handler=True):
    if not callable_handler:
        return types.SimpleNamespace(handler="kein-callable")
    return types.SimpleNamespace(handler=handler)


@pytest.fixture
def plan_registry(monkeypatch):
    """Erlaubt das Setzen eines plan_create-Entries."""

    def _install(entry):
        monkeypatch.setattr(registry, "get_entry", lambda name: entry if name == "plan_create" else None)

    return _install


# ---------------------------------------------------------------------------
# _try_generate_plan_from_gaps
# ---------------------------------------------------------------------------


class TestPlanFromGaps:
    def test_no_plan_create_entry_returns_none(self, plan_registry):
        plan_registry(None)

        assert ui_gap._try_generate_plan_from_gaps("/tmp/proj", [_gap("🔴")]) is None

    def test_non_callable_handler_returns_none(self, plan_registry):
        plan_registry(_entry(callable_handler=False))

        assert ui_gap._try_generate_plan_from_gaps("/tmp/proj", [_gap("🔴")]) is None

    def test_dict_result_is_returned_and_all_severities_become_tasks(self, plan_registry):
        calls = []

        def handler(payload):
            calls.append(payload)
            return {"status": "ok", "plan": "ui-gaps"}

        plan_registry(_entry(handler))

        gaps = [
            _gap("🔴", "product"),
            _gap("🔴", "order"),
            _gap("🟡", "customer"),
            _gap("🔵", "seo"),
            _gap("🟢", "invoice"),
        ]
        result = ui_gap._try_generate_plan_from_gaps("/tmp/proj", gaps)

        assert result == {"status": "ok", "plan": "ui-gaps"}
        assert "UI-Gaps beheben (5 Lücken in proj)" in calls[0]["goal"]
        names = [task["name"] for task in calls[0]["tasks"]]
        assert any("🔴 product" in name for name in names)
        assert any("🟡 customer" in name for name in names)
        assert any("🔵 seo" in name for name in names)
        # 🟢-Gaps landen als Task (Info-Zweig)
        assert any("🟢 invoice" in name for name in names)
        assert calls[0]["tasks"][0]["files"] == ["/tmp/proj"]
        assert calls[0]["tasks"][0]["id"] == "gap-1"

    def test_json_string_result_is_parsed(self, plan_registry):
        plan_registry(_entry(lambda payload: json.dumps({"plan_id": "abc"})))

        assert ui_gap._try_generate_plan_from_gaps("/tmp/proj", [_gap("🔴")]) == {"plan_id": "abc"}

    def test_non_dict_json_result_returns_none(self, plan_registry):
        plan_registry(_entry(lambda payload: json.dumps(["nur", "eine", "liste"])))

        assert ui_gap._try_generate_plan_from_gaps("/tmp/proj", [_gap("🔴")]) is None

    def test_handler_exception_is_swallowed(self, plan_registry):
        def handler(payload):
            raise RuntimeError("plan_follow kaputt")

        plan_registry(_entry(handler))

        assert ui_gap._try_generate_plan_from_gaps("/tmp/proj", [_gap("🔴")]) is None

    def test_empty_gap_list_builds_plan_without_tasks(self, plan_registry):
        calls = []
        plan_registry(_entry(lambda payload: calls.append(payload) or {"ok": True}))

        ui_gap._try_generate_plan_from_gaps("/tmp/proj", [])

        assert calls[0]["tasks"] == []


# ---------------------------------------------------------------------------
# analysis_ui_gap_tool
# ---------------------------------------------------------------------------


class TestToolHandler:
    def test_missing_path_argument(self):
        payload = json.loads(ui_gap.analysis_ui_gap_tool({}))

        assert payload["status"] == "error"
        assert "Path" in payload["error"]

    def test_unknown_path(self, tmp_path):
        payload = json.loads(ui_gap.analysis_ui_gap_tool({"path": str(tmp_path / "nope")}))

        assert payload["status"] == "error"

    def test_project_without_ui_layers_warns(self, tmp_path):
        project = tmp_path / "plain"
        project.mkdir()

        payload = json.loads(ui_gap.analysis_ui_gap_tool({"path": str(project)}))

        assert payload["status"] == "warning"
        assert "Keine UI-Layer" in payload["message"]

    def test_non_list_gaps_are_treated_as_empty(self, tmp_path, monkeypatch):
        project = tmp_path / "proj"
        project.mkdir()

        monkeypatch.setattr(ui_gap, "discover_uis", lambda path: [types.SimpleNamespace(routes=[])])
        monkeypatch.setattr(
            ui_gap,
            "build_coverage_matrix",
            lambda path: {"_coverage": {"total_modules": 0}, "_gaps": "kaputt", "_meta": {}},
        )

        # JSON-Format: `_gaps` wird unverändert durchgereicht, aber nicht als
        # Liste interpretiert (kein Plan, kein Crash)
        payload = json.loads(ui_gap.analysis_ui_gap_tool({"path": str(project), "format": "json"}))

        assert payload["status"] == "ok"
        assert payload["data"]["gaps"] == "kaputt"

    def test_exception_during_analysis_is_reported(self, tmp_path, monkeypatch):
        project = tmp_path / "proj"
        project.mkdir()

        monkeypatch.setattr(ui_gap, "discover_uis", lambda path: [types.SimpleNamespace(routes=[])])

        def _boom(path):
            raise ValueError("Matrix kaputt")

        monkeypatch.setattr(ui_gap, "build_coverage_matrix", _boom)

        payload = json.loads(ui_gap.analysis_ui_gap_tool({"path": str(project)}))

        assert payload["status"] == "error"
        assert "Matrix kaputt" in payload["error"]

    def test_text_output_contains_summary(self, tmp_path, monkeypatch):
        project = tmp_path / "proj"
        project.mkdir()

        monkeypatch.setattr(ui_gap, "discover_uis", lambda path: [types.SimpleNamespace(routes=[{"path": "/"}])])
        monkeypatch.setattr(
            ui_gap,
            "build_coverage_matrix",
            lambda path: {
                "_coverage": {
                    "total_modules": 2,
                    "with_admin": 1,
                    "admin_coverage_pct": 50,
                    "with_storefront": 0,
                    "storefront_coverage_pct": 0,
                    "with_detail_admin": 0,
                },
                "_gaps": [_gap("🔴"), _gap("🟢")],
                "_meta": {"project_root": str(project), "total_layers": 1, "layers_found": []},
            },
        )

        payload = json.loads(ui_gap.analysis_ui_gap_tool({"path": str(project), "format": "text"}))

        assert payload["layers"] == 1
        assert payload["total_routes"] == 1
        assert payload["gap_count"] == 2
        assert "ZUSAMMENFASSUNG" in payload["report"]
        assert "Critical (Admin fehlt): 1" in payload["report"]
        assert "Info (API ohne Page): 1" in payload["report"]
