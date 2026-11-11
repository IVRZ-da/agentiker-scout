"""Fehlerpfade der Honcho-Bruecke und der UI-Inspektion.

Beide Module tun so, als waeren sie optional: fehlt eine Domaene oder das MCP,
soll der Aufrufer eine brauchbare Antwort bekommen statt eines Tracebacks.
Genau diese Zweige waren ungetestet.
"""
from __future__ import annotations

import sys

import pytest

# ─── shared/honcho.py ───────────────────────────────────────────────────

class TestHonchoSessionHelpers:
    """Jeder Helper faengt fehlende Domaenen ab und liefert None."""

    def test_analysis_session_none_when_import_fails(self, monkeypatch):
        import scout.shared.honcho as honcho

        monkeypatch.setitem(sys.modules, "scout.analysis.analysis_session", None)
        assert honcho._get_analysis_session() is None

    def test_analysis_session_reports_intent(self, monkeypatch):
        import types

        import scout.shared.honcho as honcho

        session = types.SimpleNamespace(intent="review", findings=[1, 2, 3])
        fake = types.ModuleType("scout.analysis.analysis_session")
        fake._active_session = session
        monkeypatch.setitem(sys.modules, "scout.analysis.analysis_session", fake)

        result = honcho._get_analysis_session()
        assert result == {"intent": "review", "findings_count": 3}

    def test_bughunt_session_none_when_import_fails(self, monkeypatch):
        import scout.shared.honcho as honcho

        monkeypatch.setitem(sys.modules, "scout.bughunt.bughunt_core", None)
        assert honcho._get_bughunt_session() is None

    def test_bughunt_session_maps_fields(self, monkeypatch):
        import types

        import scout.shared.honcho as honcho

        fake = types.ModuleType("scout.bughunt.bughunt_core")
        fake.get_active_session = lambda: {"findings": [1, 2], "severity": "P1"}
        monkeypatch.setitem(sys.modules, "scout.bughunt.bughunt_core", fake)

        assert honcho._get_bughunt_session() == {"findings_count": 2, "severity": "P1"}

    def test_bughunt_session_obj_none_without_active_tracker(self, monkeypatch):
        import types

        import scout.shared.honcho as honcho

        class Tracker:
            def is_active(self):
                return False

        fake = types.ModuleType("scout.bughunt.bughunt_core")
        fake.get_tracker = lambda: Tracker()
        fake.load_session = lambda sid: {"id": sid}
        monkeypatch.setitem(sys.modules, "scout.bughunt.bughunt_core", fake)

        assert honcho._get_bughunt_session_obj() is None

    def test_bughunt_session_obj_loads_active_session(self, monkeypatch):
        import types

        import scout.shared.honcho as honcho

        class Tracker:
            active_session_id = "s-1"

            def is_active(self):
                return True

        loaded = {"id": "s-1"}
        fake = types.ModuleType("scout.bughunt.bughunt_core")
        fake.get_tracker = lambda: Tracker()
        fake.load_session = lambda sid: loaded
        monkeypatch.setitem(sys.modules, "scout.bughunt.bughunt_core", fake)

        assert honcho._get_bughunt_session_obj() is loaded

    def test_research_session_none_when_import_fails(self, monkeypatch):
        import scout.shared.honcho as honcho

        monkeypatch.setitem(sys.modules, "scout.research.research_core", None)
        assert honcho._get_research_session() is None

    def test_research_session_maps_fields(self, monkeypatch):
        import types

        import scout.shared.honcho as honcho

        fake = types.ModuleType("scout.research.research_core")
        fake.get_active_research = lambda: {"query": "cannabis", "sources": ["a", "b"]}
        monkeypatch.setitem(sys.modules, "scout.research.research_core", fake)

        assert honcho._get_research_session() == {"query": "cannabis", "sources_count": 2}


class TestHonchoPersist:
    def test_pattern_deduction_failure_is_logged_not_raised(self, monkeypatch):
        """Ein Fehler in der Pattern-Ableitung darf den Session-End nicht kippen."""
        import scout.shared.honcho as honcho

        monkeypatch.setattr(honcho, "_get_bughunt_session", lambda: {"findings_count": 1})
        monkeypatch.setattr(honcho, "_get_bughunt_session_obj", lambda: object())

        def boom(session):
            raise RuntimeError("deduction kaputt")

        import types

        broken = types.ModuleType("scout.bughunt.bughunt_hooks")
        broken._auto_deduce_patterns = boom
        monkeypatch.setitem(sys.modules, "scout.bughunt.bughunt_hooks", broken)

        # darf nicht werfen
        honcho._persist_bughunt_summary()


# ─── analysis/tools/ui_inspect.py ───────────────────────────────────────

class TestUiInspectDegradation:
    def test_without_mcp_returns_instruction(self, monkeypatch):
        """Ohne Chrome-DevTools-MCP gibt es eine Anleitung statt eines Fehlers."""
        import scout.analysis.tools.ui_inspect as ui

        class EmptyRegistry:
            def get_entry(self, name):
                return None

        monkeypatch.setattr(
            "scout.shared.registry.registry", EmptyRegistry(), raising=False
        )

        result = ui.analysis_ui_inspect_tool({"url": "https://example.com"})
        assert "MCP" in result or "mcp_available" in result
        assert "Traceback" not in result

    def test_mcp_import_failure_degrades(self, monkeypatch):
        import scout.analysis.tools.ui_inspect as ui

        monkeypatch.setitem(sys.modules, "scout.shared.registry", None)
        result = ui.analysis_ui_inspect_tool({"url": "https://example.com"})
        assert isinstance(result, str)

    def test_inspection_exception_becomes_error_message(self, monkeypatch):
        import scout.analysis.tools.ui_inspect as ui

        class Registry:
            def get_entry(self, name):
                return object()

        monkeypatch.setattr(
            "scout.shared.registry.registry", Registry(), raising=False
        )

        def boom(*args, **kwargs):
            raise RuntimeError("DOM kaputt")

        monkeypatch.setattr(ui, "_run_ui_inspection", boom)
        result = ui.analysis_ui_inspect_tool({"url": "https://example.com"})
        assert "fehlgeschlagen" in result
        assert "DOM kaputt" in result


