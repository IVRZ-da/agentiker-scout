"""Coverage-Ergänzung für scout/analysis/tools/ui_discovery.py.

Schwerpunkt: Fehlerpfade (PermissionError, kaputte package.json), Route-Parsing
für Auth-Gruppen/Detail-Routen, Monorepo-Scan über apps/ + packages/, Go-Routen
und die Summary-Formatierung.

Alle Projektstrukturen entstehen in tmp_path.
"""

from __future__ import annotations

import os

from scout.analysis.tools import ui_discovery as ui

# ---------------------------------------------------------------------------
# Helfer
# ---------------------------------------------------------------------------


def _nextjs_project(root, with_config=True, with_middleware=False, package_json=None):
    root.mkdir(parents=True, exist_ok=True)
    if with_config:
        (root / "next.config.ts").write_text("")
    if with_middleware:
        (root / "middleware.ts").write_text("")
    if package_json is not None:
        (root / "package.json").write_text(package_json)
    app = root / "app"
    app.mkdir(exist_ok=True)
    (app / "page.tsx").write_text("export default function Home() {}")
    return root


def _raiser(*_a, **_kw):
    raise PermissionError("kein Zugriff")


# ---------------------------------------------------------------------------
# PermissionError-Pfade beim Datei-Scan
# ---------------------------------------------------------------------------


def test_find_page_files_swallows_permission_error(tmp_path, monkeypatch):
    monkeypatch.setattr(ui.os, "walk", _raiser)
    assert ui._find_page_files(str(tmp_path)) == []


def test_find_route_files_swallows_permission_error(tmp_path, monkeypatch):
    monkeypatch.setattr(ui.os, "walk", _raiser)
    assert ui._find_route_files(str(tmp_path)) == []


def test_medusa_modules_permission_error_returns_empty(tmp_path, monkeypatch):
    modules = tmp_path / "src" / "modules"
    modules.mkdir(parents=True)

    def _listdir(path):
        if str(path).endswith("modules"):
            raise PermissionError("kein Zugriff")
        return os.listdir(path)

    monkeypatch.setattr(ui.os, "listdir", _listdir)
    assert ui._get_medusa_modules(str(tmp_path)) == []


def test_go_modules_permission_error_returns_empty(tmp_path, monkeypatch):
    (tmp_path / "internal" / "core").mkdir(parents=True)

    def _listdir(path):
        if str(path).endswith("core"):
            raise PermissionError("kein Zugriff")
        return os.listdir(path)

    monkeypatch.setattr(ui.os, "listdir", _listdir)
    assert ui._get_go_modules(str(tmp_path)) == []


