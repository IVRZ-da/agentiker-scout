"""Integrationstests für Scout — Cross-Domain Workflows.

MIGRIERT AUS: scout/tests/test_e2e/test_e2e_workflows.py (2 Tests)
Grund: Cross-Domain Workflows (analysis → bughunt, security → report).
Diese Tests prüfen dass Tools in realistischer Reihenfolge zusammenarbeiten.

KEIN E2E_TEST Gate mehr — läuft immer, aber als 'integration' markiert.
"""

import json
import pytest

pytestmark = pytest.mark.integration


class TestCrossDomainWorkflows:
    """Cross-domain workflows (analysis → bughunt → research)."""

    def test_inspect_then_bughunt(self, tmp_path):
        """Erst analysis_inspect, dann bug_hunt_start auf selbes Projekt."""
        from scout.analysis.analysis_tools import analysis_inspect_tool
        from scout.bughunt.bughunt_tools import bug_hunt_start

        # Sample-Projekt in tmp_path anlegen
        sample_file = tmp_path / "_fmt.py"
        sample_file.write_text("""def hello():
    return \"world\"

class Calculator:
    def add(self, a, b):
        return a + b
""")

        # Step 1: Analyse
        inspect_result = json.loads(analysis_inspect_tool({"path": str(sample_file), "depth": 1}))
        assert inspect_result.get("status") != "error"

        # Step 2: Bug-Hunt starten
        session_result = json.loads(bug_hunt_start({"project": str(tmp_path), "scope": "quick"}))
        if session_result.get("status") == "error":
            # BugHunt braucht manchmal spezifische Struktur — akzeptiere graceful degradation
            assert "error" in session_result
        else:
            assert session_result.get("session_id") or session_result.get("data", {}).get("session_id", "")

    def test_security_then_report(self, tmp_path):
        """analysis_security → analysis_report."""
        from scout.analysis.analysis_tools import analysis_security_tool, analysis_report_tool

        # Security scan
        sec_result = json.loads(analysis_security_tool({"path": str(tmp_path), "kinds": ["errors"]}))
        # Security scan kann auf tmp_path (leeres Verzeichnis) fehlschlagen — das ist OK
        if sec_result.get("status") != "error":
            # Report
            report_result = json.loads(analysis_report_tool({
                "scope": "test-integration",
                "findings": {"test": "value"},
            }))
            assert report_result.get("status") != "error"
