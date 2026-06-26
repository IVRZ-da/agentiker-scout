"""Tests for MCP Chrome DevTools Integration im Scout Plugin.

Testet:
- is_mcp_devtools_available() — Registry-Check
- _extract_console_errors() — Console Finding-Extraktion
- _extract_network_errors() — Network Finding-Extraktion
- _CODE_INTEL_SCAN_MAP — console_errors + network_errors Einträge
"""


class TestMcpDevtoolsAvailability:
    """is_mcp_devtools_available — Registry-Check fuer MCP Tools."""

    def test_not_available_by_default(self):
        """Ohne Registry-Eintrag -> False."""
        from scout.bughunt.bughunt_scanrunner import is_mcp_devtools_available
        assert is_mcp_devtools_available() is False

    def test_available_when_registered(self):
        """Mit Registry-Eintrag -> True."""
        from tools.registry import registry

        from scout.bughunt.bughunt_scanrunner import is_mcp_devtools_available
        registry.entries["mcp_chrome_devtools_list_console_messages"] = {"tool": "mocked"}
        try:
            assert is_mcp_devtools_available() is True
        finally:
            registry.entries.pop("mcp_chrome_devtools_list_console_messages", None)

    def test_other_tool_does_not_trigger(self):
        """Nur das spezifische MCP-Tool zaehlt."""
        from tools.registry import registry

        from scout.bughunt.bughunt_scanrunner import is_mcp_devtools_available
        registry.entries["mcp_something_else"] = {"tool": "mocked"}
        try:
            assert is_mcp_devtools_available() is False
        finally:
            registry.entries.pop("mcp_something_else", None)


class TestConsoleErrorsExtraction:
    """_extract_console_errors — Console Message Finding-Extraktion."""

    def test_empty_input(self):
        from scout.bughunt.bughunt_scanrunner import _extract_console_errors
        assert _extract_console_errors("") == []
        assert _extract_console_errors(None) == []

    def test_no_errors(self):
        from scout.bughunt.bughunt_scanrunner import _extract_console_errors
        result = _extract_console_errors(
            "## Console messages\n[log] everything ok\n[info] loaded"
        )
        assert result == []

    def test_extracts_errors(self):
        from scout.bughunt.bughunt_scanrunner import _extract_console_errors
        findings = _extract_console_errors(
            "## Console messages\n[error] TypeError: undefined\n[warn] Deprecated API\n[log] ok"
        )
        assert len(findings) == 2
        assert findings[0]["severity"] == "P1"  # error
        assert findings[1]["severity"] == "P2"  # warn
        assert all(f["file"] == "browser_console" for f in findings)

    def test_dict_format(self):
        from scout.bughunt.bughunt_scanrunner import _extract_console_errors
        result = {"result": "## Console messages\n[error] Network Error\n[warn] Slow"}
        findings = _extract_console_errors(result)
        assert len(findings) == 2

    def test_warning_keyword(self):
        """Auch 'warning' wird als Warnung erkannt."""
        from scout.bughunt.bughunt_scanrunner import _extract_console_errors
        findings = _extract_console_errors(
            "## Console messages\n[warning] Deprecated property used"
        )
        assert len(findings) == 1
        assert findings[0]["severity"] == "P2"


class TestNetworkErrorsExtraction:
    """_extract_network_errors — Network 4xx/5xx Finding-Extraktion."""

    def test_empty_input(self):
        from scout.bughunt.bughunt_scanrunner import _extract_network_errors
        assert _extract_network_errors("") == []
        assert _extract_network_errors(None) == []

    def test_all_200_ignored(self):
        from scout.bughunt.bughunt_scanrunner import _extract_network_errors
        result = _extract_network_errors(
            "reqid=1 GET / [200]\nreqid=2 POST /api [200]"
        )
        assert result == []

    def test_extracts_4xx(self):
        from scout.bughunt.bughunt_scanrunner import _extract_network_errors
        findings = _extract_network_errors(
            "reqid=1 GET /login [401]\nreqid=2 GET /css [404]"
        )
        assert len(findings) == 2
        assert all(f["severity"] == "P2" for f in findings)
        assert all(f["file"] == "browser_network" for f in findings)

    def test_extracts_5xx(self):
        from scout.bughunt.bughunt_scanrunner import _extract_network_errors
        findings = _extract_network_errors(
            "reqid=1 POST /data [500]\nreqid=2 GET /api [503]"
        )
        assert len(findings) == 2
        assert all(f["severity"] == "P1" for f in findings)

    def test_mixed_status_codes(self):
        from scout.bughunt.bughunt_scanrunner import _extract_network_errors
        findings = _extract_network_errors(
            "reqid=1 GET / [200]\nreqid=2 POST /login [401]\n"
            "reqid=3 PUT /data [500]\nreqid=4 GET /css [404]"
        )
        assert len(findings) == 3
        sevs = [f["severity"] for f in findings]
        assert sevs == ["P2", "P1", "P2"]  # 401=P2, 500=P1, 404=P2

    def test_dict_format(self):
        from scout.bughunt.bughunt_scanrunner import _extract_network_errors
        result = {"result": "reqid=1 GET /api [500]\nreqid=2 GET /ok [200]"}
        findings = _extract_network_errors(result)
        assert len(findings) == 1
        assert findings[0]["severity"] == "P1"


class TestCodeIntelScanMap:
    """_CODE_INTEL_SCAN_MAP — neue console_errors + network_errors Eintraege."""

    def test_console_errors_entry(self):
        from scout.bughunt.bughunt_scanrunner import _CODE_INTEL_SCAN_MAP
        assert "console_errors" in _CODE_INTEL_SCAN_MAP
        entry = _CODE_INTEL_SCAN_MAP["console_errors"]
        assert entry["tool"] == "mcp_chrome_devtools_list_console_messages"
        assert callable(entry["finding_extractor"])

    def test_network_errors_entry(self):
        from scout.bughunt.bughunt_scanrunner import _CODE_INTEL_SCAN_MAP
        assert "network_errors" in _CODE_INTEL_SCAN_MAP
        entry = _CODE_INTEL_SCAN_MAP["network_errors"]
        assert entry["tool"] == "mcp_chrome_devtools_list_network_requests"
        assert callable(entry["finding_extractor"])
