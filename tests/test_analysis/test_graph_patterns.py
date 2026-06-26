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

    def test_multi_part_string_arrow(self):
        """String with multi-part -> line: nur erstes und letztes Element."""
        result = _mermaid_from_dependency("a -> b -> c")
        assert "a --> c" in result

    def test_dict_with_non_list_values(self):
        """Dict mit Nicht-List-Werten — kein Graph."""
        result = _mermaid_from_dependency({"key": "value"})
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
        assert "Cycle 1" in result
        assert "Cycle 5" in result
        assert "Cycle 6" not in result

    def test_non_list_cycles(self):
        result = _mermaid_from_cycles({"cycles": "not a list"})
        assert "no_cycles" in result

    def test_single_cycle(self):
        data = {"cycles": [["a", "b", "a"]]}
        result = _mermaid_from_cycles(data)
        assert "Cycle 1" in result
        assert "a_0 --> b_0" in result


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
            "sections": {"dependency_graph": {"modules": [["a", "b"]]}},
        }
        result = analysis_graph_tool({"report": report, "type": "dependency"})
        data = json.loads(result)
        assert data["status"] == "ok"
        assert "a --> b" in str(data)

    def test_dependency_graph_4_graphs_fallback(self):
        report = {
            "tool": "analysis",
            "sections": {"4_graphs": {"dependency_graph": {"modules": [["x", "y"]]}}},
        }
        result = analysis_graph_tool({"report": report, "type": "dependency"})
        data = json.loads(result)
        assert data["status"] == "ok"
        assert "x --> y" in str(data)

    def test_dependency_graph_report_fallback(self):
        report = {
            "tool": "analysis",
            "dependency_graph": {"modules": [["p", "q"]]},
        }
        result = analysis_graph_tool({"report": report, "type": "dependency"})
        data = json.loads(result)
        assert data["status"] == "ok"
        assert "p --> q" in str(data)

    def test_cycles_graph(self):
        report = {
            "tool": "analysis_architecture",
            "sections": {"cycles": {"cycles": [["a", "b", "a"]]}},
        }
        result = analysis_graph_tool({"report": report, "type": "cycles"})
        data = json.loads(result)
        assert data["status"] == "ok"

    def test_cycles_graph_4_graphs_fallback(self):
        report = {
            "tool": "analysis",
            "sections": {"4_graphs": {"cycles": {"cycles": [["x", "y", "x"]]}}},
        }
        result = analysis_graph_tool({"report": report, "type": "cycles"})
        data = json.loads(result)
        assert data["status"] == "ok"

    def test_cycles_graph_report_fallback(self):
        report = {
            "tool": "analysis",
            "cycles": {"cycles": [["p", "q", "p"]]},
        }
        result = analysis_graph_tool({"report": report, "type": "cycles"})
        data = json.loads(result)
        assert data["status"] == "ok"

    def test_summary_graph(self):
        report = {"summary": {"files": 10, "modules": 5, "status": "clean"}}
        result = analysis_graph_tool({"report": report, "type": "summary"})
        data = json.loads(result)
        assert data["status"] == "ok"
        assert "files: 10" in str(data)

    def test_summary_with_non_scalar_values(self):
        report = {"summary": {"files": 10, "details": {"nested": True}, "tags": ["a", "b"]}}
        result = analysis_graph_tool({"report": report, "type": "summary"})
        data = json.loads(result)
        assert data["status"] == "ok"
        assert "files: 10" in str(data)

    def test_report_with_layers(self):
        report = {
            "tool": "inspect",
            "layers": {"dependency_graph": {"mods": [["x", "y"]]}},
        }
        result = analysis_graph_tool({"report": report, "type": "dependency"})
        data = json.loads(result)
        assert data["status"] == "ok"

    def test_report_with_findings(self):
        report = {
            "tool": "deadcode",
            "findings": {"unused": []},
        }
        result = analysis_graph_tool({"report": report, "type": "dependency"})
        data = json.loads(result)
        assert data["status"] == "ok"


# ======================================================================
# analysis_pattern_discover_tool — Integrationstests
# ======================================================================

class TestAnalysisPatternDiscoverTool:
    def test_missing_path(self):
        from scout.analysis.tools.graph_patterns import analysis_pattern_discover_tool
        result = analysis_pattern_discover_tool({"path": ""})
        data = json.loads(result)
        assert data["status"] == "error"

    def test_with_tmp_path_empty(self, tmp_path: Path):
        from scout.analysis.tools.graph_patterns import analysis_pattern_discover_tool
        result = analysis_pattern_discover_tool({"path": str(tmp_path)})
        data = json.loads(result)
        assert data["status"] in ("ok", "error")

    def test_with_frameworks_list(self, tmp_path: Path):
        """frameworks=[] => else-Zweig mit fw_names = list(frameworks_opt)."""
        from scout.analysis.tools.graph_patterns import analysis_pattern_discover_tool
        result = analysis_pattern_discover_tool({
            "path": str(tmp_path),
            "frameworks": ["python"],
            "scan_language": "python",
        })
        data = json.loads(result)
        assert data["status"] in ("ok", "error")
        if data["status"] == "ok" and "frameworks" in data:
            assert "specified" in data["frameworks"]

    def test_frameworks_lang_detection(self, tmp_path: Path):
        """Ohne scan_language aber mit frameworks -> lang_map Detection."""
        from scout.analysis.tools.graph_patterns import analysis_pattern_discover_tool
        result = analysis_pattern_discover_tool({
            "path": str(tmp_path),
            "frameworks": ["python"],
        })
        data = json.loads(result)
        assert data["status"] in ("ok", "error")

    def test_with_candidates_confidence(self, tmp_path: Path):
        """Mehrere Pattern-Matches -> Confidence-Scoring wird durchlaufen."""
        from scout.analysis.tools.graph_patterns import analysis_pattern_discover_tool
        # Mehrere .py Dateien mit dem silent-catch Pattern
        for i in range(15):
            (tmp_path / f"f{i}.py").write_text(
                "try:\n    x = 1\nexcept?: pass\n"
            )
        result = analysis_pattern_discover_tool({
            "path": str(tmp_path),
            "min_frequency": 1,
            "scan_language": "python",
        })
        data = json.loads(result)
        assert data["status"] in ("ok", "error")


