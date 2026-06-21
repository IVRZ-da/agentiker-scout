"""Tests für ESLint/TypeScript-ESLint Bug-Patterns in data/patterns/typescript/eslint.yaml."""

import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_eslint_yaml() -> list:
    path = Path(__file__).parents[1] / "data" / "patterns" / "typescript" / "eslint.yaml"
    if not path.exists():
        return []
    with open(path) as f:
        data = yaml.safe_load(f)
    return data or []


class TestEslintYamlStructure:
    """Validiert die YAML-Struktur der ESLint-Patterns."""

    def test_file_exists(self):
        path = Path(__file__).parents[1] / "data" / "patterns" / "typescript" / "eslint.yaml"
        assert path.exists(), "eslint.yaml existiert nicht"

    def test_at_least_30_patterns(self):
        patterns = _load_eslint_yaml()
        assert len(patterns) >= 30, f"Nur {len(patterns)} Patterns (mind. 30 erwartet)"

    def test_all_have_required_fields(self):
        required = {"id", "cwe", "category", "severity", "languages", "title", "scan_query", "fix_description", "confidence"}
        for p in _load_eslint_yaml():
            missing = required - set(p.keys())
            assert not missing, f"{p['id']}: fehlende Felder: {missing}"

    def test_ids_have_correct_prefix(self):
        valid_prefixes = ("TS-", "SEC-", "HOOK-", "IMP-", "NOSEC-")
        for p in _load_eslint_yaml():
            assert any(p["id"].startswith(pre) for pre in valid_prefixes), \
                f"{p['id']}: ungültiger Prefix (nicht in {valid_prefixes})"

    def test_cwe_format(self):
        for p in _load_eslint_yaml():
            assert p["cwe"].startswith("CWE-"), f"{p['id']}: cwe '{p['cwe']}' beginnt nicht mit CWE-"
            parts = p["cwe"].split("-")
            assert len(parts) >= 2 and parts[1].isdigit(), f"{p['id']}: cwe '{p['cwe']}' hat keine Nummer"

    def test_severity_valid(self):
        valid = {"critical", "high", "medium", "low", "info"}
        for p in _load_eslint_yaml():
            assert p["severity"] in valid, f"{p['id']}: severity '{p['severity']}' ungültig"

    def test_confidence_valid(self):
        valid = {"high", "medium", "low"}
        for p in _load_eslint_yaml():
            assert p["confidence"] in valid, f"{p['id']}: confidence '{p['confidence']}' ungültig"

    def test_languages_ts_or_js(self):
        for p in _load_eslint_yaml():
            for lang in p["languages"]:
                assert lang in ("typescript", "javascript"), \
                    f"{p['id']}: language '{lang}' nicht in typescript/javascript"

    def test_scan_query_not_empty(self):
        for p in _load_eslint_yaml():
            assert p["scan_query"] and len(p["scan_query"]) > 2, \
                f"{p['id']}: scan_query zu kurz oder leer"

    def test_fix_description_not_empty(self):
        for p in _load_eslint_yaml():
            assert p["fix_description"] and len(p["fix_description"]) > 10, \
                f"{p['id']}: fix_description zu kurz"

    def test_unique_ids(self):
        patterns = _load_eslint_yaml()
        ids = [p["id"] for p in patterns]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {[i for i in ids if ids.count(i) > 1]}"

    def test_category_valid(self):
        valid_cats = {"security", "code-quality"}
        for p in _load_eslint_yaml():
            assert p["category"] in valid_cats, f"{p['id']}: category '{p['category']}' ungültig"


class TestEslintPatternLoaderIntegration:
    """Integration mit PatternLoader."""

    def test_loader_loads_eslint_patterns(self):
        from shared.pattern_loader import PatternLoader
        loader = PatternLoader(patterns_dir=str(Path(__file__).parents[1] / "data" / "patterns"))
        patterns = loader.load_all()
        esl_ids = {p.id for p in patterns if p.id.startswith(("TS-", "SEC-", "HOOK-", "IMP-", "NOSEC-"))}
        assert len(esl_ids) >= 30, f"Nur {len(esl_ids)} ESLint-Patterns im Loader"

    def test_eslint_filter_by_language_ts(self):
        from shared.pattern_loader import PatternLoader
        loader = PatternLoader(patterns_dir=str(Path(__file__).parents[1] / "data" / "patterns"))
        ts_patterns = loader.filter(languages=["typescript"])
        esl = [p for p in ts_patterns if p.id.startswith("TS-")]
        assert len(esl) >= 8, f"Nur {len(esl)} TS-spezifische Patterns"

    def test_eslint_filter_by_security(self):
        from shared.pattern_loader import PatternLoader
        loader = PatternLoader(patterns_dir=str(Path(__file__).parents[1] / "data" / "patterns"))
        sec = loader.filter(categories=["security"])
        esl_sec = [p for p in sec if p.id.startswith("SEC-")]
        assert len(esl_sec) >= 10, f"Nur {len(esl_sec)} Security-Patterns"


class TestEslintDistribution:
    """Verteilung über Kategorien."""

    def test_security_patterns_exist(self):
        patterns = _load_eslint_yaml()
        sec = [p for p in patterns if p["category"] == "security"]
        assert len(sec) >= 8, f"Nur {len(sec)} Security-Patterns (mind. 8 erwartet)"

    def test_code_quality_patterns_exist(self):
        patterns = _load_eslint_yaml()
        cq = [p for p in patterns if p["category"] == "code-quality"]
        assert len(cq) >= 10, f"Nur {len(cq)} Code-Quality-Patterns (mind. 10 erwartet)"

    def test_ts_only_no_javascript(self):
        patterns = _load_eslint_yaml()
        for p in patterns:
            if p["id"].startswith("TS-"):
                assert p["languages"] == ["typescript"], f"{p['id']}: sollte nur TS sein"

    def test_no_sec_duplicates(self):
        patterns = _load_eslint_yaml()
        sec_queries = [p["scan_query"] for p in patterns if p["category"] == "security"]
        # gleiche Queries für verschiedene Patterns können legitim sein
        # (z.B. eval kann von SEC-001 und SEC-009 erfasst werden)
        dups = len(sec_queries) - len(set(sec_queries))
        assert dups <= 3, f"Zu viele duplicate scan_queries in security: {dups}"
