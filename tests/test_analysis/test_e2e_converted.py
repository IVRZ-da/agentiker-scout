"""Konvertierte E2E-Tests aus test_e2e/test_e2e_tools.py als Unit-Tests.

Testet analysis_* Tools gegen sample-Dateien in tmp_path statt dem
echten Plugin-Verzeichnis. KEIN E2E_TEST Gate, KEIN sys.path Hack.

Nur Tests die NICHT bereits in test_analysis_tools.py abgedeckt sind:
  - inspect auf multi-symbol sample file
  - deadcode auf Directory mit sample files
  - architecture auf Directory mit sample files
  - performance auf sample file
  - ask mit Frage zu sample project
  - graph aus inspect result (unique flow)
"""

from __future__ import annotations

import json
import os

# sys.modules Mocks werden von tests/conftest.py gesetzt
from scout.analysis.analysis_tools import (
    analysis_inspect_tool,
    analysis_deadcode_tool,
    analysis_architecture_tool,
    analysis_performance_tool,
    analysis_ask_tool,
    analysis_graph_tool,
)


# ---------------------------------------------------------------------------
# Helper: sample project anlegen
# ---------------------------------------------------------------------------


def _create_sample_project(tmp_path) -> str:
    """Erzeugt sample.py + sample.ts und eine subdir/ im tmp_path."""
    (tmp_path / "sample.py").write_text(
        '"""Sample module for testing."""\n'
        "\n"
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        'GLOBAL_CONST = "hello"\n'
        "\n"
        "\n"
        "class Calculator:\n"
        '    """A simple calculator."""\n'
        "\n"
        "    def add(self, a: int, b: int) -> int:\n"
        '        """Add two numbers."""\n'
        "        return a + b\n"
        "\n"
        "    def subtract(self, a: int, b: int) -> int:\n"
        "        return a - b\n"
        "\n"
        "\n"
        "def helper(value: str) -> str:\n"
        '    """A helper function."""\n'
        "    return value.upper()\n"
    )

    (tmp_path / "sample.ts").write_text(
        "export interface User {\n"
        "  name: string;\n"
        "  age: number;\n"
        "}\n"
        "\n"
        "export function greet(name: string): string {\n"
        '  return `Hello ${name}`;\n'
        "}\n"
        "\n"
        "export class UserService {\n"
        "  async getUsers(): Promise<User[]> {\n"
        "    return [];\n"
        "  }\n"
        "}\n"
    )

    sub = tmp_path / "subdir"
    sub.mkdir(exist_ok=True)
    (sub / "__init__.py").write_text("# subpackage\n")
    (sub / "module.py").write_text(
        "from ..sample import Calculator\n"
        "\n"
        "\n"
        "def use_calc() -> int:\n"
        "    c = Calculator()\n"
        "    return c.add(1, 2)\n"
    )

    return str(tmp_path)


# ===========================================================================
# Tests: analysis_inspect on sample file
# ===========================================================================


class TestInspectOnSampleFile:
    """analysis_inspect_tool gegen eine sample.py mit mehreren Symbolen."""

    def test_inspect_returns_summary_or_symbols(self, tmp_path):
        _create_sample_project(tmp_path)
        result = json.loads(
            analysis_inspect_tool(
                {"path": os.path.join(tmp_path, "sample.py"), "depth": 1}
            )
        )
        assert result.get("status") != "error", f"Got error: {result}"
        assert "symbols" in result or "summary" in result, (
            f"Expected symbols or summary, got keys: {list(result.keys())}"
        )

    def test_inspect_on_empty_py_file(self, tmp_path):
        (tmp_path / "empty.py").write_text("")
        result = json.loads(
            analysis_inspect_tool({"path": os.path.join(tmp_path, "empty.py"), "depth": 1})
        )
        assert result.get("status") != "error", f"Got error: {result}"

    def test_inspect_on_ts_file(self, tmp_path):
        _create_sample_project(tmp_path)
        result = json.loads(
            analysis_inspect_tool(
                {"path": os.path.join(tmp_path, "sample.ts"), "depth": 1}
            )
        )
        assert result.get("status") != "error", f"Got error: {result}"


# ===========================================================================
# Tests: analysis_deadcode on sample project
# ===========================================================================


