"""analysis_migration Tool — YAML-basierte Bulk Migration.

Wrapper für code_migration mit Dry-Run Support.
"""
from __future__ import annotations

import logging
from typing import Any

from scout._fmt import fmt_err, fmt_ok

from .base import _call_tool, _validate_and_resolve_path

logger = logging.getLogger("analysis")


def analysis_migration_tool(args: dict, **kwargs) -> str:
    """Führt Bulk-Migrationen via ast-grep aus."""
    path = args.get("path", "")
    rules = args.get("rules", [])
    dry_run = args.get("dry_run", True)

    if not rules:
        return fmt_err("At least one migration rule is required")

    path_error, resolved_path = _validate_and_resolve_path(path)
    if path_error:
        return fmt_err(f"{path_error} (path: {path})")
    path = resolved_path

    result: dict[str, Any] = {
        "path": path,
        "rules_count": len(rules),
        "dry_run": dry_run,
        "status": {},
    }

    try:
        migration = _call_tool(
            "code_migration",
            path=path,
            rules=rules,
            dry_run=dry_run,
        )
        if isinstance(migration, dict) and "error" in migration:
            return fmt_err(f"{migration['error']} (tool: {migration.get('tool', 'code_migration')})")
        if migration:
            result["status"] = migration if isinstance(migration, dict) else {"raw": str(migration)[:500]}
    except Exception as e:
        logger.warning("code_migration failed: %s", e)
        return fmt_err(f"Migration failed: {e}")

    parts = [f"🔄 Migration: {len(rules)} Regeln"]
    parts.append(f"  Dry-Run: {'ja' if dry_run else 'nein'}")
    result["summary"] = "\n".join(parts)

    return fmt_ok(result)
