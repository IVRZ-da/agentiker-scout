#!/usr/bin/env python3
"""
Convert semgrep-rules (from /tmp/semgrep-rules) to Hermes Scout YAML pattern files.

Outputs:
  - data/patterns/security/semgrep.yaml        (security rules)
  - data/patterns/code-quality/semgrep-q.yaml   (correctness rules)

Filters:
  - Languages: python, javascript, typescript, go, rust
  - Categories: security, correctness
  - Skips taint-mode rules (mode: taint)
  - Uses simple ``pattern:`` entries (extracts from patterns/pattern-either where possible)
  - Limits to ~500 rules
"""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, List, Optional, Tuple

import yaml

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("semgrep-convert")

# ── Paths ───────────────────────────────────────────────────────────────────
SEMGREP_DIR = Path("/tmp/semgrep-rules")
SCOUT_DIR = Path(os.path.expanduser("~/.hermes/plugins/scout"))
OUTPUT_SECURITY = SCOUT_DIR / "data" / "patterns" / "security" / "semgrep.yaml"
OUTPUT_QUALITY = SCOUT_DIR / "data" / "patterns" / "code-quality" / "semgrep-q.yaml"

# Supported languages for bug_hunt_scan
SUPPORTED_LANGUAGES = frozenset({"python", "javascript", "typescript", "go", "rust"})

# Semgrep severity → Scout severity
SEVERITY_MAP = {
    "ERROR": "critical",
    "WARNING": "high",
    "INFO": "medium",
}

# Keys that make a pattern dict "complex" (not a simple grep pattern)
COMPLEX_PATTERN_KEYS = frozenset({
    "pattern-inside", "pattern-not", "pattern-not-inside", "pattern-regex",
    "pattern-sources", "pattern-sinks", "pattern-sanitizers",
    "metavariable-regex", "metavariable-pattern", "metavariable-comparison",
    "focus-metavariable", "pattern-not-regex",
})

# ── Helpers ─────────────────────────────────────────────────────────────────


def is_simple_pattern_item(item: Any) -> bool:
    """Return True if *item* is a dict with ONLY a ``pattern`` key."""
    return isinstance(item, dict) and "pattern" in item and len(item) == 1 and isinstance(item["pattern"], str)


def extract_all_simple_patterns(rule: dict) -> Optional[str]:
    """Extract a usable scan_query from a semgrep rule.

    Strategy:
      - Top-level ``pattern:`` → use directly.
      - Top-level ``pattern-either:`` with simple sub-patterns → join with ``|``.
      - ``patterns:`` list → collect all ``pattern:`` entries (skip pattern-inside/not etc).
      - If no simple pattern entries exist, return None.

    Returns a combined pattern string or None.
    """
    parts: List[str] = []

    # 1. Top-level pattern
    if "pattern" in rule and isinstance(rule["pattern"], str):
        parts.append(rule["pattern"])

    # 2. Top-level pattern-either
    if "pattern-either" in rule:
        pats = rule["pattern-either"]
        if isinstance(pats, list):
            for p in pats:
                if is_simple_pattern_item(p):
                    parts.append(p["pattern"])

    # 3. patterns list
    if "patterns" in rule:
        pats = rule["patterns"]
        if isinstance(pats, list):
            for p in pats:
                if is_simple_pattern_item(p):
                    parts.append(p["pattern"])
                elif isinstance(p, dict) and "pattern-either" in p:
                    subs = p["pattern-either"]
                    if isinstance(subs, list):
                        for s in subs:
                            if is_simple_pattern_item(s):
                                parts.append(s["pattern"])

    if parts:
        # Normalize: collapse newlines, extra whitespace, and trim
        normalized = "|".join(parts)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized
    return None


def extract_cwe(metadata: dict) -> str:
    """Extract CWE number from metadata."""
    cwe_raw = metadata.get("cwe") or metadata.get("cwe_id") or ""
    if isinstance(cwe_raw, list):
        for entry in cwe_raw:
            m = re.match(r"(CWE-\d+)", str(entry))
            if m:
                return m.group(1)
    elif isinstance(cwe_raw, str):
        m = re.match(r"(CWE-\d+)", cwe_raw)
        if m:
            return m.group(1)
    return "CWE-000"


def extract_fix(rule: dict) -> str:
    """Extract fix description from rule."""
    if "fix" in rule and isinstance(rule["fix"], str):
        fix = rule["fix"].strip()
        if fix:
            return fix
    if "fix-regex" in rule and isinstance(rule["fix-regex"], dict):
        regex = rule["fix-regex"].get("regex", "")
        replacement = rule["fix-regex"].get("replacement", "")
        if regex and replacement:
            return f"Replace '{regex}' with '{replacement}'"
    return ""


def map_confidence(metadata: dict) -> str:
    """Map semgrep confidence to scout confidence."""
    conf = str(metadata.get("confidence", "MEDIUM")).upper()
    mapping = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
    return mapping.get(conf, "medium")


def rule_id_to_scout_id(rule_id: str) -> str:
    """Create a scout pattern ID from a semgrep rule ID."""
    safe = re.sub(r"[^a-zA-Z0-9-]", "-", rule_id)
    safe = re.sub(r"-+", "-", safe).strip("-").lower()
    if not safe:
        safe = "unknown"
    return f"semgrep-{safe[:50]}"


