"""go_handler.py — Go HTTP Handler + Router Extractor.

Extrahiert Go Core Module (internal/core/*/) und findet HTTP-Routen
via einfacher Textmuster in router.go/handler.go Dateien.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List

logger = logging.getLogger("analysis.extractors.go_handler")


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def _has_dir(root: str, *parts: str) -> bool:
    return os.path.isdir(os.path.join(root, *parts))


def _has_file(root: str, *parts: str) -> bool:
    return os.path.isfile(os.path.join(root, *parts))


def detect(path: str) -> bool:
    """Erkennt Go Backend mit HTTP Handlern."""
    has_go_mod = _has_file(path, "go.mod")
    has_handler_dir = _has_dir(path, "internal", "core")
    has_api_dir = _has_dir(path, "internal", "api")
    return has_go_mod and (has_handler_dir or has_api_dir)


# ---------------------------------------------------------------------------
# Module Discovery
# ---------------------------------------------------------------------------

def get_modules(path: str) -> List[str]:
    """Listet Go Core Module (internal/core/*/) auf."""
    core_dir = os.path.join(path, "internal", "core")
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
# Route Discovery (basic)
# ---------------------------------------------------------------------------

def _find_route_files(root: str) -> List[str]:
    """Findet relevante Router-Dateien."""
    files = []
    api_dir = os.path.join(root, "internal", "api")
    if _has_dir(api_dir):
        try:
            for dirpath, dirnames, filenames in os.walk(api_dir):
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                for fn in filenames:
                    if fn.endswith(".go"):
                        files.append(os.path.join(dirpath, fn))
        except PermissionError:
            pass
    # Auch handler.go Dateien in internal/core durchsuchen
    core_dir = os.path.join(root, "internal", "core")
    if _has_dir(core_dir):
        try:
            for dirpath, dirnames, filenames in os.walk(core_dir):
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                for fn in filenames:
                    if fn.endswith("handler.go") or fn == "routes.go":
                        files.append(os.path.join(dirpath, fn))
        except PermissionError:
            pass
    return files


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_route_patterns(content: str, source: str) -> List[Dict[str, Any]]:
    """Findet HTTP-Routen in Go-Code via Regex."""
    routes = []
    seen = set()

    patterns = [
        r'(?:router|mux|r)\.(?:HandleFunc|Handle)\s*\(\s*"([^"]+)"',
        r'(?:router|mux|r)\.(?:HandleFunc|Handle)\s*\(\s*`([^`]+)`',
        r'(?:router|mux|r)\.(?:GET|POST|PUT|DELETE|PATCH|HEAD)\s*\(\s*"([^"]+)"',
        r'(?:router|mux|r)\.(?:GET|POST|PUT|DELETE|PATCH|HEAD)\s*\(\s*`([^`]+)`',
        r'//\s*Route:\s*(/\S+)',
        # Chi subrouter prefixes
        r'r\.Route\s*\(\s*"([^"]+)"',
        r'r\.Route\s*\(\s*`([^`]+)`',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, content):
            route_path = match.group(1)
            if route_path not in seen:
                seen.add(route_path)
                routes.append({
                    "path": route_path,
                    "source_file": source,
                    "route_type": "go-api",
                    "params": re.findall(r"\{([^}]+)\}", route_path),
                })
    return routes


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract(path: str) -> List[Dict[str, Any]]:
    """Findet alle Go HTTP-Routen und Module."""
    # Finde Module
    get_modules(path)

    # Finde Routen
    routes = []
    for filepath in _find_route_files(path):
        try:
            with open(filepath) as f:
                content = f.read()
            rel_path = os.path.relpath(filepath, path)
            routes.extend(_parse_route_patterns(content, rel_path))
        except Exception as e:
            logger.debug("route file parsing failed: %s", e)

    return routes
