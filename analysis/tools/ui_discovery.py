"""ui_discovery — UI-Layer-Erkennung für Multi-UI-Projekte.

Erkennt automatisch welche UI-Frameworks in einem Projekt verwendet werden
und extrahiert Routen + Backend-Module.

Unterstützte UI-Typen:
  - nextjs: Next.js App Router (app/**/page.tsx)
  - medusa-admin: Medusa Admin Dashboard (src/admin/routes/)
  - medusa-api: Medusa API Routes (src/api/**/route.ts)
  - go-handler: Go HTTP Handler (internal/core/*/handler.go)
  - vite: Generic Vite/React project
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger("analysis.ui_discovery")


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class UiLayer:
    """Repräsentiert eine UI-Layer in einem Projekt."""

    path: str                          # Absoluter Pfad zum UI-Root
    ui_type: str                       # nextjs | medusa-admin | medusa-api | go-handler | vite
    name: str                          # Lesbarer Name (z.B. "Storefront", "Admin")
    routes: List[Dict[str, Any]] = field(default_factory=list)
    modules: List[str] = field(default_factory=list)
    markers: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "ui_type": self.ui_type,
            "name": self.name,
            "routes": self.routes,
            "modules": self.modules,
            "markers": self.markers,
        }


# ---------------------------------------------------------------------------
# Framework Detection
# ---------------------------------------------------------------------------

def _has_file(root: str, *parts: str) -> bool:
    """Prüft ob eine Datei existiert (relative Pfade)."""
    return os.path.isfile(os.path.join(root, *parts))


def _has_dir(root: str, *parts: str) -> bool:
    """Prüft ob ein Verzeichnis existiert."""
    return os.path.isdir(os.path.join(root, *parts))


def _find_page_files(root: str) -> List[str]:
    """Findet alle page.tsx Dateien rekursiv (ohne node_modules)."""
    matches = []
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            # node_modules überspringen
            dirnames[:] = [d for d in dirnames if d != "node_modules" and not d.startswith(".")]
            if "page.tsx" in filenames:
                matches.append(os.path.relpath(os.path.join(dirpath, "page.tsx"), root))
    except PermissionError:
        pass
    return sorted(matches)


def _find_route_files(root: str) -> List[str]:
    """Findet alle route.ts Dateien (API-Routen) rekursiv."""
    matches = []
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d != "node_modules" and not d.startswith(".")]
            for fn in filenames:
                if fn == "route.ts" or fn == "route.js":
                    matches.append(os.path.relpath(os.path.join(dirpath, fn), root))
    except PermissionError:
        pass
    return sorted(matches)


def _detect_nextjs(path: str) -> bool:
    """Erkennt Next.js App Router Projekt (auch mit src/ directory)."""
    has_next_config = (
        _has_file(path, "next.config.js")
        or _has_file(path, "next.config.mjs")
        or _has_file(path, "next.config.ts")
    )

    # Prüfe app/ und src/app/
    app_paths = [
        os.path.join(path, "app"),
        os.path.join(path, "src", "app"),
    ]
    has_app_dir = any(
        _has_dir(ap) and len(_find_page_files(ap)) > 0
        for ap in app_paths
    )

    has_package = _has_file(path, "package.json")

    # Prüfe package.json auf next dependency
    has_next_dep = False
    if has_package:
        try:
            import json
            with open(os.path.join(path, "package.json")) as f:
                pkg = json.load(f)
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            has_next_dep = "next" in deps
        except Exception as e:
            logger.debug("package.json parse failed: %s", e)

    return (has_app_dir and has_next_dep) or (has_next_config and has_app_dir)


def _detect_medusa_admin(path: str) -> bool:
    """Erkennt Medusa Admin UI (src/admin/routes/)."""
    admin_routes = os.path.join(path, "src", "admin", "routes")
    if not _has_dir(admin_routes):
        return False
    pages = _find_page_files(admin_routes)
    return len(pages) > 0


def _detect_medusa_api(path: str) -> bool:
    """Erkennt Medusa API Routes (src/api/)."""
    api_dir = os.path.join(path, "src", "api")
    if not _has_dir(api_dir):
        return False
    routes = _find_route_files(api_dir)
    return len(routes) > 0


def _detect_go_handler(path: str) -> bool:
    """Erkennt Go Backend mit HTTP Handlern."""
    has_go_mod = _has_file(path, "go.mod")
    has_handler_dir = _has_dir(path, "internal", "core")
    has_api_dir = _has_dir(path, "internal", "api")
    return has_go_mod and (has_handler_dir or has_api_dir)


def _detect_vite(path: str) -> bool:
    """Erkennt Vite/React Projekt."""
    return _has_file(path, "vite.config.ts") or _has_file(path, "vite.config.js")


# ---------------------------------------------------------------------------
# Route Extraction
# ---------------------------------------------------------------------------

def _parse_nextjs_route(rel_path: str) -> Dict[str, Any]:
    """Parst einen Next.js page.tsx Pfad in eine Route.

    Beispiele:
      app/[locale]/(store)/products/[handle]/page.tsx
      → path: /products/[handle], params: [locale, handle], groups: [store]
    """
    # Entferne app/ prefix und page.tsx suffix
    route = rel_path.replace("page.tsx", "").rstrip("/")

    # Entferne route groups ((name))  — sie ändern den Pfad nicht
    groups = re.findall(r"\(([^)]+)\)", route)
    route_clean = re.sub(r"/\([^)]+\)", "", route)

    # Extrahiere Parameter ([name])
    params = re.findall(r"\[([^\]]+)\]", route_clean)

    # Bestimme Auth-Status
    auth_status = "public"
    if "(protected)" in route:
        auth_status = "protected"
    elif "(guest)" in route:
        auth_status = "guest"

    # Bestimme Route-Typ
    route_type = "page"
    if "[id]" in params or len([p for p in params if p != "locale"]) > 0:
        route_type = "detail"

    return {
        "path": route_clean,
        "full_path": route,
        "params": params,
        "groups": groups,
        "auth_status": auth_status,
        "route_type": route_type,
        "source_file": rel_path,
    }


def _parse_medusa_admin_route(rel_path: str) -> Dict[str, Any]:
    """Parst einen Medusa Admin page.tsx Pfad.

    Beispiele:
      routes/seo/products/page.tsx → /seo/products
      routes/brands/page.tsx → /brands
    """
    # Entferne routes/ prefix und page.tsx suffix
    route = rel_path.replace("routes/", "").replace("/page.tsx", "")

    return {
        "path": "/" + route,
        "full_path": "/" + route,
        "params": [],
        "route_type": "admin-page",
        "source_file": rel_path,
    }


def _parse_api_route(rel_path: str) -> Dict[str, Any]:
    """Parst einen API route.ts Pfad.

    Beispiele:
      api/store/products/route.ts → GET /api/store/products
    """
    route = rel_path.replace("/route.ts", "").replace("/route.js", "")

    # Extrahiere Parameter
    params = re.findall(r"\[([^\]]+)\]", route)

    return {
        "path": "/" + route,
        "full_path": "/" + route,
        "params": params,
        "route_type": "api",
        "source_file": rel_path,
    }


def _get_nextjs_routes(root: str) -> List[Dict[str, Any]]:
    """Extrahiert alle Next.js Routen aus app/ oder src/app/."""
    for app_sub in ["app", os.path.join("src", "app")]:
        app_dir = os.path.join(root, app_sub)
        if _has_dir(app_dir):
            pages = _find_page_files(app_dir)
            return [_parse_nextjs_route(p) for p in pages]
    return []


def _get_medusa_admin_routes(root: str) -> List[Dict[str, Any]]:
    """Extrahiert alle Medusa Admin Routen."""
    routes_dir = os.path.join(root, "src", "admin", "routes")
    if not _has_dir(routes_dir):
        return []
    pages = _find_page_files(routes_dir)
    return [_parse_medusa_admin_route(p) for p in pages]


def _get_medusa_api_routes(root: str) -> List[Dict[str, Any]]:
    """Extrahiert alle Medusa API Routen."""
    api_dir = os.path.join(root, "src", "api")
    if not _has_dir(api_dir):
        return []
    routes = _find_route_files(api_dir)
    return [_parse_api_route(r) for r in routes]


# ---------------------------------------------------------------------------
# Backend Module Discovery
# ---------------------------------------------------------------------------

def _get_medusa_modules(root: str) -> List[str]:
    """Listet Medusa Backend Module (src/modules/*/) auf."""
    modules_dir = os.path.join(root, "src", "modules")
    if not _has_dir(modules_dir):
        return []
    try:
        return sorted([
            d for d in os.listdir(modules_dir)
            if _has_dir(modules_dir, d) and not d.startswith(".")
        ])
    except PermissionError:
        return []


def _get_go_modules(root: str) -> List[str]:
    """Listet Go Core Module (internal/core/*/) auf."""
    core_dir = os.path.join(root, "internal", "core")
    if not _has_dir(core_dir):
        return []
    try:
        return sorted([
            d for d in os.listdir(core_dir)
            if _has_dir(core_dir, d) and not d.startswith(".")
        ])
    except PermissionError:
        return []


# ---------------------------------------------------------------------------
# Main Discovery
# ---------------------------------------------------------------------------

def discover_uis(project_root: str) -> List[UiLayer]:
    """Erkennt alle UI-Layer in einem Projekt.

    Scannt das Projekt-Root und bekannte Unterverzeichnisse (apps/, packages/)
    nach UI-Framework-Markern. Gibt eine Liste aller gefundenen UiLayer zurück.
    """
    if not os.path.isdir(project_root):
        logger.warning("Project root not found: %s", project_root)
        return []

    project_root = os.path.abspath(project_root)
    ui_layers: List[UiLayer] = []

    # 1️⃣ Direkt im Root scannen
    ui_layers.extend(_scan_directory(project_root))

    # 2️⃣ Monorepo: apps/ subdirectories scannen
    apps_dir = os.path.join(project_root, "apps")
    if _has_dir(apps_dir):
        try:
            for sub in sorted(os.listdir(apps_dir)):
                sub_path = os.path.join(apps_dir, sub)
                if os.path.isdir(sub_path) and not sub.startswith("."):
                    ui_layers.extend(_scan_directory(sub_path, prefix=sub))
        except PermissionError:
            pass

    # 3️⃣ packages/ subdirectories scannen
    pkgs_dir = os.path.join(project_root, "packages")
    if _has_dir(pkgs_dir):
        try:
            for sub in sorted(os.listdir(pkgs_dir)):
                sub_path = os.path.join(pkgs_dir, sub)
                if os.path.isdir(sub_path) and not sub.startswith("."):
                    ui_layers.extend(_scan_directory(sub_path, prefix=f"packages/{sub}"))
        except PermissionError:
            pass

    # 4️⃣ Bekannte UI-Subdirs im Root (admin/, storefront/, frontend/)
    known_ui_dirs = ["admin", "storefront", "frontend", "dashboard"]
    for sub in known_ui_dirs:
        sub_path = os.path.join(project_root, sub)
        if os.path.isdir(sub_path) and not any(l.path == sub_path for l in ui_layers):
            sub_layers = _scan_directory(sub_path, prefix=sub)
            # Nur hinzufügen wenn nicht bereits erfasst
            for sl in sub_layers:
                if sl.path not in [l.path for l in ui_layers]:
                    ui_layers.append(sl)

    return ui_layers


def _scan_directory(path: str, prefix: str = "") -> List[UiLayer]:
    """Scannt ein einzelnes Verzeichnis nach UI-Framework-Markern."""
    layers: List[UiLayer] = []
    # Für benannte Subdirs: prefix nutzen, sonst dirname
    if prefix:
        # apps/storefront → "storefront", apps/backend → "backend"
        base_name = prefix.split("/")[-1]
    else:
        base_name = os.path.basename(path)

    # Detect Next.js
    if _detect_nextjs(path):
        routes = _get_nextjs_routes(path)
        modules = _get_medusa_modules(path)
        markers = ["next.config", "app/"]
        if _has_file(path, "middleware.ts"):
            markers.append("middleware.ts")
        layers.append(UiLayer(
            path=path,
            ui_type="nextjs",
            name=base_name,
            routes=routes,
            modules=modules,
            markers=markers,
        ))

    # Detect Medusa Admin
    if _detect_medusa_admin(path):
        routes = _get_medusa_admin_routes(path)
        _modules = _get_medusa_modules(path)
        markers = ["src/admin/routes/"]
        layers.append(UiLayer(
            path=path,
            ui_type="medusa-admin",
            name=f"{base_name}-admin",
            routes=routes,
            modules=_modules,
            markers=markers,
        ))

    # Detect Medusa API
    if _detect_medusa_api(path):
        routes = _get_medusa_api_routes(path)
        markers = ["src/api/"]
        api_modules = _get_medusa_modules(path)
        layers.append(UiLayer(
            path=path,
            ui_type="medusa-api",
            name=f"{base_name}-api",
            routes=routes,
            modules=api_modules,
            markers=markers,
        ))

    # Detect Go Handler (backend modules only, no routes extracted here)
    if _detect_go_handler(path):
        modules = _get_go_modules(path)
        markers = ["go.mod", "internal/core/"]
        # Try to find route registrations
        routes = _find_go_routes(path)
        layers.append(UiLayer(
            path=path,
            ui_type="go-handler",
            name=base_name,
            routes=routes,
            modules=modules,
            markers=markers,
        ))

    # Detect Vite (generic)
    if _detect_vite(path):
        markers = ["vite.config"]
        if not any(l.path == path for l in layers):
            layers.append(UiLayer(
                path=path,
                ui_type="vite",
                name=f"{base_name}" if prefix else "frontend",
                routes=[],
                modules=[],
                markers=markers,
            ))

    return layers


# ---------------------------------------------------------------------------
# Go Route Discovery (basic)
# ---------------------------------------------------------------------------

def _find_go_routes(root: str) -> List[Dict[str, Any]]:
    """Findet Go HTTP-Routen via einfacher Textmuster.

    Sucht nach router.HandleFunc, router.GET, router.POST etc.
    in internal/api/router.go oder ähnlichen Dateien.
    """
    routes = []
    # Typische Router-Dateien durchsuchen
    for filename in ["router.go", "routes.go", "api.go", "handler.go"]:
        for dirpath, dirnames, filenames in os.walk(os.path.join(root, "internal")):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            if filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    with open(filepath) as f:
                        content = f.read()
                    # Einfache Pattern für Go Router
                    patterns = [
                        r'(?:router|mux|r)\.(?:HandleFunc|GET|POST|PUT|DELETE|PATCH)\s*\(\s*"([^"]+)"',
                        r'(?:router|mux|r)\.(?:HandleFunc|GET|POST|PUT|DELETE|PATCH)\s*\(\s*`([^`]+)`',
                        r'//\s*Route:\s*(/\S+)',
                    ]
                    for pattern in patterns:
                        for match in re.finditer(pattern, content):
                            route_path = match.group(1)
                            if route_path not in [r["path"] for r in routes]:
                                routes.append({
                                    "path": route_path,
                                    "source_file": os.path.relpath(filepath, root),
                                    "route_type": "go-api",
                                    "params": re.findall(r"\{([^}]+)\}", route_path),
                                })
                except Exception as e:
                    logger.debug("go route regex match failed: %s", e)
    return routes


# ---------------------------------------------------------------------------
# Summary Helpers
# ---------------------------------------------------------------------------

def summarize_ui_layers(layers: List[UiLayer]) -> str:
    """Erzeugt eine lesbare Zusammenfassung der UI-Layer."""
    if not layers:
        return "Keine UI-Layer gefunden."

    lines = [f"Gefundene UI-Layer: {len(layers)}"]
    for layer in layers:
        route_count = len(layer.routes)
        module_count = len(layer.modules)
        lines.append(f"\n  [{layer.ui_type}] {layer.name}")
        lines.append(f"    Pfad: {layer.path}")
        lines.append(f"    Routen: {route_count}")
        if module_count:
            lines.append(f"    Module: {', '.join(layer.modules[:10])}")
            if module_count > 10:
                lines.append(f"      ... und {module_count - 10} weitere")
        lines.append(f"    Marker: {', '.join(layer.markers)}")

    total_routes = sum(len(l.routes) for l in layers)
    total_modules = sum(len(l.modules) for l in layers)
    lines.append(f"\nGesamt: {total_routes} Routen, {total_modules} Module")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    layers = discover_uis(root)