def collect_rules() -> Tuple[List[dict], List[dict]]:
    """Collect and convert semgrep rules.

    Returns:
        Tuple of (security_rules, correctness_rules) as dicts ready for YAML output.
    """
    if not SEMGREP_DIR.is_dir():
        logger.error("Semgrep rules dir not found: %s", SEMGREP_DIR)
        logger.error("Run: git clone --depth 1 https://github.com/semgrep/semgrep-rules.git /tmp/semgrep-rules")
        sys.exit(1)

    # Find all YAML rule files (exclude .test.yaml)
    yaml_files: List[Path] = []
    for lang in SUPPORTED_LANGUAGES:
        for f in sorted(SEMGREP_DIR.glob(f"{lang}/**/*.yaml")):
            if ".test." in f.name:
                continue
            yaml_files.append(f)
        for f in sorted(SEMGREP_DIR.glob(f"{lang}/**/*.yml")):
            if ".test." in f.name:
                continue
            yaml_files.append(f)

    if not yaml_files:
        logger.error("No YAML rule files found in %s for languages %s", SEMGREP_DIR, SUPPORTED_LANGUAGES)
        sys.exit(1)

    logger.info("Found %d YAML files in semgrep rules", len(yaml_files))

    security_entries: List[dict] = []
    quality_entries: List[dict] = []
    skipped_no_pattern = 0
    skipped_taint = 0
    skipped_category = 0
    skipped_language = 0
    skipped_other = 0
    seen_ids: set[str] = set()

    MAX_RULES = 500
    counter = 0

    for filepath in yaml_files:
        if counter >= MAX_RULES:
            break

        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh)
        except Exception as e:
            logger.debug("YAML parse error in %s: %s", filepath.name, e)
            skipped_other += 1
            continue

        if not raw or not isinstance(raw, dict):
            continue

        for rule in raw.get("rules", []):
            if counter >= MAX_RULES:
                break

            if not isinstance(rule, dict):
                continue

            # ── Filter: Category ────────────────────────────────────────────
            metadata = rule.get("metadata") or {}
            if not isinstance(metadata, dict):
                metadata = {}

            category = str(metadata.get("category", "")).lower()
            # Map semgrep categories to scout categories
            category_map = {
                "security": "security",
                "correctness": "code-quality",
                "best-practice": "code-quality",
            }
            mapped_category = category_map.get(category)
            if mapped_category is None:
                skipped_category += 1
                continue

            # ── Filter: Languages ───────────────────────────────────────────
            languages = rule.get("languages") or []
            if not isinstance(languages, list):
                languages = [str(languages)]

            if not any(l in SUPPORTED_LANGUAGES for l in languages):  # noqa: E741
                skipped_language += 1
                continue

            # ── Filter: Taint mode ──────────────────────────────────────────
            if rule.get("mode") == "taint" or "pattern-sources" in rule or "pattern-sinks" in rule:
                skipped_taint += 1
                continue

            # ── Extract scan query ──────────────────────────────────────────
            scan_query = extract_all_simple_patterns(rule)
            if not scan_query:
                skipped_no_pattern += 1
                continue

            # ── Build entry ─────────────────────────────────────────────────
            rule_id = rule.get("id", f"unknown-{counter}")
            pid = rule_id_to_scout_id(rule_id)

            if pid in seen_ids:
                pid = f"{pid}-{counter}"
            seen_ids.add(pid)

            severity_raw = str(rule.get("severity", "WARNING")).upper()
            severity = SEVERITY_MAP.get(severity_raw, "medium")

            cwe = extract_cwe(metadata)
            title = str(rule.get("message", "")).strip().replace("\n", " ")[:200]
            fix_desc = extract_fix(rule)
            confidence = map_confidence(metadata)

            entry = {
                "id": pid,
                "cwe": cwe,
                "category": mapped_category,
                "severity": severity,
                "languages": [l for l in languages if l in SUPPORTED_LANGUAGES],  # noqa: E741
                "title": title,
                "scan_query": scan_query,
                "fix_description": fix_desc,
                "confidence": confidence,
            }

            if mapped_category == "security":
                security_entries.append(entry)
            else:
                quality_entries.append(entry)

            counter += 1

    logger.info(
        "Scanned rules: %d extracted, %d taint, %d bad-category, "
        "%d bad-language, %d no-pattern, %d other-err",
        counter,
        skipped_taint,
        skipped_category,
        skipped_language,
        skipped_no_pattern,
        skipped_other,
    )
    logger.info("Security: %d rules, Correctness: %d rules", len(security_entries), len(quality_entries))

    return security_entries, quality_entries


def write_yaml(entries: List[dict], output_path: Path) -> int:
    """Write a list of pattern entries to a YAML file."""
    if not entries:
        logger.info("No entries for %s — skipping", output_path.name)
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("# Semgrep Rules — auto-converted by convert_semgrep_rules.py\n")
        fh.write(f"# Total: {len(entries)} rules\n\n")
        # Use yaml.dump with formatting options
        yaml.dump(entries, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)

    written = len(entries)
    logger.info("Wrote %d rules to %s", written, output_path)
    return written


def main() -> None:
    logger.info("Starting semgrep → scout pattern conversion")
    logger.info("Source: %s", SEMGREP_DIR)
    logger.info("Output security: %s", OUTPUT_SECURITY)
    logger.info("Output quality: %s", OUTPUT_QUALITY)

    security_entries, quality_entries = collect_rules()

    total = 0
    total += write_yaml(security_entries, OUTPUT_SECURITY)
    total += write_yaml(quality_entries, OUTPUT_QUALITY)

    print(f"\n{'=' * 60}")
    print(f"✅ Conversion complete: {total} rules written")
    print(f"   Security: {OUTPUT_SECURITY}")
    print(f"   Quality:  {OUTPUT_QUALITY}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
