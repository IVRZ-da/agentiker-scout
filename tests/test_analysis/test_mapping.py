"""Tests für tools/mapping.py — Coverage-Matrix und Gap-Detection mit tmp_path."""

from __future__ import annotations

from pathlib import Path

# sys.modules Mocks werden von conftest.py gesetzt
from scout.analysis.tools.mapping import (
    _module_to_route_segments,
    _route_matches_module,
    build_coverage_matrix,
    format_coverage_report,
    GAP_CRITICAL,
    GAP_WARNING,
    GAP_ORPHAN,
    GAP_MISSING_DETAIL,
)


# ---------------------------------------------------------------------------
# Helper: minimale detectbare Projektstrukturen
# ---------------------------------------------------------------------------


def _create_medusa_backend(root: Path, admin_routes=None,
                           api_routes=None, modules=None) -> Path:
    """Erzeugt eine minimal detectbare Medusa Backend-Struktur."""
    root.mkdir(parents=True, exist_ok=True)
    if admin_routes:
        for route in admin_routes:
            d = root / "src" / "admin" / "routes" / route
            d.mkdir(parents=True)
            (d / "page.tsx").write_text("export default function AdminPage() {}")
    if api_routes:
        for route in api_routes:
            d = root / "src" / "api" / route
            d.mkdir(parents=True)
            (d / "route.ts").write_text("export async function GET() {}")
    if modules:
        for mod in modules:
            (root / "src" / "modules" / mod).mkdir(parents=True)
    return root


def _build_minimal_multi_ui_project(tmp_path: Path) -> Path:
    """Erzeugt ein Multi-UI-Projekt (Medusa Admin + API + Next.js Storefront)."""
    project = tmp_path / "multi-ui-project"
    project.mkdir()
    apps = project / "apps"
    apps.mkdir()

    # Backend (Medusa Admin + API + Modules)
    _create_medusa_backend(
        apps / "backend",
        admin_routes=["products", "orders", "seo", "invoice"],
        api_routes=["store/products", "admin/orders"],
        modules=["product", "order", "customer", "seo"],
    )

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


def _build_minimal_go_project(tmp_path: Path) -> Path:
    """Erzeugt ein reines Go-Projekt ohne UI-Layer."""
    project = tmp_path / "go-project"
    project.mkdir()
    (project / "go.mod").write_text("module test\n")
    core_dir = project / "internal" / "core"
    core_dir.mkdir(parents=True)
    (core_dir / "handler.go").write_text("package core")
    for mod in ["product", "order", "user"]:
        (core_dir / mod).mkdir()
    return project


def _build_minimal_go_with_storefront(tmp_path: Path) -> Path:
    """Erzeugt ein Go-Projekt mit Next.js Storefront."""
    project = tmp_path / "go-storefront"
    project.mkdir()
    apps = project / "apps"
    apps.mkdir()

    # Go Backend
    go_backend = apps / "backend"
    go_backend.mkdir()
    (go_backend / "go.mod").write_text("module test\n")
    core_dir = go_backend / "internal" / "core"
    core_dir.mkdir(parents=True)
    (core_dir / "handler.go").write_text("package core")
    for mod in ["product", "order"]:
        (core_dir / mod).mkdir()

    # Next.js Storefront
    storefront = apps / "storefront"
    storefront.mkdir()
    (storefront / "next.config.ts").write_text("")
    app_dir = storefront / "app"
    app_dir.mkdir()
    (app_dir / "page.tsx").write_text("export default function Home() {}")
    for sub in ("products", "orders"):
        (app_dir / sub).mkdir()
        (app_dir / sub / "page.tsx").write_text(f"export default function {sub.title()}() {{}}")

    return project


# ===========================================================================
# Tests
# ===========================================================================


class TestNameMatching:
    """Modul-Name → Route-Segment Matching."""

    def test_simple_module(self):
        segs = _module_to_route_segments("brand")
        assert "brand" in segs
        assert "brands" in segs

    def test_hyphen_module(self):
        segs = _module_to_route_segments("hero-banner")
        assert "hero-banner" in segs
        assert "hero_banner" in segs

    def test_exact_route_match(self):
        assert _route_matches_module("/brands", "brand")
        assert _route_matches_module("/seo", "seo")

    def test_subroute_match(self):
        assert _route_matches_module("/seo/products", "seo")
        assert _route_matches_module("/blog/posts", "blog")
        assert _route_matches_module("/gdpr/consents", "gdpr")

    def test_no_false_positive(self):
        assert not _route_matches_module("/agent-channels", "agent")
        assert not _route_matches_module("/agent-shop-manager", "agent")
        assert not _route_matches_module("/channel-product", "product")

    def test_plural_match(self):
        assert _route_matches_module("/bundles", "bundle")
        assert _route_matches_module("/invoices", "invoice")

    def test_alias_match(self):
        assert _route_matches_module("/brands", "brand")
        assert _route_matches_module("/bundles", "bundle")
        assert _route_matches_module("/invoices", "invoice")

    def test_no_implicit_alias(self):
        assert not _route_matches_module("/legal-texts", "legal")
        assert _route_matches_module("/legal-texts", "legal-texts")


