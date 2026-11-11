#!/usr/bin/env python3
"""Prueft die Pattern-Bibliothek auf Vollstaendigkeit und Konsistenz.

Ein Pattern ohne ``false_positive_notes`` ist im Betrieb wertlos: der Agent
meldet dann jeden Treffer als Fund, auch wenn es ein bekanntes Artefakt ist.
Dieser Lint macht die Notes zur Pflicht, damit sie nicht wieder abwandern.

Aufruf:
    python3 scripts/lint_patterns.py           # Report + Exit-Code
    python3 scripts/lint_patterns.py --json    # maschinenlesbar
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
PATTERNS_FILE = PLUGIN_ROOT / "bughunt" / "data" / "patterns_data.json"

MIN_NOTES_CHARS = 20
VALID_SEVERITIES = {"P0", "P1", "P2", "P3", "INFO"}
#: grep/manual/semgrep plus alle code_intel-Tools (Praefix "code_").
VALID_SCAN_TYPES = {"grep", "manual", "semgrep"}
REQUIRED_FIELDS = ("pattern_id", "name", "category", "severity", "description")


def load_patterns(path: Path = PATTERNS_FILE) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    groups = data.get("patterns", data)
    if isinstance(groups, dict):
        return [p for group in groups.values() for p in group]
    return list(groups)


WARNINGS: list[str] = []


def check(patterns: list[dict]) -> list[dict]:
    """Liefert Verstoesse als [{pattern_id, rule, message}]."""
    violations: list[dict] = []
    seen: dict[str, str] = {}

    for pattern in patterns:
        pid = pattern.get("pattern_id", "<ohne id>")

        for field in REQUIRED_FIELDS:
            if not pattern.get(field):
                violations.append({"pattern_id": pid, "rule": "R1",
                                   "message": f"Pflichtfeld '{field}' fehlt"})

        pid_value = pattern.get("pattern_id")
        if pid_value:
            if pid_value in seen:
                violations.append({"pattern_id": pid, "rule": "R2",
                                   "message": "pattern_id doppelt vergeben"})
            seen[pid_value] = pattern.get("name", "")

        notes = pattern.get("false_positive_notes") or ""
        if len(notes.strip()) < MIN_NOTES_CHARS:
            violations.append({
                "pattern_id": pid, "rule": "R3",
                "message": f"false_positive_notes fehlen oder zu kurz "
                           f"({len(notes.strip())} < {MIN_NOTES_CHARS} Zeichen)",
            })

        severity = pattern.get("severity")
        if severity and severity not in VALID_SEVERITIES:
            violations.append({"pattern_id": pid, "rule": "R4",
                               "message": f"unbekannte severity '{severity}'"})

        scan_type = pattern.get("scan_type", "")
        if scan_type and scan_type not in VALID_SCAN_TYPES and not scan_type.startswith("code_"):
            violations.append({"pattern_id": pid, "rule": "R5",
                               "message": f"unbekannter scan_type '{scan_type}'"})

        if scan_type == "grep" and not pattern.get("scan_query"):
            violations.append({"pattern_id": pid, "rule": "R6",
                               "message": "scan_type=grep ohne scan_query"})

        query = pattern.get("scan_query") or ""
        if query:
            try:
                re.compile(query)
            except re.error:
                # Kein Verstoss: das Pattern ist gueltiges grep-BRE, nur kein
                # Python-Regex. Die Treffer-Zuordnung faellt dann auf den
                # Literal-Text zurueck (shared/grep_batch.py).
                WARNINGS.append(pid)

    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="JSON-Ausgabe")
    parser.add_argument("--list", action="store_true", help="alle Patterns auflisten")
    args = parser.parse_args(argv)

    patterns = load_patterns()
    violations = check(patterns)

    if args.list:
        for pattern in patterns:
            print(f"{pattern.get('pattern_id', '?'):>8}  "
                  f"{pattern.get('severity', '?'):<5}  {pattern.get('name', '')}")
        return 0

    if args.json:
        print(json.dumps({
            "patterns": len(patterns),
            "violations": len(violations),
            "by_rule": _by_rule(violations),
            "details": violations,
        }, indent=2, ensure_ascii=False))
        return 1 if violations else 0

    print(f"Patterns geprueft: {len(patterns)}   Verstoesse: {len(violations)}")
    if WARNINGS:
        print(f"  Hinweis: {len(WARNINGS)} Patterns sind grep-BRE, kein Python-Regex "
              f"(Literal-Fallback): {', '.join(WARNINGS)}")
    if violations:
        print("\nnach Regel:", _by_rule(violations))
        for violation in violations:
            print(f"  [{violation['rule']}] {violation['pattern_id']:<8} {violation['message']}")
        return 1

    categories = sorted({p.get("category", "") for p in patterns})
    print(f"Kategorien: {len(categories)} — {', '.join(c for c in categories if c)}")
    print("Alle Patterns haben Notes, gueltige Severity und eindeutige IDs.")
    return 0


def _by_rule(violations: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for violation in violations:
        counts[violation["rule"]] = counts.get(violation["rule"], 0) + 1
    return counts


if __name__ == "__main__":
    sys.exit(main())
