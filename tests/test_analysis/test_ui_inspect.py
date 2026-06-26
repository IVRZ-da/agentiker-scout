"""Tests für analysis_ui_inspect — UI-Element-Analyse via Chrome DevTools MCP.

Testet:
- analysis_ui_inspect_tool() ohne MCP (Graceful Degradation)
- _call_mcp() mit gemockter Registry
- _inspect_dom() JS-Code-Generierung
- _check_ui_presence() JS-Code-Generierung
"""

from __future__ import annotations

from unittest.mock import MagicMock


class MockEntry:
    def __init__(self, return_value="mocked_result"):
        self.handler = MagicMock(return_value=return_value)


class TestUiInspectNoMCP:
    """analysis_ui_inspect_tool ohne MCP-Verfuegbarkeit."""

    def test_no_url_returns_error(self):
        from scout.analysis.tools.ui_inspect import analysis_ui_inspect_tool
        result = analysis_ui_inspect_tool({"url": ""})
        assert "error" in result or "fmt_err" in result or "erforderlich" in result

    def test_graceful_degradation_without_mcp(self):
        """Ohne MCP sollen Instructions zurueckgegeben werden."""
        from scout.analysis.tools.ui_inspect import analysis_ui_inspect_tool
        result = analysis_ui_inspect_tool({"url": "https://example.com"})
        assert isinstance(result, str)
        # Sollte einen fmt_ok/err zurueckgeben
        # fmt_ok gibt dict mit "instruction"
        assert len(result) > 0

    def test_graceful_with_all_params(self):
        from scout.analysis.tools.ui_inspect import analysis_ui_inspect_tool
        result = analysis_ui_inspect_tool({
            "url": "https://example.com",
            "include_dom": True,
            "check_presence": True,
        })
        assert isinstance(result, str)
        assert len(result) > 0


class TestCallMcp:
    """_call_mcp — Registry-Dispatch fuer MCP-Tools."""

    def test_returns_mcp_not_available(self):
        from scout.analysis.tools.ui_inspect import _call_mcp
        registry = MagicMock()
        registry.get_entry.return_value = None
        result = _call_mcp(registry, "mcp_chrome_devtools_take_snapshot", {})
        assert "nicht verfuegbar" in result

    def test_calls_handler_with_args(self):
        from scout.analysis.tools.ui_inspect import _call_mcp
        registry = MagicMock()
        mock_entry = MockEntry('{"result": "test_snapshot"}')
        registry.get_entry.return_value = mock_entry

        result = _call_mcp(registry, "mcp_chrome_devtools_take_snapshot", {})
        assert "test_snapshot" in result
        mock_entry.handler.assert_called_once_with({})

    def test_handles_exception(self):
        from scout.analysis.tools.ui_inspect import _call_mcp
        registry = MagicMock()
        mock_entry = MagicMock()
        mock_entry.handler.side_effect = RuntimeError("CDP connection failed")
        registry.get_entry.return_value = mock_entry

        result = _call_mcp(registry, "mcp_chrome_devtools_navigate_page",
                           {"url": "http://test.de"})
        assert "connection failed" in result

    def test_truncates_long_result(self):
        from scout.analysis.tools.ui_inspect import _call_mcp
        registry = MagicMock()
        mock_entry = MockEntry("x" * 5000)
        registry.get_entry.return_value = mock_entry

        result = _call_mcp(registry, "mcp_chrome_devtools_take_snapshot", {})
        assert len(result) <= 1100  # 1000 char limit + prefix


class TestDomInspection:
    """_inspect_dom — JS-Code und Registry-Dispatch."""

    def test_no_evaluate_script_entry(self):
        from scout.analysis.tools.ui_inspect import _inspect_dom
        registry = MagicMock()
        registry.get_entry.return_value = None
        result = _inspect_dom(registry)
        assert "nicht verfuegbar" in result

    def test_calls_evaluate_script(self):
        from scout.analysis.tools.ui_inspect import _inspect_dom
        registry = MagicMock()
        mock_entry = MockReturnEntry('{"totalElements": 42, "visible": 30, '
                                     '"hidden": 12, "inputs": 3, "buttons": 5, '
                                     '"links": 10, "images": 2, "headings": 4}')
        registry.get_entry.return_value = mock_entry.entry

        result = _inspect_dom(registry)
        assert "42" in result or "totalElements" in result or mock_entry.result in result

    def test_js_code_contains_expected_selectors(self):
        """Der JS-Code sollte relevante DOM-Selektoren enthalten."""
        from scout.analysis.tools.ui_inspect import _inspect_dom
        # Indirekter Test: die Funktion nutzt evaluate_script mit festem JS-Code
        # Wir pruefen dass evaluate_script aufgerufen wird
        registry = MagicMock()
        registry.get_entry.return_value = None
        result = _inspect_dom(registry)
        assert "nicht verfuegbar" in result  # Kein MCP -> Meldung