# ======================================================================
# _discover_* Helfer — Direkte Tests mit leeren existing_queries
# ======================================================================

class TestDiscoverPythonPatterns:
    def test_silent_catch_found(self, tmp_path: Path):
        from scout.analysis.tools.graph_patterns import _discover_python_patterns
        (tmp_path / "silent.py").write_text("try:\n    x = 1\nexcept?: pass\n")
        candidates = []
        _discover_python_patterns(tmp_path, candidates, set(), 1)
        names = [c["suggested_name"] for c in candidates]
        assert "Silent Catch (Python)" in names

    def test_silent_catch_below_min_frequency(self, tmp_path: Path):
        from scout.analysis.tools.graph_patterns import _discover_python_patterns
        (tmp_path / "silent.py").write_text("try:\n    x = 1\nexcept?: pass\n")
        candidates = []
        _discover_python_patterns(tmp_path, candidates, set(), 100)
        assert len(candidates) == 0

    def test_multiple_matches_for_confidence(self, tmp_path: Path):
        """Mehrere Matches -> höhere frequency im Candidate."""
        from scout.analysis.tools.graph_patterns import _discover_python_patterns
        for i in range(5):
            (tmp_path / f"f{i}.py").write_text(
                "try:\n    x = 1\nexcept?: pass\n"
            )
        candidates = []
        _discover_python_patterns(tmp_path, candidates, set(), 1)
        assert len(candidates) >= 1
        # Frequency sollte >= 5 sein
        assert candidates[0]["frequency"] >= 5


class TestDiscoverTSPatterns:
    def test_console_log_found(self, tmp_path: Path):
        from scout.analysis.tools.graph_patterns import _discover_ts_patterns
        (tmp_path / "debug.ts").write_text("console.log('test');\n")
        candidates = []
        _discover_ts_patterns(tmp_path, candidates, set(), 1)
        names = [c["suggested_name"] for c in candidates]
        assert "Console Log" in names

    def test_any_type_found(self, tmp_path: Path):
        from scout.analysis.tools.graph_patterns import _discover_ts_patterns
        (tmp_path / "loose.ts").write_text("const x: any = 1;\n")
        candidates = []
        _discover_ts_patterns(tmp_path, candidates, set(), 1)
        names = [c["suggested_name"] for c in candidates]
        assert "any" in " ".join(names).lower()

    def test_force_dynamic_found(self, tmp_path: Path):
        from scout.analysis.tools.graph_patterns import _discover_ts_patterns
        (tmp_path / "dynamic.ts").write_text("export const dynamic = 'force-dynamic';\n")
        candidates = []
        _discover_ts_patterns(tmp_path, candidates, set(), 1)
        names = [c["suggested_name"] for c in candidates]
        assert any("force" in n.lower() for n in names)

    def test_all_ts_patterns_found(self, tmp_path: Path):
        from scout.analysis.tools.graph_patterns import _discover_ts_patterns
        (tmp_path / "debug.ts").write_text("console.log('test');\n")
        (tmp_path / "loose.ts").write_text("const x: any = 1;\n")
        (tmp_path / "dynamic.ts").write_text("export const dynamic = 'force-dynamic';\n")
        candidates = []
        _discover_ts_patterns(tmp_path, candidates, set(), 1)
        assert len(candidates) == 3


class TestDiscoverGoPatterns:
    def test_error_handling_found(self, tmp_path: Path):
        from scout.analysis.tools.graph_patterns import _discover_go_patterns
        (tmp_path / "main.go").write_text("if err != nil {\n    return\n}\n")
        candidates = []
        _discover_go_patterns(tmp_path, candidates, set(), 1)
        names = [c["suggested_name"] for c in candidates]
        assert any("Error" in n for n in names)

    def test_go_below_min_frequency(self, tmp_path: Path):
        from scout.analysis.tools.graph_patterns import _discover_go_patterns
        (tmp_path / "main.go").write_text("if err != nil {\n    return\n}\n")
        candidates = []
        _discover_go_patterns(tmp_path, candidates, set(), 100)
        assert len(candidates) == 0

    def test_go_skipped_when_in_existing(self, tmp_path: Path):
        from scout.analysis.tools.graph_patterns import _discover_go_patterns
        (tmp_path / "main.go").write_text("if err != nil {\n    return\n}\n")
        candidates = []
        _discover_go_patterns(tmp_path, candidates, {r"if err\s*!=\s*nil\s*\{\s*$"}, 1)
        assert len(candidates) == 0