class TestUiInspectionFlow:
    """``_run_ui_inspection`` mit allen Flag-Kombinationen."""

    @pytest.fixture
    def ui(self):
        import scout.analysis.tools.ui_inspect as module

        return module

    def test_plain_run_without_flags(self, ui, monkeypatch):
        monkeypatch.setattr(ui, "_call_mcp", lambda registry, name, args: f"{name}-ok")
        result = ui._run_ui_inspection("https://x.test", False, False, False, False)
        assert "x.test" in result or "url" in result

    def test_with_dom_and_presence(self, ui, monkeypatch):
        calls = {"dom": 0, "presence": 0}
        monkeypatch.setattr(ui, "_call_mcp", lambda registry, name, args: "ok")
        monkeypatch.setattr(ui, "_inspect_dom", lambda registry: calls.__setitem__("dom", calls["dom"] + 1) or "dom")
        monkeypatch.setattr(ui, "_check_ui_presence", lambda registry: calls.__setitem__("presence", calls["presence"] + 1) or "presence")

        ui._run_ui_inspection("https://x.test", True, True, False, False)
        assert calls == {"dom": 1, "presence": 1}

    def test_store_baseline_writes_file(self, ui, monkeypatch, tmp_path):
        monkeypatch.setattr(ui, "_call_mcp", lambda registry, name, args: "ok")
        monkeypatch.setattr(ui, "_baseline_path", lambda url: tmp_path / "b.json")

        ui._run_ui_inspection("https://x.test", False, False, True, False)
        assert (tmp_path / "b.json").exists()

    def test_compare_baseline_reports_differences(self, ui, monkeypatch, tmp_path):
        path = tmp_path / "b.json"
        path.write_text('{"data": {"dom_info": "alt", "console_messages": "a", "network_requests": "n"}}', encoding="utf-8")
        monkeypatch.setattr(ui, "_baseline_path", lambda url: path)
        monkeypatch.setattr(ui, "_call_mcp", lambda registry, name, args: "neu")

        result = ui._run_ui_inspection("https://x.test", False, False, False, True)
        assert "DOM-Info" in result or "unterschiedlich" in result.lower()


class TestBaselineComparison:
    def test_missing_baseline(self, ui_module, monkeypatch, tmp_path):
        monkeypatch.setattr(ui_module, "_baseline_path", lambda url: tmp_path / "nix.json")
        assert "Keine Baseline" in ui_module._compare_with_baseline("u", {})

    def test_corrupt_baseline(self, ui_module, monkeypatch, tmp_path):
        path = tmp_path / "kaputt.json"
        path.write_text("{kein json", encoding="utf-8")
        monkeypatch.setattr(ui_module, "_baseline_path", lambda url: path)
        assert "korrupt" in ui_module._compare_with_baseline("u", {})

    def test_console_only_difference(self, ui_module, monkeypatch, tmp_path):
        path = tmp_path / "b.json"
        path.write_text('{"data": {"dom_info": "gleich", "console_messages": "alt", "network_requests": "n"}}', encoding="utf-8")
        monkeypatch.setattr(ui_module, "_baseline_path", lambda url: path)

        result = ui_module._compare_with_baseline("u", {
            "dom_info": "gleich", "console_messages": "neu", "network_requests": "n",
        })
        assert "Console" in result

    def test_network_only_difference(self, ui_module, monkeypatch, tmp_path):
        path = tmp_path / "b.json"
        path.write_text('{"data": {"dom_info": "g", "console_messages": "c", "network_requests": "alt"}}', encoding="utf-8")
        monkeypatch.setattr(ui_module, "_baseline_path", lambda url: path)

        result = ui_module._compare_with_baseline("u", {
            "dom_info": "g", "console_messages": "c", "network_requests": "neu",
        })
        assert "Network" in result

    def test_identical_reports_no_differences(self, ui_module, monkeypatch, tmp_path):
        path = tmp_path / "b.json"
        path.write_text('{"data": {"dom_info": "g", "console_messages": "c", "network_requests": "n"}}', encoding="utf-8")
        monkeypatch.setattr(ui_module, "_baseline_path", lambda url: path)

        result = ui_module._compare_with_baseline("u", {
            "dom_info": "g", "console_messages": "c", "network_requests": "n",
        })
        assert "Keine Unterschiede" in result

    def test_store_baseline_writes_payload(self, ui_module, monkeypatch, tmp_path):
        path = tmp_path / "b.json"
        monkeypatch.setattr(ui_module, "_baseline_path", lambda url: path)
        ui_module._store_baseline("https://x.test", {"dom_info": "d"})

        import json
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["url"] == "https://x.test"
        assert saved["data"] == {"dom_info": "d"}


@pytest.fixture
def ui_module():
    import scout.analysis.tools.ui_inspect as module

    return module
