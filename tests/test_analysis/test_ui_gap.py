"""Tests für tools/ui_gap.py — analysis_ui_gap Tool-Handler mit tmp_path."""

from __future__ import annotations

from pathlib import Path

from scout.analysis.tools.mapping import build_coverage_matrix
from scout.analysis.tools.ui_discovery import discover_uis

# sys.modules Mocks werden von conftest.py gesetzt
from scout.analysis.tools.ui_gap import (
    _clean_matrix,
    _generate_mermaid,
    _generate_summary,
    analysis_ui_gap_tool,
)

# ---------------------------------------------------------------------------
# Helper: minimale detectbare Projektstruktur
# ---------------------------------------------------------------------------


def _build_minimal_multi_ui_project(tmp_path: Path) -> Path:
    """Erzeugt ein Multi-UI-Projekt (Medusa Admin + API + Next.js Storefront)."""
    project = tmp_path / "multi-ui-project"
    project.mkdir()
    apps = project / "apps"
    apps.mkdir()

    # Backend (Medusa Admin + API + Modules)
    backend = apps / "backend"
    backend.mkdir()
    for route in ["products", "orders", "seo", "invoice"]:
        d = backend / "src" / "admin" / "routes" / route
        d.mkdir(parents=True)
        (d / "page.tsx").write_text("export default function AdminPage() {}")
    for route in ["store/products", "admin/orders"]:
        d = backend / "src" / "api" / route
        d.mkdir(parents=True)
        (d / "route.ts").write_text("export async function GET() {}")
    for mod in ["product", "order", "customer", "seo"]:
        (backend / "src" / "modules" / mod).mkdir(parents=True)

    # Storefront (Next.js)
    storefront = apps / "storefront"
    storefront.mkdir()
    (storefront / "next.config.ts").write_text("")
    app_dir = storefront / "app"
    app_dir.mkdir()
    (app_dir / "page.tsx").write_text("export default function Home() {}")
    for sub in ["products", "orders"]:
        d = storefront / "app" / sub
        d.mkdir(parents=True)
        (d / "page.tsx").write_text("export default function Page() {}")

    return project


# ===========================================================================
# Tests
# ===========================================================================


class TestUiGapTool:
    """analysis_ui_gap_tool-Tests mit tmp_path Fixtures."""

    def test_text_format(self, tmp_path):
        project = _build_minimal_multi_ui_project(tmp_path)
        result = analysis_ui_gap_tool({"path": str(project), "format": "text"})
        assert "✅" in result or "Success" in result
        assert len(result) > 500

    def test_json_format(self, tmp_path):
        project = _build_minimal_multi_ui_project(tmp_path)
        result = analysis_ui_gap_tool({"path": str(project), "format": "json"})
        assert '"format": "json"' in result
        assert '"has_admin"' in result

    def test_mermaid_format(self, tmp_path):
        project = _build_minimal_multi_ui_project(tmp_path)
        result = analysis_ui_gap_tool({"path": str(project), "format": "mermaid"})
        assert "graph TD" in result
        assert "UI-Layer" in result

    def test_invalid_path(self):
        result = analysis_ui_gap_tool({"path": "/nonexistent"})
        assert "❌" in result or "Error" in result or "Path not found" in result

    def test_empty_path(self):
        result = analysis_ui_gap_tool({"path": ""})
        assert "❌" in result or "Error" in result or "Path is required" in result

    def test_without_storefront(self, tmp_path):
        project = _build_minimal_multi_ui_project(tmp_path)
        result = analysis_ui_gap_tool({
            "path": str(project),
            "include_storefront": False,
        })
        assert "✅" in result or "Success" in result


class TestUiGapHelpers:
    """Helper-Tests mit tmp_path Fixtures."""

    def test_clean_matrix(self, tmp_path):
        project = _build_minimal_multi_ui_project(tmp_path)
        matrix = build_coverage_matrix(str(project))
        cleaned = _clean_matrix(matrix)
        assert "coverage" in cleaned
        assert "gaps" in cleaned
        assert "_meta" not in cleaned
        assert "_coverage" not in cleaned

    def test_clean_matrix_module_entries(self, tmp_path):
        project = _build_minimal_multi_ui_project(tmp_path)
        matrix = build_coverage_matrix(str(project))
        cleaned = _clean_matrix(matrix)
        for key in cleaned:
            if key in ("coverage", "gaps"):
                continue
            entry = cleaned[key]
            assert "has_admin" in entry
            assert "has_storefront" in entry

    def test_generate_mermaid(self, tmp_path):
        project = _build_minimal_multi_ui_project(tmp_path)
        matrix = build_coverage_matrix(str(project))
        diagram = _generate_mermaid(matrix, str(project))
        assert "graph TD" in diagram
        assert "UIs" in diagram
        assert "Coverage" in diagram

    def test_generate_summary(self, tmp_path):
        project = _build_minimal_multi_ui_project(tmp_path)
        matrix = build_coverage_matrix(str(project))
        layers = discover_uis(str(project))
        summary = _generate_summary(matrix, layers)
        assert "Backend-Module" in summary
        assert "Admin UI" in summary
