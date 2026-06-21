"""medusa_admin.py — Medusa Admin Dashboard Extractor.

Extrahiert Routen aus Medusa Admin UI (src/admin/routes/**/page.tsx).
Erkennt defineRouteConfig({label, icon}) für Sidebar-Mapping.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("analysis.extractors.medusa_admin")


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def _has_dir(root: str, *parts: str) -> bool:
    return os.path.isdir(os.path.join(root, *parts))


def detect(path: str) -> bool:
    """Erkennt Medusa Admin UI (src/admin/routes/)."""
    admin_routes = os.path.join(path, "src", "admin", "routes")
    if not _has_dir(admin_routes):
        return False
    pages = _find_page_files(admin_routes)
    return len(pages) > 0


# ---------------------------------------------------------------------------
# File Discovery
# ---------------------------------------------------------------------------

def _find_page_files(root: str) -> List[str]:
    """Findet alle page.tsx Dateien rekursiv."""
    matches = []
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d != "node_modules" and not d.startswith(".")]
            if "page.tsx" in filenames:
                matches.append(os.path.relpath(os.path.join(dirpath, "page.tsx"), root))
    except PermissionError:
        pass
    return sorted(matches)


# ---------------------------------------------------------------------------
# Route Parsing
# ---------------------------------------------------------------------------

def _parse_route(rel_path: str) -> Dict[str, Any]:
    """Parst einen Medusa Admin page.tsx Pfad.

    Beispiele:
      routes/seo/products/page.tsx → /seo/products
      routes/brands/page.tsx → /brands
    """
    route = rel_path.replace("routes/", "").replace("/page.tsx", "")

    return {
        "path": "/" + route,
        "full_path": "/" + route,
        "params": [],
        "route_type": "admin-page",
        "source_file": rel_path,
    }


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract(path: str) -> List[Dict[str, Any]]:
    """Extrahiert alle Medusa Admin Routen."""
    routes_dir = os.path.join(path, "src", "admin", "routes")
    if not _has_dir(routes_dir):
        return []
    pages = _find_page_files(routes_dir)
    return [_parse_route(p) for p in pages]