def test_discover_uis_tolerates_unreadable_apps_dir(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    (project / "apps").mkdir(parents=True)
    (project / "packages").mkdir()
    _nextjs_project(project / "storefront")

    monkeypatch.setattr(ui.os, "listdir", _raiser)

    # apps/ und packages/ sind nicht lesbar → Root-Scan liefert trotzdem Treffer
    layers = ui.discover_uis(str(project))

    assert [layer.ui_type for layer in layers] == ["nextjs"]


def test_discover_uis_missing_root_returns_empty(tmp_path):
    assert ui.discover_uis(str(tmp_path / "gibt-es-nicht")) == []


# ---------------------------------------------------------------------------
# Framework-Erkennung
# ---------------------------------------------------------------------------


def test_nextjs_detected_via_dependency_without_config(tmp_path):
    project = _nextjs_project(
        tmp_path / "store",
        with_config=False,
        package_json='{"dependencies": {"next": "^16.0.0", "react": "^19"}}',
    )
    assert ui._detect_nextjs(str(project)) is True


def test_nextjs_broken_package_json_is_ignored(tmp_path):
    project = _nextjs_project(
        tmp_path / "store",
        with_config=False,
        package_json="{ das ist kein json",
    )
    # Ohne next-Dependency und ohne next.config → keine Erkennung
    assert ui._detect_nextjs(str(project)) is False


def test_detectors_reject_plain_directory(tmp_path):
    project = tmp_path / "leer"
    project.mkdir()
    assert ui._detect_medusa_admin(str(project)) is False
    assert ui._detect_medusa_api(str(project)) is False
    assert ui._detect_go_handler(str(project)) is False
    assert ui._detect_vite(str(project)) is False


# ---------------------------------------------------------------------------
# Route-Parsing
# ---------------------------------------------------------------------------


class TestNextRouteParsing:
    def test_protected_group_marks_route(self):
        route = ui._parse_nextjs_route("app/(protected)/orders/page.tsx")

        assert route["auth_status"] == "protected"
        assert route["groups"] == ["protected"]
        assert route["route_type"] == "page"

    def test_guest_group_marks_route(self):
        route = ui._parse_nextjs_route("app/(guest)/login/page.tsx")

        assert route["auth_status"] == "guest"

    def test_dynamic_segment_is_detail_view(self):
        route = ui._parse_nextjs_route("app/products/[handle]/page.tsx")

        assert route["params"] == ["handle"]
        assert route["route_type"] == "detail"

    def test_locale_only_is_not_detail_view(self):
        route = ui._parse_nextjs_route("app/[locale]/about/page.tsx")

        assert route["params"] == ["locale"]
        assert route["route_type"] == "page"


def test_api_route_params_extracted():
    route = ui._parse_api_route("api/store/products/[id]/route.ts")

    assert route["path"] == "/api/store/products/[id]"
    assert route["params"] == ["id"]
    assert route["route_type"] == "api"


# ---------------------------------------------------------------------------
# Route-Discovery ohne passende Verzeichnisse
# ---------------------------------------------------------------------------


def test_route_collectors_return_empty_without_dirs(tmp_path):
    root = str(tmp_path)
    assert ui._get_nextjs_routes(root) == []
    assert ui._get_medusa_admin_routes(root) == []
    assert ui._get_medusa_api_routes(root) == []
    assert ui._get_go_modules(root) == []


def test_nextjs_routes_from_src_app(tmp_path):
    project = tmp_path / "with-src"
    (project / "src" / "app" / "shop").mkdir(parents=True)
    (project / "src" / "app" / "shop" / "page.tsx").write_text("")

    routes = ui._get_nextjs_routes(str(project))

    assert len(routes) == 1
    assert routes[0]["path"] == "shop"


# ---------------------------------------------------------------------------
# Monorepo-Scan
# ---------------------------------------------------------------------------


def test_packages_and_known_dirs_are_scanned(tmp_path):
    project = tmp_path / "mono"
    project.mkdir()

    pkg = project / "packages" / "ui-kit"
    pkg.mkdir(parents=True)
    (pkg / "vite.config.ts").write_text("")

    storefront = _nextjs_project(project / "storefront", with_middleware=True)

    layers = ui.discover_uis(str(project))
    by_type = {layer.ui_type: layer for layer in layers}

    assert by_type["vite"].name == "ui-kit"
    assert "middleware.ts" in by_type["nextjs"].markers
    assert by_type["nextjs"].path == str(storefront)


def test_dotted_subdirs_are_ignored(tmp_path):
    project = tmp_path / "mono"
    (project / "apps" / ".cache").mkdir(parents=True)
    (project / "packages" / ".tmp").mkdir(parents=True)

    assert ui.discover_uis(str(project)) == []


def test_vite_marker_does_not_duplicate_existing_layer(tmp_path):
    project = _nextjs_project(tmp_path / "hybrid")
    (project / "vite.config.js").write_text("")

    layers = ui.discover_uis(str(project))

    assert [layer.ui_type for layer in layers] == ["nextjs"]


# ---------------------------------------------------------------------------
# Go-Routen
# ---------------------------------------------------------------------------


def test_go_routes_extracted_from_router_files(tmp_path):
    project = tmp_path / "go-shop"
    (project / "internal" / "api").mkdir(parents=True)
    (project / "go.mod").write_text("module example.test/shop\n")
    (project / "internal" / "api" / "router.go").write_text(
        "\n".join([
            'router.HandleFunc("/products", listProducts)',
            'mux.GET("/products/{id}", getProduct)',
            'r.POST(`/orders`, createOrder)',
            "// Route: /health",
            'router.HandleFunc("/products", listProductsAgain)',
        ])
    )

    routes = ui._find_go_routes(str(project))
    paths = [route["path"] for route in routes]

    assert "/products" in paths
    assert "/products/{id}" in paths
    assert "/orders" in paths
    assert "/health" in paths
    # Duplikate werden nur einmal aufgenommen
    assert paths.count("/products") == 1
    detail = next(r for r in routes if r["path"] == "/products/{id}")
    assert detail["params"] == ["id"]
    assert detail["route_type"] == "go-api"
    assert detail["source_file"].endswith("router.go")


def test_go_route_collection_skips_unreadable_file(tmp_path):
    project = tmp_path / "go-shop"
    api = project / "internal" / "api"
    api.mkdir(parents=True)
    (project / "go.mod").write_text("module example.test/shop\n")
    broken = api / "router.go"
    broken.write_text('router.GET("/secret", handler)')
    broken.chmod(0o000)
    try:
        routes = ui._find_go_routes(str(project))
    finally:
        broken.chmod(0o644)

    assert routes == []


def test_go_backend_layer_includes_modules_and_markers(tmp_path):
    project = tmp_path / "go-shop"
    (project / "internal" / "core" / "orders").mkdir(parents=True)
    (project / "internal" / "core" / "products").mkdir()
    (project / "go.mod").write_text("module example.test/shop\n")

    layers = ui.discover_uis(str(project))

    assert len(layers) == 1
    layer = layers[0]
    assert layer.ui_type == "go-handler"
    assert layer.modules == ["orders", "products"]
    assert layer.markers == ["go.mod", "internal/core/"]


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def test_summary_empty_layers():
    assert ui.summarize_ui_layers([]) == "Keine UI-Layer gefunden."


def test_summary_lists_all_modules_up_to_ten():
    layer = ui.UiLayer(
        path="/tmp/x",
        ui_type="nextjs",
        name="shop",
        routes=[{"path": "/"}],
        modules=[f"mod{i}" for i in range(12)],
        markers=["app/"],
    )

    summary = ui.summarize_ui_layers([layer])

    assert "Gefundene UI-Layer: 1" in summary
    assert "mod0" in summary
    assert "mod9" in summary
    assert "und 2 weitere" in summary
    assert "Gesamt: 1 Routen, 12 Module" in summary


def test_layer_to_dict_roundtrip(tmp_path):
    layer = ui.UiLayer(path=str(tmp_path), ui_type="vite", name="frontend")

    as_dict = layer.to_dict()

    assert as_dict["ui_type"] == "vite"
    assert as_dict["routes"] == []
    assert as_dict["modules"] == []