class TestDeadcodeOnSampleProject:
    """analysis_deadcode_tool gegen ein sample Directory."""

    def test_deadcode_imports_on_directory(self, tmp_path):
        _create_sample_project(tmp_path)
        result = json.loads(
            analysis_deadcode_tool({"path": str(tmp_path), "kinds": ["imports"]})
        )
        assert result.get("status") != "error", f"Got error: {result}"

    def test_deadcode_all_kinds_on_directory(self, tmp_path):
        _create_sample_project(tmp_path)
        result = json.loads(
            analysis_deadcode_tool({"path": str(tmp_path), "kinds": ["all"]})
        )
        assert result.get("status") != "error", f"Got error: {result}"

    def test_deadcode_functions_on_directory(self, tmp_path):
        _create_sample_project(tmp_path)
        result = json.loads(
            analysis_deadcode_tool({"path": str(tmp_path), "kinds": ["functions"]})
        )
        assert result.get("status") != "error", f"Got error: {result}"


# ===========================================================================
# Tests: analysis_architecture on sample project
# ===========================================================================


class TestArchitectureOnSampleProject:
    """analysis_architecture_tool gegen ein sample Directory."""

    def test_architecture_text_on_directory(self, tmp_path):
        _create_sample_project(tmp_path)
        result = json.loads(
            analysis_architecture_tool(
                {"path": str(tmp_path), "format": "text", "depth": 1}
            )
        )
        assert result.get("status") != "error", f"Got error: {result}"

    def test_architecture_mermaid_on_directory(self, tmp_path):
        _create_sample_project(tmp_path)
        result = json.loads(
            analysis_architecture_tool(
                {"path": str(tmp_path), "format": "mermaid", "depth": 1}
            )
        )
        assert result.get("status") != "error", f"Got error: {result}"

    def test_architecture_depth_2(self, tmp_path):
        _create_sample_project(tmp_path)
        result = json.loads(
            analysis_architecture_tool(
                {"path": str(tmp_path), "depth": 2}
            )
        )
        assert result.get("status") != "error", f"Got error: {result}"
        assert "cycles" in result.get("sections", {})


# ===========================================================================
# Tests: analysis_performance on sample file
# ===========================================================================


class TestPerformanceOnSampleFile:
    """analysis_performance_tool gegen eine sample.py."""

    def test_performance_on_sample_py(self, tmp_path):
        _create_sample_project(tmp_path)
        result = json.loads(
            analysis_performance_tool(
                {"path": os.path.join(tmp_path, "sample.py")}
            )
        )
        assert result.get("status") != "error", f"Got error: {result}"

    def test_performance_on_subdir(self, tmp_path):
        _create_sample_project(tmp_path)
        result = json.loads(
            analysis_performance_tool({"path": str(tmp_path)})
        )
        assert result.get("status") != "error", f"Got error: {result}"


# ===========================================================================
# Tests: analysis_ask about sample project
# ===========================================================================


class TestAskAboutSampleProject:
    """analysis_ask_tool mit Frage zu sample project (mit path)."""

    def test_ask_with_path_to_project(self, tmp_path):
        _create_sample_project(tmp_path)
        result = json.loads(
            analysis_ask_tool(
                {
                    "question": "What does this project provide?",
                    "path": str(tmp_path),
                }
            )
        )
        assert result.get("status") != "error", f"Got error: {result}"
        assert "question" in result

    def test_ask_about_symbol_in_project(self, tmp_path):
        _create_sample_project(tmp_path)
        result = json.loads(
            analysis_ask_tool(
                {
                    "question": "Describe the Calculator class",
                    "path": str(tmp_path),
                }
            )
        )
        assert result.get("status") != "error", f"Got error: {result}"


# ===========================================================================
# Tests: analysis_graph from inspect result (unique flow)
# ===========================================================================


class TestGraphFromInspect:
    """analysis_graph_tool mit realem inspect-report aus sample file."""

    def test_graph_dependency_from_inspect(self, tmp_path):
        _create_sample_project(tmp_path)
        report = json.loads(
            analysis_inspect_tool(
                {"path": os.path.join(tmp_path, "sample.py"), "depth": 1}
            )
        )
        assert report.get("status") != "error", f"Inspect failed: {report}"
        result = json.loads(
            analysis_graph_tool({"report": report, "type": "dependency"})
        )
        assert result.get("status") != "error", f"Graph failed: {result}"

    def test_graph_summary_from_inspect(self, tmp_path):
        _create_sample_project(tmp_path)
        report = json.loads(
            analysis_inspect_tool(
                {"path": os.path.join(tmp_path, "sample.py"), "depth": 1}
            )
        )
        assert report.get("status") != "error", f"Inspect failed: {report}"
        result = json.loads(
            analysis_graph_tool({"report": report, "type": "summary"})
        )
        assert result.get("status") != "error", f"Graph failed: {result}"
