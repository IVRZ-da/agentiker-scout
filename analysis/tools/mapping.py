"""mapping.py — Backend→UI Mapping Engine für UI-Gap-Analyse.

Vergleicht Backend-Module gegen extrahierte UI-Routen aus allen UI-Layern.
Berechnet Coverage-Scores und identifiziert Gaps pro Typ.

Reine Namens-Konventionen, keine hardcodierten Projekt-Aliase.
- Plural: +s (brand→brands), +es (box→boxes)
- Hyphen↔Underscore: hero-banner↔hero_banner
- Singular↔Plural werden gegeneinander geprüft
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Set

from .ui_discovery import UiLayer, discover_uis

logger = logging.getLogger("analysis.mapping")


# ---------------------------------------------------------------------------
# Gap Types
# ---------------------------------------------------------------------------

GAP_CRITICAL = "🔴"   # Backend Module ohne Admin UI
GAP_WARNING = "🟡"    # Backend Module ohne Storefront Page
GAP_INFO = "🟢"       # API Route ohne korrespondierende Page
GAP_ORPHAN = "🟠"     # Admin Page ohne Backend Module
GAP_MISSING_DETAIL = "🔵"  # Entity nur List, kein Detail

GAP_LABELS = {
    GAP_CRITICAL: "Backend Module ohne Admin UI",
    GAP_WARNING: "Backend Module ohne Storefront Page",
    GAP_INFO: "API Route ohne korrespondierende Page",
    GAP_ORPHAN: "Admin Page ohne Backend Module",
    GAP_MISSING_DETAIL: "Nur List-View, kein Detail",
}


# ---------------------------------------------------------------------------
# Namens-Konventionen (rein generisch)
# ---------------------------------------------------------------------------
# Keine hardcodierten Aliase! Ausnahmen gehören in eine optionale
# Projekt-Config (.ui-gap.yaml), nicht ins Plugin.


def _module_to_route_segments(module_name: str) -> List[str]:
    """Wandelt Modulname in mögliche Route-Segmente (generisch).

    Verwendet nur Namens-Konventionen, keine hardcodierten Aliase:
      - Modulname selbst
      - Plural mit +s (brand→brands)
      - Plural mit +es bei Endungen -ch,-sh,-s,-x,-z (box→boxes)
      - Hyphen→Underscore (hero-banner→hero_banner)
    """
    segments = [module_name]

    # Plural +s (einfach)
    if not module_name.endswith("s"):
        segments.append(module_name + "s")

    # Plural +es (endet auf -ch, -sh, -s, -x, -z)
    if module_name.endswith(("ch", "sh", "s", "x", "z")):
        segments.append(module_name + "es")

    # Replace hyphens with underscores
    segments.append(module_name.replace("-", "_"))

    return list(set(segments))


def _route_matches_module(route_path: str, module_name: str) -> bool:
    """Prüft ob ein Route-Pfad zu einem Modulnamen passt (segmentgenau).

    Vergleicht Pfad-Segmente gegen Modul-Namen inkl. Plural-Varianten.
    'brand' matcht '/brands' aber 'agent' matcht NICHT '/agent-channels'.

    Keine hardcodierten Aliase — nur generische Namens-Konventionen.
    """
    segments = _module_to_route_segments(module_name)
    path_segments = [s for s in route_path.strip("/").lower().split("/") if s]
    for seg in segments:
        seg_lower = seg.lower()
        for ps in path_segments:
            if ps == seg_lower:
                return True
            # Erlaube Singular→Plural (brand→brands)
            if seg_lower + "s" == ps or seg_lower == ps + "s":
                return True
    return False


# ---------------------------------------------------------------------------
# Coverage Matrix
# ---------------------------------------------------------------------------

CoverageMatrix = Dict[str, Dict[str, Any]]


def build_coverage_matrix(project_root: str) -> CoverageMatrix:
    """Baut eine Coverage-Matrix: welche Module haben UI-Seiten in welchem Layer.

    Returns:
      {
        "module_name": {
          "has_admin": True/False,
          "has_storefront": True/False,
          "has_api": True/False,
          "has_detail_admin": True/False,
          "has_detail_storefront": True/False,
          "admin_pages": [...],
          "storefront_pages": [...],
          "api_routes": [...],
          "found_admin": [path1, ...],
          "found_storefront": [path1, ...],
          "found_api": [path1, ...],
        },
        ...
        "coverage": {"total_modules": N, "with_admin": N, ...},
        "gaps": [{...}, ...],
      }
    """
    layers = discover_uis(project_root)
    return _analyze_layers(layers, project_root)


def _analyze_layers(layers: List[UiLayer], project_root: str) -> CoverageMatrix:
    """Analysiert UI-Layer gegen Backend-Module."""
    # Finde alle Backend-Module (Dedupliziert über Layer)
    all_modules: Dict[str, Set[str]] = {}  # module_name → quellen (Pfade)
    admin_layer = None
    storefront_layer = None
    api_layer = None

    for layer in layers:
        if layer.ui_type == "medusa-admin":
            admin_layer = layer
        elif layer.ui_type == "nextjs":
            storefront_layer = layer
        elif layer.ui_type == "medusa-api":
            api_layer = layer
        elif layer.ui_type == "go-handler":
            pass

        # Sammle Module aus allen Layern
        for m in layer.modules:
            if m not in all_modules:
                all_modules[m] = set()
            all_modules[m].add(layer.path)

    # Starte Matrix
    matrix: CoverageMatrix = {
        "_meta": {
            "project_root": project_root,
            "layers_found": [l.to_dict() for l in layers],
            "total_layers": len(layers),
        }
    }

    gaps = []

    for module_name in sorted(all_modules.keys()):
        entry: Dict[str, Any] = {
            "name": module_name,
            "sources": list(all_modules[module_name]),
            "has_admin": False,
            "has_storefront": False,
            "has_api": False,
            "has_detail_admin": False,
            "has_detail_storefront": False,
            "admin_pages": [],
            "storefront_pages": [],
            "api_routes": [],
        }

        # Prüfe Admin-Layer
        if admin_layer:
            matching = [r for r in admin_layer.routes if _route_matches_module(r["path"], module_name)]
            if matching:
                entry["has_admin"] = True
                entry["admin_pages"] = matching
                # Detail = [id] param oder sub-route (z.B. seo/products/ → seo ist parent)
                entry["has_detail_admin"] = any(
                    r.get("route_type") == "detail"
                    or "[id]" in r.get("path", "")
                    or len(r["path"].strip("/").split("/")) >= 2  # sub-route = detail view
                    for r in matching
                )

        # Prüfe Storefront-Layer
        if storefront_layer:
            matching = [r for r in storefront_layer.routes if _route_matches_module(r["path"], module_name)]
            if matching:
                entry["has_storefront"] = True
                entry["storefront_pages"] = matching
                entry["has_detail_storefront"] = any(
                    r.get("route_type") == "detail" or "[id]" in r.get("path", "")
                    for r in matching
                )

        # Prüfe API-Layer
        if api_layer:
            matching = [r for r in api_layer.routes if _route_matches_module(r["path"], module_name)]
            if matching:
                entry["has_api"] = True
                entry["api_routes"] = matching

        matrix[module_name] = entry

        # Gap-Erkennung
        if entry["has_api"] or True:  # Alle Module prüfen
            if not entry["has_admin"]:
                gaps.append({
                    "type": GAP_CRITICAL,
                    "module": module_name,
                    "detail": f"Keine Admin-UI-Page für Modul '{module_name}'",
                    "suggestion": f"Admin-Page für {module_name} erstellen",
                })
            if storefront_layer and not entry["has_storefront"]:
                gaps.append({
                    "type": GAP_WARNING,
                    "module": module_name,
                    "detail": f"Keine Storefront-Page für Modul '{module_name}'",
                    "suggestion": f"Storefront-Seite für {module_name} prüfen",
                })
            if entry["has_admin"] and not entry["has_detail_admin"]:
                gaps.append({
                    "type": GAP_MISSING_DETAIL,
                    "module": module_name,
                    "detail": f"Admin-Page für '{module_name}' hat keine Detail-Ansicht",
                    "suggestion": f"Erstelle admin/routes/{module_name}/[id]/page.tsx",
                })

    # Orphan-Admin-Pages (Admin-Seiten ohne Backend-Modul)
    all_module_names = set(all_modules.keys())
    if admin_layer:
        for r in admin_layer.routes:
            path_parts = r["path"].strip("/").split("/")
            if path_parts and path_parts[0]:
                route_root = path_parts[0]
                # Prüfe ob irgendein Modul zu dieser Route passt
                has_module = any(
                    _route_matches_module(r["path"], m)
                    for m in all_module_names
                )
                if not has_module:
                    gaps.append({
                        "type": GAP_ORPHAN,
                        "module": route_root,
                        "detail": f"Admin-Page '{r['path']}' ohne Backend-Modul",
                        "suggestion": f"Prüfen ob Modul für '{route_root}' fehlt oder Page obsolet ist",
                    })

    # API-Orphan-Routes (API ohne korrespondierende Page)
    if api_layer and (admin_layer or storefront_layer):
        for r in api_layer.routes:
            path = r["path"]
            # Generischer Check: Hat irgendein Modul eine korrespondierende Page?
            has_page = any(
                _route_matches_module(path, m)
                for m in all_module_names
            ) if all_module_names else False
            if not has_page:
                # Nur wenn die API-Route nicht zu einem core-Medusa-Pfad gehört
                # (core-Pfade sind oft /admin/... die kein Modul-Mapping brauchen)
                is_core_api = any(seg in path.lower() for seg in [
                    "/admin/", "/auth/",
                ]) if hasattr(api_layer, 'routes') else False
                if not is_core_api:
                    gaps.append({
                        "type": GAP_INFO,
                        "module": path.split("/")[-1],
                        "detail": f"API-Route '{path}' ohne korrespondierende Page",
                        "suggestion": f"Erstelle Page für {path}",
                    })

    # Coverage Summary
    total = len(all_module_names)
    with_admin = sum(1 for k, v in matrix.items() if not k.startswith("_") and v["has_admin"])
    with_storefront = sum(1 for k, v in matrix.items() if not k.startswith("_") and v["has_storefront"])
    with_api = sum(1 for k, v in matrix.items() if not k.startswith("_") and v["has_api"])
    with_detail_admin = sum(1 for k, v in matrix.items() if not k.startswith("_") and v["has_detail_admin"])

    matrix["_coverage"] = {
        "total_modules": total,
        "with_admin": with_admin,
        "with_storefront": with_storefront,
        "with_api": with_api,
        "with_detail_admin": with_detail_admin,
        "admin_coverage_pct": round(with_admin / total * 100, 1) if total else 0,
        "storefront_coverage_pct": round(with_storefront / total * 100, 1) if total else 0,
    }

    matrix["_gaps"] = _deduplicate_gaps(gaps)

    return matrix


def _deduplicate_gaps(gaps: List[Dict]) -> List[Dict]:
    """Entfernt Duplikate aus Gap-Liste."""
    seen = set()
    unique = []
    for gap in gaps:
        key = (gap["type"], gap["module"])
        if key not in seen:
            seen.add(key)
            unique.append(gap)
    return unique


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------

def format_coverage_report(matrix: CoverageMatrix) -> str:
    """Erzeugt lesbaren Coverage-Report als Text."""
    coverage = matrix.get("_coverage", {})
    gaps = matrix.get("_gaps", [])
    meta = matrix.get("_meta", {})

    lines = []
    lines.append("╔══════════════════════════════════════════════════╗")
    lines.append("║  UI Gap Analysis Report")
    lines.append(f"║  Projekt: {meta.get('project_root', '?')}")
    lines.append(f"║  UI-Layer: {meta.get('total_layers', 0)}")
    lines.append("╠══════════════════════════════════════════════════╣")

    # Coverage Overview
    lines.append("║  Coverage:")
    total = coverage.get("total_modules", 0)
    lines.append(f"║    {total} Backend-Module")
    lines.append(f"║    ✅ Admin UI:    {coverage.get('with_admin', 0)}/{total} ({coverage.get('admin_coverage_pct', 0)}%)")
    lines.append(f"║    ✅ Storefront:  {coverage.get('with_storefront', 0)}/{total} ({coverage.get('storefront_coverage_pct', 0)}%)")
    lines.append(f"║    🔄 API Routes:  {coverage.get('with_api', 0)}/{total}")
    lines.append(f"║    📋 Detail-View: {coverage.get('with_detail_admin', 0)}/{total}")
    lines.append("╠══════════════════════════════════════════════════╣")

    # Gaps by type
    for gap_type, label in GAP_LABELS.items():
        type_gaps = [g for g in gaps if g["type"] == gap_type]
        if type_gaps:
            lines.append(f"║  {gap_type} {label}:")
            for g in type_gaps[:10]:
                lines.append(f"║    • {g['module']} — {g['detail']}")
            if len(type_gaps) > 10:
                lines.append(f"║      ... und {len(type_gaps) - 10} weitere")
            lines.append("║")

    # Layer Details
    lines.append("╠══════════════════════════════════════════════════╣")
    lines.append("║  UI-Layer Details:")
    for layer in meta.get("layers_found", []):
        lines.append(f"║    [{layer['ui_type']}] {layer['name']}")
        lines.append(f"║      Routen: {len(layer['routes'])}")

    # Module→Page Mapping (Detail)
    lines.append("╠══════════════════════════════════════════════════╣")
    lines.append("║  Modul-Mapping:")
    for key in sorted(matrix.keys()):
        if key.startswith("_"):
            continue
        v = matrix[key]
        icons = []
        if v["has_admin"]:
            icons.append("✅A")
        else:
            icons.append("❌A")
        if v["has_storefront"]:
            icons.append("✅S")
        else:
            icons.append("❌S")
        if v["has_api"]:
            icons.append("✅API")
        else:
            icons.append("❌API")
        lines.append(f"║    {' '.join(icons)} {key}")

    lines.append("╚══════════════════════════════════════════════════╝")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    matrix = build_coverage_matrix(root)
