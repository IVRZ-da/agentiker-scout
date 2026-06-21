"""Tests für tools/ui_discovery.py — UI-Layer-Erkennung mit tmp_path Fixtures."""

from __future__ import annotations

from pathlib import Path

# sys.modules Mocks werden von conftest.py gesetzt
from scout.analysis.tools.ui_discovery import (
    UiLayer,
    _detect_go_handler,
    _detect_medusa_admin,
    _detect_medusa_api,
    _detect_nextjs,
    _detect_vite,
    _get_go_modules,
    _get_medusa_admin_routes,
    _get_medusa_api_routes,
    _get_medusa_modules,
    _get_nextjs_routes,
    discover_uis,
    summarize_ui_layers,
)

# ---------------------------------------------------------------------------
# Helper: minimale detectbare Projektstrukturen
# ---------------------------------------------------------------------------


def _create_nextjs_storefront(root: Path) -> Path:
    """Erzeugt eine minimal detectbare Next.js Storefront."""
    root.mkdir(parents=True)
    (root / "next.config.ts").write_text("")
    app_dir = root / "app"
    app_dir.mkdir(parents=True)
    (app_dir / "page.tsx").write_text("export default function Home() {}")
    return root


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


def _create_go_backend(root: Path, modules=None) -> Path:
    """Erzeugt eine minimal detectbare Go-Backend-Struktur."""
    root.mkdir(parents=True)
    (root / "go.mod").write_text("module test\n")
    core_dir = root / "internal" / "core"
    core_dir.mkdir(parents=True)
    (core_dir / "handler.go").write_text("package core")
    if modules:
        for mod in modules:
            (core_dir / mod).mkdir()
    return root


def _create_monorepo(tmp_path: Path) -> Path:
    """Erzeugt eine minimale Multi-UI-Monorepo-Struktur."""
    project = tmp_path / "monorepo"
    project.mkdir()
    apps = project / "apps"
    apps.mkdir()

    # Storefront (Next.js)
    _create_nextjs_storefront(apps / "storefront")
    for sub in ["products", "orders"]:
        d = apps / "storefront" / "app" / sub
        d.mkdir(parents=True)
        (d / "page.tsx").write_text("export default function Page() {}")

    # Backend (Medusa Admin + API + Modules)
    _create_medusa_backend(
        apps / "backend",
        admin_routes=["products", "orders", "seo", "invoice"],
        api_routes=["store/products", "admin/orders"],
        modules=["product", "order", "customer", "seo"],
    )

    return project


# ===========================================================================
# Tests
# ===========================================================================


class TestUiLayerDataclass:
    """UiLayer Dataclass basics."""

    def test_create_ui_layer(self):
        layer = UiLayer(path="/tmp/test", ui_type="nextjs", name="test")
        assert layer.path == "/tmp/test"
        assert layer.ui_type == "nextjs"
        assert layer.name == "test"
        assert layer.routes == []
        assert layer.modules == []
        assert layer.markers == []

    def test_to_dict(self):
        layer = UiLayer(path="/tmp", ui_type="nextjs", name="x", routes=[{"path": "/"}])
        d = layer.to_dict()
        assert d["path"] == "/tmp"
        assert d["ui_type"] == "nextjs"
        assert d["name"] == "x"
        assert len(d["routes"]) == 1