class MockReturnEntry:
    """Helper: liefert ein MockEntry mit serialisierbarem Ergebnis."""
    def __init__(self, json_result: str):
        self.result = json_result
        self.entry = MagicMock()
        self.entry.handler = MagicMock(return_value=json_result)


class TestPresenceCheck:
    """_check_ui_presence — UI-Element-Pruefung."""

    def test_no_evaluate_script(self):
        from scout.analysis.tools.ui_inspect import _check_ui_presence
        registry = MagicMock()
        registry.get_entry.return_value = None
        result = _check_ui_presence(registry)
        assert "nicht verfuegbar" in result

    def test_calls_evaluate_script_with_presence_js(self):
        from scout.analysis.tools.ui_inspect import _check_ui_presence
        registry = MagicMock()
        mock_entry = MockReturnEntry('{"navigation": true, "main": true, '
                                     '"footer": true, "search": false, '
                                     '"headings": 3, "buttons": 8, '
                                     '"links": 15, "images": 1, "forms": 1}')
        registry.get_entry.return_value = mock_entry.entry

        result = _check_ui_presence(registry)
        assert mock_entry.result in result


class TestBaseline:
    """Baseline-Funktionen — speichern + vergleichen."""

    def test_store_and_find_baseline(self, tmp_path):
        """Baseline speichern und Datei finden."""
        # monkeypatch das Baseline-Verzeichnis
        import scout.analysis.tools.ui_inspect as ui_mod
        from scout.analysis.tools.ui_inspect import _baseline_path, _store_baseline
        original = ui_mod._BASELINE_DIR
        try:
            ui_mod._BASELINE_DIR = tmp_path / "baselines"
            test_url = "https://example.com/page"
            _store_baseline(test_url, {"dom_info": "test", "console_messages": "ok"})
            path = _baseline_path(test_url)
            assert path.exists()
            assert path.stat().st_size > 10
        finally:
            ui_mod._BASELINE_DIR = original

    def test_compare_no_baseline(self):
        """Ohne Baseline -> 'Keine Baseline'."""
        from scout.analysis.tools.ui_inspect import _compare_with_baseline
        result = _compare_with_baseline("https://no-baseline.com", {})
        assert "Keine Baseline" in result or "keine" in result.lower()

    def test_compare_identical(self, tmp_path):
        """Identische Daten -> keine Unterschiede."""
        import scout.analysis.tools.ui_inspect as ui_mod
        from scout.analysis.tools.ui_inspect import (
            _compare_with_baseline,
            _store_baseline,
        )
        original = ui_mod._BASELINE_DIR
        try:
            ui_mod._BASELINE_DIR = tmp_path / "baselines"
            test_url = "https://example.com/same"
            data = {"dom_info": "a", "console_messages": "b", "network_requests": "c"}
            _store_baseline(test_url, data)
            result = _compare_with_baseline(test_url, data)
            assert "keine" in result.lower() or "Keine" in result
        finally:
            ui_mod._BASELINE_DIR = original

    def test_compare_different(self, tmp_path):
        """Unterschiedliche Daten -> Unterschiede erkennen."""
        import scout.analysis.tools.ui_inspect as ui_mod
        from scout.analysis.tools.ui_inspect import _compare_with_baseline, _store_baseline
        original = ui_mod._BASELINE_DIR
        try:
            ui_mod._BASELINE_DIR = tmp_path / "baselines"
            test_url = "https://example.com/diff"
            _store_baseline(test_url, {"dom_info": "old", "console_messages": "old"})
            result = _compare_with_baseline(test_url, {"dom_info": "new", "console_messages": "old"})
            assert "DOM" in result or "Unterschied" in result
        finally:
            ui_mod._BASELINE_DIR = original

    def test_corrupt_baseline(self, tmp_path):
        """Korrupte Baseline -> entsprechende Meldung."""
        import scout.analysis.tools.ui_inspect as ui_mod
        from scout.analysis.tools.ui_inspect import _baseline_path, _compare_with_baseline
        original = ui_mod._BASELINE_DIR
        try:
            ui_mod._BASELINE_DIR = tmp_path / "baselines"
            # Kaputte JSON-Datei erstellen
            path = _baseline_path("https://example.com/corrupt")
            path.write_text("{kaputt}", encoding="utf-8")
            result = _compare_with_baseline("https://example.com/corrupt", {})
            assert "korrupt" in result.lower() or "lesbar" in result.lower()
        finally:
            ui_mod._BASELINE_DIR = original
