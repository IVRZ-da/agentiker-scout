"""ui_gap.py — analysis_ui_gap Tool-Handler.

Kombiniert UI-Discovery, Route-Extraktion und Mapping in einem Aufruf.
Output als formatierter Text, JSON oder Mermaid-Diagramm.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

from scout._fmt import fmt_err, fmt_ok, fmt_warn

from .mapping import build_coverage_matrix, format_coverage_report
from .ui_discovery import discover_uis

logger = logging.getLogger("analysis.ui_gap")


# ---------------------------------------------------------------------------
# plan_follow Integration (lose Kopplung via Registry)
# ---------------------------------------------------------------------------


def _try_generate_plan_from_gaps(project_root: str, gaps: List[Dict]) -> Optional[dict]:
    """Erzeugt einen Plan aus gefundenen UI-Gaps via Registry (plan_follow).

    Silent skip wenn plan_follow nicht geladen ist.
    """
    min(len(gaps), 10)  # Max 10 Tasks pro Plan
    critical = [g for g in gaps if g["type"] == "🔴"][:3]
    warnings = [g for g in gaps if g["type"] in ("🟡", "🟠", "🔵")][:4]
    infos = [g for g in gaps if g["type"] == "🟢"][:3]

    tasks = []
    for g in critical:
        tasks.append(f"🔴 {g['module']}: {g['detail']}")
    for g in warnings:
        tasks.append(f"🟡 {g['module']}: {g['detail']}")
    for g in infos:
        tasks.append(f"🟢 {g['module']}: {g['detail']}")

    try:
        from tools.registry import registry
        entry = registry.get_entry("plan_create")
        if entry is None:
            return None
        handler = getattr(entry, "handler", None)
        if not callable(handler):
            return None

        plan_tasks = []
        for i, g in enumerate(critical + warnings + infos[:3]):
            plan_tasks.append({
                "id": f"gap-{i+1}",
                "name": f"{g['type']} {g['module']}: {g['detail'][:60]}",
                "verify": "",
                "files": [project_root],
            })

        result = handler({
            "goal": f"UI-Gaps beheben ({len(gaps)} Lücken in {os.path.basename(project_root)})",
            "tasks": plan_tasks,
        })
        if isinstance(result, str):
            import json
            parsed = json.loads(result)
            return parsed if isinstance(parsed, dict) else None
        return result
    except ImportError:
        return None
    except Exception as e:
        logger.info("plan_follow integration skipped: %s", e)
        return None


# ---------------------------------------------------------------------------
# Main Tool
# ---------------------------------------------------------------------------


def analysis_ui_gap_tool(args: dict, **kwargs) -> str:
    """analysis_ui_gap — Erkennt UI-Layer, extrahiert Routen, identifiziert Coverage-Gaps.

    Args:
        path: Absoluter Pfad zum Projekt-Root
        format: Output-Format (text/json/mermaid)
        include_storefront: Storefront-Routen einbeziehen
        include_admin: Admin-Routen einbeziehen
    """
    path = args.get("path", "")
    output_format = args.get("format", "text")
    args.get("include_storefront", True)
    args.get("include_admin", True)

    if not path:
        return fmt_err("Path is required")

    if not os.path.isdir(path):
        return fmt_err(f"Path not found: {path}")

    try:
        # 1️⃣ UI-Layer discoveren
        layers = discover_uis(path)

        if not layers:
            return fmt_warn(f"Keine UI-Layer in '{path}' gefunden.")

        # 2️⃣ Coverage-Matrix bauen
        matrix = build_coverage_matrix(path)

        # 3️⃣ Plan generieren (wenn Gaps existieren)
        gaps = matrix.get("_gaps", [])
        if not isinstance(gaps, list):
            gaps = []
        if gaps:
            _try_generate_plan_from_gaps(path, gaps)

        # 4️⃣ Output formatieren
        if output_format == "json":
            return fmt_ok({"format": "json", "data": _clean_matrix(matrix)})

        elif output_format == "mermaid":
            mermaid = _generate_mermaid(matrix, path)
            return fmt_ok({"format": "mermaid", "diagram": mermaid})

        else:  # text (default)
            report = format_coverage_report(matrix)
            summary = _generate_summary(matrix, layers)
            return fmt_ok({
                "format": "text",
                "report": report + "\n" + summary,
                "layers": len(layers),
                "total_routes": sum(len(l.routes) for l in layers),
                "total_modules": matrix.get("_coverage", {}).get("total_modules", 0),
                "admin_coverage_pct": matrix.get("_coverage", {}).get("admin_coverage_pct", 0),
                "storefront_coverage_pct": matrix.get("_coverage", {}).get("storefront_coverage_pct", 0),
                "gap_count": len(matrix.get("_gaps", [])),
            })

    except Exception as e:
        logger.exception("analysis_ui_gap failed")
        return fmt_err(f"UI Gap Analysis fehlgeschlagen: {e}")


def _clean_matrix(matrix: dict) -> dict:
    """Entfernt interne _prefixed Keys für JSON-Output."""
    cleaned = {}
    for key, value in matrix.items():
        if key == "_meta":
            continue
        if key == "_coverage":
            cleaned["coverage"] = value
        elif key == "_gaps":
            cleaned["gaps"] = value
        else:
            entry = dict(value)
            # Entferne große Listen für JSON-Übersicht
            entry.pop("admin_pages", None)
            entry.pop("storefront_pages", None)
            entry.pop("api_routes", None)
            cleaned[key] = entry
    return cleaned


def _generate_mermaid(matrix: dict, project_root: str) -> str:
    """Generiert ein Mermaid-Diagramm der UI-Gap-Analyse."""
    coverage = matrix.get("_coverage", {})
    gaps = matrix.get("_gaps", [])
    meta = matrix.get("_meta", {})

    lines = [
        "graph TD",
        f'    P[\"{os.path.basename(project_root)}\"]',
        "",
        "    subgraph UIs[UI-Layer]",
    ]

    for layer in meta.get("layers_found", []):
        safe_name = layer["name"].replace("-", "_").replace(" ", "_")
        route_count = len(layer["routes"])
        layer_label = layer["name"]
        lines.append(f'        L_{safe_name}["{layer_label} ({route_count}r)"]')
        lines.append(f'        P --> L_{safe_name}')

    lines.extend([
        "",
        "    subgraph Coverage[Coverage]",
        f'        C1["Admin UI: {coverage.get("admin_coverage_pct", 0)}%"]',
        f'        C2["Storefront: {coverage.get("storefront_coverage_pct", 0)}%"]',
        "    end",
    ])

    if gaps:
        lines.extend([
            "",
            "    subgraph Gaps[Gefundene Lücken]",
        ])
        for i, gap in enumerate(gaps[:5]):
            gap["module"].replace("-", "_").replace(" ", "_")
            gap_type = gap["type"]
            lines.append(f'        G{i}["{gap_type} {gap["module"]}"]')
        lines.append("    end")

    return "\n".join(lines)


def _generate_summary(matrix: dict, layers: list) -> str:
    """Erzeugt eine kompakte Zusammenfassung der Analyse."""
    coverage = matrix.get("_coverage", {})
    gaps = matrix.get("_gaps", [])

    lines = [
        "\n" + "=" * 60,
        "📊 ZUSAMMENFASSUNG",
        "=" * 60,
    ]

    # Coverage
    lines.append(f"Backend-Module: {coverage.get('total_modules', 0)}")
    lines.append(f"Admin UI:       {coverage.get('with_admin', 0)}/{coverage.get('total_modules', 0)} ({coverage.get('admin_coverage_pct', 0)}%)")
    lines.append(f"Storefront:     {coverage.get('with_storefront', 0)}/{coverage.get('total_modules', 0)} ({coverage.get('storefront_coverage_pct', 0)}%)")
    lines.append(f"Detail-Views:   {coverage.get('with_detail_admin', 0)}/{coverage.get('total_modules', 0)}")

    # Gap-Zusammenfassung
    if gaps:
        lines.append("")
        for gap_type, label in [
            ("🔴", "Critical (Admin fehlt)"),
            ("🟡", "Warning (Storefront fehlt)"),
            ("🟢", "Info (API ohne Page)"),
            ("🟠", "Orphan (Page ohne Module)"),
            ("🔵", "Missing Detail"),
        ]:
            count = len([g for g in gaps if g["type"] == gap_type])
            if count:
                lines.append(f"  {gap_type} {label}: {count}")

    lines.append("=" * 60)
    return "\n".join(lines)
