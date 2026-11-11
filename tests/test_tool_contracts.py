"""Tool-Contract-Gate: Description-Qualitaet, Enums, response_format.

Der Test ruft denselben Linter auf, den auch der Pre-Commit-Hook nutzen kann.
Damit kann die Regel nicht durch Schema-Drift verrotten.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[1]
LINTER = PLUGIN_DIR / "scripts" / "lint_tool_contracts.py"
REGISTRY = PLUGIN_DIR / "scout_tool_registry.json"
ANALYSIS_SCHEMAS = PLUGIN_DIR / "analysis" / "tools" / "schemas_data.json"


@pytest.fixture(scope="module")
def lint_result() -> dict:
    result = subprocess.run(
        [sys.executable, str(LINTER), "--json"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(PLUGIN_DIR),
    )
    assert result.stdout, f"Linter ohne Ausgabe: {result.stderr}"
    return json.loads(result.stdout)


def test_linter_has_no_violations(lint_result: dict) -> None:
    assert lint_result["violations"] == 0, (
        f"{lint_result['violations']} Verstoesse: "
        f"{json.dumps(lint_result['issues'][:8], indent=2, ensure_ascii=False)}"
    )


def test_linter_sees_all_tools(lint_result: dict) -> None:
    """42 Tools = 20 analysis + 13 bughunt + 9 research (Stand 0.6.0).

    Vorher 56: sechs 1:1-code_intel-Wrapper gestrichen, research von 17 auf 9
    konsolidiert (delete/tag/verify/merge/compare -> research_update(action=...),
    export_all -> research_export(all=true), auto/schedule -> P4).
    """
    assert lint_result["tools"] == 42, lint_result["tools"]


def test_descriptions_are_substantial() -> None:
    """Stichprobe ohne Linter: jede Description nennt mehr als nur den Namen."""
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    shortest = min(len(e["schema"]["description"]) for domain in reg.values() for e in domain)
    assert shortest >= 120, f"kuerzeste Description: {shortest} Zeichen"


def test_response_format_tools_declare_enum() -> None:
    """Wer response_format anbietet, muss beide Werte erlauben."""
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    schemas = [e["schema"] for domain in reg.values() for e in domain]
    schemas += list(json.loads(ANALYSIS_SCHEMAS.read_text(encoding="utf-8")).values())

    checked = 0
    for schema in schemas:
        props = (schema.get("parameters") or {}).get("properties") or {}
        rf = props.get("response_format")
        if not rf:
            continue
        checked += 1
        assert rf.get("enum") == ["concise", "detailed"], schema.get("name")
        assert rf.get("default") == "detailed", schema.get("name")
    assert checked >= 15, f"nur {checked} Tools mit response_format"


def test_no_tool_exceeds_param_budget() -> None:
    """AWS-Empfehlung: maximal 8 Parameter pro Tool."""
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    over = []
    for domain in reg.values():
        for entry in domain:
            params = (entry["schema"].get("parameters") or {}).get("properties") or {}
            if len(params) > 8:
                over.append((entry["name"], len(params)))
    assert not over, f"zu viele Parameter: {over}"
