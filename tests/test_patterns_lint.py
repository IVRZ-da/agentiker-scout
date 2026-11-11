"""Pattern-Bibliothek: Pflicht-Notes, eindeutige IDs, ausfuehrbare Scans.

Ein Pattern ohne ``false_positive_notes`` ist im Betrieb wertlos — der Agent
meldet dann jeden Treffer als Fund. Der Lint haelt diese Regel in der Suite.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
PATTERNS_FILE = PLUGIN_ROOT / "bughunt" / "data" / "patterns_data.json"
LINT = PLUGIN_ROOT / "scripts" / "lint_patterns.py"


def _load() -> list[dict]:
    data = json.loads(PATTERNS_FILE.read_text(encoding="utf-8"))
    groups = data.get("patterns", data)
    if isinstance(groups, dict):
        return [p for group in groups.values() for p in group]
    return list(groups)


@pytest.fixture(scope="module")
def patterns() -> list[dict]:
    return _load()


@pytest.fixture(scope="module")
def lint_result() -> dict:
    proc = subprocess.run(
        [sys.executable, str(LINT), "--json"],
        capture_output=True, text=True, timeout=60,
    )
    return json.loads(proc.stdout)


def test_lint_has_no_violations(lint_result):
    assert lint_result["violations"] == 0, lint_result["details"]


def test_every_pattern_has_false_positive_notes(patterns):
    without = [p["pattern_id"] for p in patterns if not (p.get("false_positive_notes") or "").strip()]
    assert without == [], f"Patterns ohne false_positive_notes: {without}"


def test_pattern_ids_are_unique(patterns):
    ids = [p.get("pattern_id") for p in patterns]
    assert len(ids) == len(set(ids)), "doppelte pattern_id"


def test_severities_are_valid(patterns):
    valid = {"P0", "P1", "P2", "P3", "INFO"}
    bad = [(p["pattern_id"], p.get("severity")) for p in patterns if p.get("severity") not in valid]
    assert bad == [], bad


def test_grep_patterns_have_query(patterns):
    bad = [p["pattern_id"] for p in patterns
           if p.get("scan_type") in ("grep", "code_search") and not p.get("scan_query")]
    assert bad == [], bad
