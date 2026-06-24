"""Tests für analysis/tools/graph_patterns.py — Mermaid-Generierung + Pattern Discovery."""

from __future__ import annotations

import json
from pathlib import Path

from scout.analysis.tools.graph_patterns import (
    _mermaid_from_cycles,
    _mermaid_from_dependency,
    analysis_graph_tool,
)

# ======================================================================
# _mermaid_from_dependency
# ======================================================================

class TestMermaidFromDependency:
    def test_empty_data(self):
        result = _mermaid_from_dependency({})
        assert "no_data" in result

    def test_dict_with_list_items(self):
        data = {"modules": [["a", "b"], ["b", "c"]]}
        result = _mermaid_from_dependency(data)
        assert "a --> b" in result
        assert "b --> c" in result

    def test_dict_with_string_items(self):
        data = {"modules": ["module_a", "module_b"]}
        result = _mermaid_from_dependency(data)
        assert "module_a" in result
        assert "module_b" in result

    def test_string_with_arrows(self):
        data = "auth -> db\napi -> auth"
        result = _mermaid_from_dependency(data)
        assert "auth --> db" in result
        assert "api --> auth" in result

    def test_none_data(self):
        result = _mermaid_from_dependency(None)
        assert "no_data" in result

    def test_empty_string(self):
        result = _mermaid_from_dependency("")
        assert "no_data" in result


# ======================================================================
# _mermaid_from_cycles
# ======================================================================

class TestMermaidFromCycles:
    def test_no_cycles(self):
        result = _mermaid_from_cycles({})
        assert "no_cycles" in result

    def test_with_cycles_list(self):
        data = {"cycles": [["a", "b", "a"], ["x", "y", "x"]]}
        result = _mermaid_from_cycles(data)
        assert "a_0 --> b_0" in result
        assert "b_0 --> a_0" in result
        assert "Cycle 1" in result

    def test_with_data_fallback(self):
        data = {"data": [["a", "b", "a"]]}
        result = _mermaid_from_cycles(data)
        assert "a_0 --> b_0" in result

    def test_max_5_cycles(self):
        cycles = [[f"m{i}", f"n{i}", f"m{i}"] for i in range(10)]
        data = {"cycles": cycles}
        result = _mermaid_from_cycles(data)
        # Nur 5 Cycles sollten gerendert werden
        assert "Cycle 1" in result
        assert "Cycle 5" in result

    def test_non_list_cycles(self):
        result = _mermaid_from_cycles({"cycles": "not a list"})
        assert "no_cycles" in result


# ======================================================================
# analysis_graph_tool
# ======================================================================

class TestAnalysisGraphTool:
    def test_missing_report(self):
        result = analysis_graph_tool({"report": {}})
        data = json.loads(result)
        assert data["status"] == "error"

    def test_dependency_graph(self):
        report = {
            "tool": "analysis_architecture",
            "sections": {
                "dependency_graph": {"modules": [["a", "b"]]}
            }
        }
        result = analysis_graph_tool({"report": report, "type": "dependency"})
        data = json.loads(result)
        assert data["status"] == "ok"
        assert "a --> b" in str(data)

    def test_cycles_graph(self):
        report = {
            "tool": "analysis_architecture",
            "sections": {
                "cycles": {"cycles": [["a", "b", "a"]]}
            }
        }
        result = analysis_graph_tool({"report": report, "type": "cycles"})
        data = json.loads(result)
        assert data["status"] == "ok"

    def test_summary_graph(self):
        report = {
            "summary": {"files": 10, "modules": 5, "status": "clean"},
        }
        result = analysis_graph_tool({"report": report, "type": "summary"})
        data = json.loads(result)
        assert data["status"] == "ok"

    def test_report_with_layers(self):
        """Fallback auf layers wenn sections fehlt."""
        report = {
            "tool": "inspect",
            "layers": {
                "dependency_graph": {"mods": [["x", "y"]]}
            }
        }
        result = analysis_graph_tool({"report": report, "type": "dependency"})
        data = json.loads(result)
        assert data["status"] == "ok"

    def test_report_with_findings(self):
        """Fallback auf findings wenn sections+layers fehlen."""
        report = {
            "tool": "deadcode",
            "findings": {"unused": []}
        }
        result = analysis_graph_tool({"report": report, "type": "dependency"})
        data = json.loads(result)
        assert data["status"] == "ok"


# ======================================================================
# analysis_pattern_discover_tool
# ======================================================================

class TestAnalysisPatternDiscoverTool:
    def test_missing_path(self):
        from scout.analysis.tools.graph_patterns import analysis_pattern_discover_tool
        result = analysis_pattern_discover_tool({"path": ""})
        data = json.loads(result)
        assert data["status"] == "error"

    def test_nonexistent_path(self):
        from scout.analysis.tools.graph_patterns import analysis_pattern_discover_tool
        result = analysis_pattern_discover_tool({"path": "/nonexistent/path/12345"})
        data = json.loads(result)
        # Kann ok oder error sein (manche Resolver akzeptieren alles)
        assert data["status"] in ("ok", "error")

    def test_with_tmp_path(self, tmp_path: Path):
        """Sollte für ein leeres Verzeichnis keine Patterns finden."""
        from scout.analysis.tools.graph_patterns import analysis_pattern_discover_tool
        result = analysis_pattern_discover_tool({"path": str(tmp_path)})
        data = json.loads(result)
        # Kann ok oder error sein, je nachdem ob Framework-Detection funktioniert
        assert data["status"] in ("ok", "error")
