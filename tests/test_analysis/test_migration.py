"""Tests für analysis_migration_tool."""
from __future__ import annotations

from scout.analysis.tools.migration import analysis_migration_tool


def _parse(raw: str) -> dict:
    import json
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"status": "error", "raw": raw}


class TestAnalysisMigration:
    def test_requires_path(self):
        result = analysis_migration_tool({})
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_requires_rules(self):
        result = analysis_migration_tool({
            "path": "/home/jo/.hermes/plugins/scout",
        })
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_output_structure(self):
        result = analysis_migration_tool({
            "path": "/home/jo/.hermes/plugins/scout",
            "rules": [
                {
                    "name": "test-rule",
                    "pattern": "console.log($ARG)",
                    "rewrite": "console.info($ARG)",
                    "file_glob": "**/*.ts",
                }
            ],
        })
        parsed = _parse(result)
        # The mocked registry returns {"status": "mocked"}, which ends up
        # as the "status" field in the output (overwriting fmt_ok's "ok")
        assert "path" in parsed
        assert parsed.get("rules_count") == 1
        assert "dry_run" in parsed
        assert "summary" in parsed

    def test_output_size(self):
        result = analysis_migration_tool({
            "path": "/home/jo/.hermes/plugins/scout",
            "rules": [
                {
                    "name": "test-rule",
                    "pattern": "console.log($ARG)",
                    "rewrite": "console.info($ARG)",
                    "file_glob": "**/*.ts",
                }
            ],
        })
        assert len(result) < 3000, f"Output zu lang: {len(result)}"

    def test_invalid_path_traversal(self):
        result = analysis_migration_tool({
            "path": "../../etc/passwd",
            "rules": [{"pattern": "x", "rewrite": "y"}],
        })
        parsed = _parse(result)
        assert parsed.get("status") == "error"

    def test_dry_run_true_by_default(self):
        result = analysis_migration_tool({
            "path": "/home/jo/.hermes/plugins/scout",
            "rules": [
                {
                    "pattern": "old_func($$$ARGS)",
                    "rewrite": "new_func($$$ARGS)",
                    "file_glob": "**/*.py",
                }
            ],
        })
        parsed = _parse(result)
        assert parsed.get("dry_run") is True

    def test_with_dry_run_false(self):
        result = analysis_migration_tool({
            "path": "/home/jo/.hermes/plugins/scout",
            "rules": [
                {
                    "pattern": "old_func($$$ARGS)",
                    "rewrite": "new_func($$$ARGS)",
                    "file_glob": "**/*.py",
                }
            ],
            "dry_run": False,
        })
        parsed = _parse(result)
        assert parsed.get("dry_run") is False