class TestCoverageMatrix:
    """Coverage-Matrix-Tests mit tmp_path Fixtures."""

    def test_matrix_structure(self, tmp_path):
        project = _build_minimal_multi_ui_project(tmp_path)
        matrix = build_coverage_matrix(str(project))
        assert "_coverage" in matrix
        assert "_gaps" in matrix
        assert "_meta" in matrix

    def test_coverage_stats(self, tmp_path):
        project = _build_minimal_multi_ui_project(tmp_path)
        matrix = build_coverage_matrix(str(project))
        cov = matrix["_coverage"]
        assert cov["total_modules"] >= 2
        assert cov["admin_coverage_pct"] > 0
        assert cov["storefront_coverage_pct"] > 0

    def test_admin_coverage(self, tmp_path):
        project = _build_minimal_multi_ui_project(tmp_path)
        matrix = build_coverage_matrix(str(project))
        cov = matrix["_coverage"]
        assert cov["with_admin"] >= 2

    def test_has_gaps(self, tmp_path):
        project = _build_minimal_multi_ui_project(tmp_path)
        matrix = build_coverage_matrix(str(project))
        assert len(matrix["_gaps"]) > 0

    def test_gap_types(self, tmp_path):
        project = _build_minimal_multi_ui_project(tmp_path)
        matrix = build_coverage_matrix(str(project))
        gap_types = {g["type"] for g in matrix["_gaps"]}
        assert GAP_CRITICAL in gap_types or GAP_WARNING in gap_types

    def test_go_matrix_structure(self, tmp_path):
        project = _build_minimal_go_project(tmp_path)
        matrix = build_coverage_matrix(str(project))
        assert "_coverage" in matrix
        assert "_gaps" in matrix

    def test_go_module_count(self, tmp_path):
        project = _build_minimal_go_project(tmp_path)
        matrix = build_coverage_matrix(str(project))
        cov = matrix["_coverage"]
        assert cov["total_modules"] >= 2

    def test_go_gaps_exist(self, tmp_path):
        project = _build_minimal_go_project(tmp_path)
        matrix = build_coverage_matrix(str(project))
        assert len(matrix["_gaps"]) > 0

    def test_go_with_storefront_coverage(self, tmp_path):
        project = _build_minimal_go_with_storefront(tmp_path)
        matrix = build_coverage_matrix(str(project))
        cov = matrix["_coverage"]
        assert cov["total_modules"] >= 2
        assert cov["with_storefront"] >= 1

    def test_module_entries_structure(self, tmp_path):
        project = _build_minimal_multi_ui_project(tmp_path)
        matrix = build_coverage_matrix(str(project))
        for key, entry in matrix.items():
            if key.startswith("_"):
                continue
            assert "has_admin" in entry
            assert "has_storefront" in entry
            assert "has_api" in entry
            assert "admin_pages" in entry

    def test_gap_detail_is_string(self, tmp_path):
        project = _build_minimal_multi_ui_project(tmp_path)
        matrix = build_coverage_matrix(str(project))
        for gap in matrix["_gaps"]:
            assert isinstance(gap["type"], str)
            assert isinstance(gap["module"], str)
            assert isinstance(gap["detail"], str)


class TestCoverageReport:
    """Coverage-Report-Tests mit tmp_path Fixtures."""

    def test_report_generates(self, tmp_path):
        project = _build_minimal_multi_ui_project(tmp_path)
        matrix = build_coverage_matrix(str(project))
        report = format_coverage_report(matrix)
        assert len(report) > 100
        assert "UI Gap Analysis Report" in report
        assert "Coverage" in report

    def test_report_shows_modules(self, tmp_path):
        project = _build_minimal_multi_ui_project(tmp_path)
        matrix = build_coverage_matrix(str(project))
        report = format_coverage_report(matrix)
        assert "✅A" in report or "❌A" in report

    def test_report_shows_gaps(self, tmp_path):
        project = _build_minimal_multi_ui_project(tmp_path)
        matrix = build_coverage_matrix(str(project))
        report = format_coverage_report(matrix)
        assert "🔴" in report or "🟡" in report or "🟢" in report
