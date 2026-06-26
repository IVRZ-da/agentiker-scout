"""nextjs.py — Next.js App Router Extractor.

Extrahiert Routen aus Next.js Projekten mit App Router.
Unterstützt app/ und src/app/ Verzeichnisse, Route Groups,
Parameter und Auth-Status Erkennung.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List

logger = logging.getLogger("analysis.extractors.nextjs")


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def _has_file(root: str, *parts: str) -> bool:
    return os.path.isfile(os.path.join(root, *parts))


def _has_dir(root: str, *parts: str) -> bool:
    return os.path.isdir(os.path.join(root, *parts))


def detect(path: str) -> bool:
    """Erkennt Next.js App Router Projekt (auch mit src/ directory)."""
    has_next_config = (
        _has_file(path, "next.config.js")
        or _has_file(path, "next.config.mjs")
        or _has_file(path, "next.config.ts")
    )

    app_paths = [
        os.path.join(path, "app"),
        os.path.join(path, "src", "app"),
    ]
    has_app_dir = any(
        _has_dir(ap) and len(_find_page_files(ap)) > 0
        for ap in app_paths
    )

    has_package = _has_file(path, "package.json")
    has_next_dep = False
    if has_package:
        try:
            import json
            with open(os.path.join(path, "package.json")) as f:
                pkg = json.load(f)
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            has_next_dep = "next" in deps
        except Exception as e:
            logger.debug("package.json read failed: %s", e)

    return (has_app_dir and has_next_dep) or (has_next_config and has_app_dir)


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
    """Parst einen Next.js page.tsx Pfad in eine Route.

    Beispiele:
      app/[locale]/(store)/products/[handle]/page.tsx
      → path: /products/[handle], params: [locale, handle], groups: [store]
    """
    route = rel_path.replace("page.tsx", "").rstrip("/")

    # Extrahiere Route Groups ((name)) — sie ändern den Pfad nicht
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


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract(path: str) -> List[Dict[str, Any]]:
    """Extrahiert alle Next.js Routen aus app/ oder src/app/."""
    for app_sub in ["app", os.path.join("src", "app")]:
        app_dir = os.path.join(path, app_sub)
        if _has_dir(app_dir):
            pages = _find_page_files(app_dir)
            return [_parse_route(p) for p in pages]
    return []
