"""Tests für tools/extractors/ — alle 4 Extraktoren (tmp_path basiert).

Erzeugt minimale Projekt-Strukturen in tmp_path statt auf
echte Repos (ivory-green-poc / agentic-shop) angewiesen zu sein.
"""

from __future__ import annotations

import json
from pathlib import Path

# sys.modules Mocks werden von conftest.py gesetzt
from scout.analysis.tools.extractors import go_handler, medusa_admin, medusa_api, nextjs

# ===================================================================
# TestNextJsExtractor
# ===================================================================


class TestNextJsExtractor:
    """Next.js Extractor mit tmp_path — minimale Projekt-Strukturen."""

    # ------------------------------------------------------------------
    # Hilfs-Funktionen
    # ------------------------------------------------------------------

    @staticmethod
    def _write(base: Path, *parts: str, content: str = "") -> None:
        """Schreibt eine Datei und erzeugt Eltern-Verzeichnisse."""
        target = base.joinpath(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def _create_nextjs_with_config(self, base: Path) -> None:
        """Erzeugt next.config.ts + app/page.tsx."""
        self._write(base, "app", "page.tsx", content="export default function Home() { return null }")
        self._write(base, "next.config.ts", content="/** @type {import('next').NextConfig} */\nmodule.exports = {}")

    def _create_nextjs_with_package_json(self, base: Path) -> None:
        """Erzeugt package.json (mit 'next' dep) + app/page.tsx."""
        self._write(base, "app", "page.tsx", content="export default function Home() { return null }")
        self._write(base, "package.json", content=json.dumps({"dependencies": {"next": "14.0.0"}}))

    def _create_extract_structure(self, base: Path) -> None:
        """Erzeugt eine Next.js-Struktur mit verschiedenen Route-Typen.

        Erstellte Routen:
          /, /dashboard, /products/[id], /categories/[slug],
          /items, /settings, /about, /users/[userId]/posts/[postId]
        """
        self._create_nextjs_with_config(base)

        self._write(base, "app", "dashboard", "page.tsx",
                     content="export default function Dashboard() { return null }")
        self._write(base, "app", "products", "[id]", "page.tsx",
                     content="export default function ProductPage() { return null }")
        self._write(base, "app", "categories", "[slug]", "page.tsx",
                     content="export default function CategoryPage() { return null }")
        self._write(base, "app", "users", "[userId]", "posts", "[postId]", "page.tsx",
                     content="export default function PostPage() { return null }")
        self._write(base, "app", "(store)", "items", "page.tsx",
                     content="export default function Items() { return null }")
        self._write(base, "app", "(protected)", "settings", "page.tsx",
                     content="export default function Settings() { return null }")
        self._write(base, "app", "about", "page.tsx",
                     content="export default function About() { return null }")

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_detect_nextjs(self, tmp_path: Path) -> None:
        """Prüft detect() mit next.config.ts und mit package.json."""
        # Fall 1: next.config.ts + app/page.tsx
        base1 = tmp_path / "with_config"
        self._create_nextjs_with_config(base1)
        assert nextjs.detect(str(base1))

        # Fall 2: package.json (mit "next" dep) + app/page.tsx
        base2 = tmp_path / "with_package"
        self._create_nextjs_with_package_json(base2)
        assert nextjs.detect(str(base2))

    def test_extract_routes(self, tmp_path: Path) -> None:
        """Prüft extrahierte Routen-Struktur."""
        base = tmp_path / "project"
        self._create_extract_structure(base)
        routes = nextjs.extract(str(base))

        # Erwarte mindestens die erstellten Routen
        assert len(routes) >= 8

        # Route-Struktur prüfen
        first = routes[0]
        assert "path" in first
        assert "params" in first
        assert "auth_status" in first
        assert "route_type" in first

    def test_has_protected_routes(self, tmp_path: Path) -> None:
        """Prüft Protected-Route Erkennung."""
        base = tmp_path / "project"
        self._create_extract_structure(base)
        routes = nextjs.extract(str(base))
        protected = [r for r in routes if r["auth_status"] == "protected"]
        assert len(protected) >= 1

    def test_has_detail_routes(self, tmp_path: Path) -> None:
        """Prüft Detail-Route Erkennung (mit Parametern ≠ locale)."""
        base = tmp_path / "project"
        self._create_extract_structure(base)
        routes = nextjs.extract(str(base))
        details = [r for r in routes if r["route_type"] == "detail"]
        assert len(details) >= 3

    def test_has_params(self, tmp_path: Path) -> None:
        """Prüft Parameter-Extraktion."""
        base = tmp_path / "project"
        self._create_extract_structure(base)
        routes = nextjs.extract(str(base))
        with_params = [r for r in routes if r["params"]]
        assert len(with_params) >= 3

    def test_has_route_groups(self, tmp_path: Path) -> None:
        """Prüft Route Group Extraktion."""
        base = tmp_path / "project"
        self._create_extract_structure(base)
        routes = nextjs.extract(str(base))
        with_groups = [r for r in routes if r["groups"]]
        assert len(with_groups) >= 2  # (store) und (protected)

    def test_extract_from_src_app(self, tmp_path: Path) -> None:
        """Prüft Extraktion aus src/app/ (alternative Struktur)."""
        base = tmp_path / "src_project"
        self._write(base, "next.config.ts", content="module.exports = {}")
        self._write(base, "src", "app", "page.tsx",
                     content="export default function Home() { return null }")
        self._write(base, "src", "app", "dashboard", "page.tsx",
                     content="export default function Dashboard() { return null }")
        routes = nextjs.extract(str(base))
        assert len(routes) >= 2

    def test_not_detect_wrong_dir(self, tmp_path: Path) -> None:
        """Leeres Verzeichnis wird nicht als Next.js erkannt."""
        assert not nextjs.detect(str(tmp_path))


# ===================================================================
# TestMedusaAdminExtractor
# ===================================================================


class TestMedusaAdminExtractor:
    """Medusa Admin Extractor mit tmp_path."""

    @staticmethod
    def _write(base: Path, *parts: str, content: str = "") -> None:
        target = base.joinpath(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def _create_admin_structure(self, base: Path) -> None:
        """Erzeugt src/admin/routes/ mit page.tsx Dateien."""
        for name in ["seo", "invoice", "brands", "bundles", "blog"]:
            self._write(base, "src", "admin", "routes", name, "page.tsx",
                         content="export default function Page() { return null }")

    def test_detect_admin(self, tmp_path: Path) -> None:
        """Prüft detect() auf src/admin/routes/."""
        base = tmp_path / "backend"
        self._create_admin_structure(base)
        assert medusa_admin.detect(str(base))

    def test_extract_routes(self, tmp_path: Path) -> None:
        """Prüft Extraktion aller Admin-Routen."""
        base = tmp_path / "backend"
        self._create_admin_structure(base)
        routes = medusa_admin.extract(str(base))
        assert len(routes) >= 5

    def test_route_structure(self, tmp_path: Path) -> None:
        """Prüft das Format extrahierter Routen."""
        base = tmp_path / "backend"
        self._create_admin_structure(base)
        routes = medusa_admin.extract(str(base))
        for r in routes:
            assert r["path"].startswith("/")
            assert "/" in r["path"]
            assert r["source_file"].endswith("page.tsx")

    def test_has_expected_routes(self, tmp_path: Path) -> None:
        """Prüft bekannte Route-Namen."""
        base = tmp_path / "backend"
        self._create_admin_structure(base)
        routes = medusa_admin.extract(str(base))
        paths = [r["path"] for r in routes]
        assert "/seo" in paths
        assert "/invoice" in paths
        assert "/brands" in paths
        assert "/bundles" in paths
        assert "/blog" in paths

    def test_has_nested_routes(self, tmp_path: Path) -> None:
        """Prüft verschachtelte Admin-Routen."""
        base = tmp_path / "backend"
        self._write(base, "src", "admin", "routes", "seo", "products", "page.tsx",
                     content="export default function Page() { return null }")
        self._write(base, "src", "admin", "routes", "seo", "pages", "page.tsx",
                     content="export default function Page() { return null }")
        routes = medusa_admin.extract(str(base))
        paths = [r["path"] for r in routes]
        assert "/seo/products" in paths
        assert "/seo/pages" in paths

    def test_not_detect_wrong_dir(self, tmp_path: Path) -> None:
        """Leeres Verzeichnis wird nicht als Medusa Admin erkannt."""
        assert not medusa_admin.detect(str(tmp_path))


# ===================================================================
# TestMedusaApiExtractor
# ===================================================================


class TestMedusaApiExtractor:
    """Medusa API Extractor mit tmp_path."""

    @staticmethod
    def _write(base: Path, *parts: str, content: str = "") -> None:
        target = base.joinpath(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def _create_api_structure(self, base: Path) -> None:
        """Erzeugt src/api/ mit route.ts Dateien."""
        self._write(base, "src", "api", "store", "products", "route.ts",
                     content="export async function GET() { return Response.json([]) }")
        self._write(base, "src", "api", "store", "categories", "route.ts",
                     content="export async function GET() { return Response.json([]) }")
        self._write(base, "src", "api", "store", "carts", "route.ts",
                     content="export async function GET() { return Response.json([]) }")
        self._write(base, "src", "api", "admin", "customers", "route.ts",
                     content="export async function GET() { return Response.json([]) }")
        self._write(base, "src", "api", "admin", "products", "route.ts",
                     content="export async function GET() { return Response.json([]) }")
        self._write(base, "src", "api", "store", "products", "[id]", "route.ts",
                     content="export async function GET() { return Response.json({}) }")
        self._write(base, "src", "api", "admin", "orders", "[id]", "route.ts",
                     content="export async function GET() { return Response.json({}) }")

    def test_detect_api(self, tmp_path: Path) -> None:
        """Prüft detect() auf src/api/."""
        base = tmp_path / "backend"
        self._create_api_structure(base)
        assert medusa_api.detect(str(base))

    def test_extract_routes(self, tmp_path: Path) -> None:
        """Prüft Extraktion aller API-Routen."""
        base = tmp_path / "backend"
        self._create_api_structure(base)
        routes = medusa_api.extract(str(base))
        assert len(routes) >= 7

    def test_has_store_routes(self, tmp_path: Path) -> None:
        """Prüft Store-Routen via /store/ im Pfad."""
        base = tmp_path / "backend"
        self._create_api_structure(base)
        routes = medusa_api.extract(str(base))
        store_routes = [r for r in routes if "/store/" in r["path"]]
        assert len(store_routes) >= 4

    def test_route_has_params(self, tmp_path: Path) -> None:
        """Prüft Extraktion von Parametern in API-Routen."""
        base = tmp_path / "backend"
        self._create_api_structure(base)
        routes = medusa_api.extract(str(base))
        with_params = [r for r in routes if r["params"]]
        assert len(with_params) >= 2

    def test_route_structure(self, tmp_path: Path) -> None:
        """Prüft das Format extrahierter API-Routen."""
        base = tmp_path / "backend"
        self._create_api_structure(base)
        routes = medusa_api.extract(str(base))
        for r in routes:
            assert r["path"].startswith("/")
            assert r["route_type"] == "api"

    def test_not_detect_wrong_dir(self, tmp_path: Path) -> None:
        """Leeres Verzeichnis wird nicht als Medusa API erkannt."""
        assert not medusa_api.detect(str(tmp_path))


# ===================================================================
# TestGoHandlerExtractor
# ===================================================================


class TestGoHandlerExtractor:
    """Go Handler Extractor mit tmp_path."""

    @staticmethod
    def _write(base: Path, *parts: str, content: str = "") -> None:
        target = base.joinpath(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def _create_go_structure(self, base: Path) -> None:
        """Erzeugt go.mod + internal/core/ + internal/api/handler.go."""
        # go.mod
        self._write(base, "go.mod", content="module github.com/example/test\n\ngo 1.22\n")

        # Core Module
        for module in ["product", "cart", "order"]:
            self._write(base, "internal", "core", module, "module.go",
                         content=f"package {module}\n\ntype Module struct {{}}\n")
            if module == "product":
                self._write(base, "internal", "core", module, "handler.go", content="""package product

// Route: /api/v1/products
func setupRoutes(r *mux.Router) {
    r.HandleFunc("/api/v1/products", getProducts).Methods("GET")
    r.HandleFunc("/api/v1/products/{id}", getProduct).Methods("GET")
}
""")
        # API handler
        self._write(base, "internal", "api", "handler.go", content="""package api

func SetupRouter(r *mux.Router) {
    r.GET("/store/products", listProducts)
    r.POST("/store/carts", createCart)
    r.Route("/api", apiSubrouter)
}
""")

    def test_detect_go(self, tmp_path: Path) -> None:
        """Prüft detect() — go.mod + internal/core/."""
        base = tmp_path / "project"
        self._create_go_structure(base)
        assert go_handler.detect(str(base))

    def test_get_modules(self, tmp_path: Path) -> None:
        """Prüft Modul-Erkennung (internal/core/ Unterverzeichnisse)."""
        base = tmp_path / "project"
        self._create_go_structure(base)
        modules = go_handler.get_modules(str(base))
        assert len(modules) >= 3
        assert "product" in modules
        assert "cart" in modules
        assert "order" in modules

    def test_extract_routes(self, tmp_path: Path) -> None:
        """Prüft Route-Extraktion aus .go Dateien."""
        base = tmp_path / "project"
        self._create_go_structure(base)
        routes = go_handler.extract(str(base))
        # Erwarte: /api/v1/products, /api/v1/products/{id},
        #          /store/products, /store/carts, /api
        assert len(routes) >= 4

    def test_has_api_v1_route(self, tmp_path: Path) -> None:
        """Prüft auf /api/ oder /store Präfix in extrahierten Routen."""
        base = tmp_path / "project"
        self._create_go_structure(base)
        routes = go_handler.extract(str(base))
        paths = [r["path"] for r in routes]
        has_api = any("/api/" in p for p in paths)
        has_store = any("/store" in p for p in paths)
        assert has_api or has_store

    def test_route_structure(self, tmp_path: Path) -> None:
        """Prüft das Format extrahierter Go-Routen."""
        base = tmp_path / "project"
        self._create_go_structure(base)
        routes = go_handler.extract(str(base))
        for r in routes:
            assert "path" in r
            assert "source_file" in r
