"""medusa_api.py — Medusa Backend API Route Extractor.

Extrahiert API-Routen aus src/api/**/route.ts.
Erkennt Parameter ([id], [slug]) und unterscheidet store/admin API.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("analysis.extractors.medusa_api")


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def _has_dir(root: str, *parts: str) -> bool:
    return os.path.isdir(os.path.join(root, *parts))


def detect(path: str) -> bool:
    """Erkennt Medusa API Routes (src/api/)."""
    api_dir = os.path.join(path, "src", "api")
    if not _has_dir(api_dir):
        return False
    routes = _find_route_files(api_dir)
    return len(routes) > 0


# ---------------------------------------------------------------------------
# File Discovery
# ---------------------------------------------------------------------------

def _find_route_files(root: str) -> List[str]:
    """Findet alle route.ts/route.js Dateien rekursiv."""
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


# ---------------------------------------------------------------------------
# Route Parsing
# ---------------------------------------------------------------------------

def _parse_route(rel_path: str) -> Dict[str, Any]:
    """Parst einen API route.ts Pfad.

    Beispiele:
      api/store/products/route.ts → /api/store/products
    """
    route = rel_path.replace("/route.ts", "").replace("/route.js", "")
    params = re.findall(r"\[([^\]]+)\]", route)

    return {
        "path": "/" + route,
        "full_path": "/" + route,
        "params": params,
        "route_type": "api",
        "source_file": rel_path,
    }


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract(path: str) -> List[Dict[str, Any]]:
    """Extrahiert alle Medusa API Routen."""
    api_dir = os.path.join(path, "src", "api")
    if not _has_dir(api_dir):
        return []
    routes = _find_route_files(api_dir)
    return [_parse_route(r) for r in routes]