class TestDetectionWithFixtures:
    """UI-Layer-Erkennung mit tmp_path Fixtures statt hardcodierten Pfaden."""

    def test_detect_nextjs(self, tmp_path):
        root = _create_nextjs_storefront(tmp_path / "storefront")
        assert _detect_nextjs(str(root))

    def test_detect_nextjs_without_config(self, tmp_path):
        """Ohne next.config.* sollte _detect_nextjs False liefern."""
        root = tmp_path / "no-config"
        root.mkdir()
        app_dir = root / "app"
        app_dir.mkdir(parents=True)
        (app_dir / "page.tsx").write_text("export default function Page() {}")
        assert not _detect_nextjs(str(root))

    def test_detect_medusa_admin(self, tmp_path):
        root = _create_medusa_backend(tmp_path / "backend", admin_routes=["seo"])
        assert _detect_medusa_admin(str(root))

    def test_detect_medusa_admin_no_routes(self, tmp_path):
        """Leeres src/admin/ ohne page.tsx sollte False liefern."""
        root = tmp_path / "backend"
        root.mkdir()
        (root / "src" / "admin" / "routes").mkdir(parents=True)
        assert not _detect_medusa_admin(str(root))

    def test_detect_medusa_api(self, tmp_path):
        root = _create_medusa_backend(tmp_path / "backend", api_routes=["store/products"])
        assert _detect_medusa_api(str(root))

    def test_detect_go_handler(self, tmp_path):
        root = _create_go_backend(tmp_path / "go-backend")
        assert _detect_go_handler(str(root))

    def test_detect_vite(self, tmp_path):
        root = tmp_path / "vite-project"
        root.mkdir()
        assert not _detect_vite(str(root))
        (root / "vite.config.ts").write_text("")
        assert _detect_vite(str(root))

    def test_discover_all_three_ui_types(self, tmp_path):
        """discover_uis erkennt Next.js + Medusa Admin + Medusa API im Monorepo."""
        project = _create_monorepo(tmp_path)
        layers = discover_uis(str(project))
        types = {l.ui_type for l in layers}
        assert "medusa-admin" in types
        assert "medusa-api" in types
        assert "nextjs" in types

    def test_discover_go_and_nextjs(self, tmp_path):
        """discover_uis erkennt Go Handler + Next.js in einem Projekt."""
        project = tmp_path / "dual-project"
        project.mkdir()
        apps = project / "apps"
        apps.mkdir()

        _create_go_backend(apps / "backend", modules=["product", "order"])
        _create_nextjs_storefront(apps / "admin")

        layers = discover_uis(str(project))
        types = {l.ui_type for l in layers}
        assert "go-handler" in types
        assert "nextjs" in types

    def test_admin_routes_extracted(self, tmp_path):
        """_get_medusa_admin_routes extrahiert korrekte Pfade."""
        backend = tmp_path / "backend"
        backend.mkdir()
        _create_medusa_backend(backend, admin_routes=["seo", "invoice", "brands"])
        routes = _get_medusa_admin_routes(str(backend))
        assert len(routes) == 3
        paths = {r["path"] for r in routes}
        assert "/seo" in paths
        assert "/invoice" in paths
        assert "/brands" in paths

    def test_api_routes_extracted(self, tmp_path):
        """_get_medusa_api_routes extrahiert korrekte Pfade."""
        backend = tmp_path / "backend"
        backend.mkdir()
        _create_medusa_backend(backend, api_routes=["store/products", "admin/customers"])
        routes = _get_medusa_api_routes(str(backend))
        assert len(routes) == 2

    def test_nextjs_routes_extracted(self, tmp_path):
        """_get_nextjs_routes extrahiert alle page.tsx-Routen."""
        storefront = _create_nextjs_storefront(tmp_path / "storefront")
        for sub in ["products", "cart", "about"]:
            d = storefront / "app" / sub
            d.mkdir(parents=True)
            (d / "page.tsx").write_text("export default function Page() {}")
        routes = _get_nextjs_routes(str(storefront))
        assert len(routes) >= 4

    def test_medusa_modules(self, tmp_path):
        """_get_medusa_modules listet src/modules/ Verzeichnisse."""
        root = tmp_path / "backend"
        root.mkdir()
        _create_medusa_backend(root, modules=["product", "order", "customer"])
        modules = _get_medusa_modules(str(root))
        assert "product" in modules
        assert "order" in modules
        assert "customer" in modules

    def test_go_modules(self, tmp_path):
        """_get_go_modules listet internal/core/ Verzeichnisse."""
        root = _create_go_backend(tmp_path / "go-backend", modules=["product", "order", "user"])
        modules = _get_go_modules(str(root))
        assert len(modules) == 3
        assert "product" in modules
        assert "user" in modules

    def test_summary(self, tmp_path):
        """summarize_ui_layers erzeugt eine lesbare Zusammenfassung."""
        project = _create_monorepo(tmp_path)
        layers = discover_uis(str(project))
        summary = summarize_ui_layers(layers)
        assert "Routen:" in summary
        assert "Module:" in summary


class TestEdgeCases:
    """Edge-Case-Tests."""

    def test_nonexistent_path(self):
        layers = discover_uis("/nonexistent/path")
        assert layers == []

    def test_empty_dir(self, tmp_path):
        layers = discover_uis(str(tmp_path))
        assert isinstance(layers, list)

    def test_no_vite_detection(self, tmp_path):
        assert not _detect_vite(str(tmp_path))
