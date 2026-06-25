"""Tests für den Semgrep → Scout Pattern Converter.

Testet:
- Script ist ausführbar (exit code 0)
- Konvertierte YAML-Dateien existieren
- YAML ist valide
- Pattern IDs haben "semgrep-" prefix
- Patterns haben scan_query, title, category
- Valide CWE-IDs
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

SCRIPT_DIR = Path(__file__).resolve().parent.parent
SCOUT_DIR = SCRIPT_DIR
SCRIPTS_DIR = SCOUT_DIR / "scripts"
DATA_DIR = SCOUT_DIR / "data" / "patterns"

SECURITY_YAML = DATA_DIR / "security" / "semgrep.yaml"
QUALITY_YAML = DATA_DIR / "code-quality" / "semgrep-q.yaml"

CWE_PATTERN = re.compile(r"^CWE-\d+$")

# ── Fixtures ────────────────────────────────────────────────────────────────


def _load_yaml(path: Path) -> list[dict]:
    """Load and validate a YAML pattern file."""
    assert path.exists(), f"Datei nicht gefunden: {path}"
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    assert isinstance(data, list), f"Erwartete Liste in {path}, bekam {type(data).__name__}"
    return data


@pytest.fixture(scope="module")
def security_patterns() -> list[dict]:
    return _load_yaml(SECURITY_YAML)


@pytest.fixture(scope="module")
def quality_patterns() -> list[dict]:
    return _load_yaml(QUALITY_YAML)


# ── Tests ───────────────────────────────────────────────────────────────────


class TestScriptExecutable:
    """Kein Script mehr — wurde gelöscht (Dead Code)."""
    pass


class TestYamlFiles:
    """Konvertierte YAML-Dateien existieren und sind valide."""

    def test_security_yaml_exists(self):
        assert SECURITY_YAML.exists(), f"{SECURITY_YAML} nicht gefunden"

    def test_quality_yaml_exists(self):
        assert QUALITY_YAML.exists(), f"{QUALITY_YAML} nicht gefunden"

    def test_security_yaml_valid(self, security_patterns):
        assert len(security_patterns) > 0, "Security YAML ist leer"

    def test_quality_yaml_valid(self, quality_patterns):
        assert len(quality_patterns) > 0, "Quality YAML ist leer"


class TestPatternIds:
    """Pattern IDs haben "semgrep-" prefix."""

    def test_security_ids_have_prefix(self, security_patterns):
        for entry in security_patterns:
            pid = entry.get("id", "")
            assert pid.startswith("semgrep-"), \
                f"Security pattern '{pid}' hat nicht 'semgrep-' prefix"

    def test_quality_ids_have_prefix(self, quality_patterns):
        for entry in quality_patterns:
            pid = entry.get("id", "")
            assert pid.startswith("semgrep-"), \
                f"Quality pattern '{pid}' hat nicht 'semgrep-' prefix"

    def test_security_ids_unique(self, security_patterns):
        ids = [e["id"] for e in security_patterns if "id" in e]
        assert len(ids) == len(set(ids)), "Duplicate IDs in security patterns"

    def test_quality_ids_unique(self, quality_patterns):
        ids = [e["id"] for e in quality_patterns if "id" in e]
        assert len(ids) == len(set(ids)), "Duplicate IDs in quality patterns"


class TestRequiredFields:
    """Patterns haben mindestens scan_query, title, category."""

    REQUIRED = frozenset({"scan_query", "title", "category", "id", "cwe", "severity", "languages", "confidence"})

    @pytest.mark.parametrize("field", REQUIRED)
    def test_security_has_field(self, security_patterns, field):
        for entry in security_patterns:
            assert field in entry, \
                f"Security pattern '{entry.get('id', '?')}' fehlt Feld '{field}'"

    @pytest.mark.parametrize("field", REQUIRED)
    def test_quality_has_field(self, quality_patterns, field):
        for entry in quality_patterns:
            assert field in entry, \
                f"Quality pattern '{entry.get('id', '?')}' fehlt Feld '{field}'"

    def test_security_scan_query_not_empty(self, security_patterns):
        for entry in security_patterns:
            assert entry.get("scan_query"), \
                f"Security pattern '{entry.get('id', '?')}' hat leeres scan_query"

    def test_quality_scan_query_not_empty(self, quality_patterns):
        for entry in quality_patterns:
            assert entry.get("scan_query"), \
                f"Quality pattern '{entry.get('id', '?')}' hat leeres scan_query"

    def test_security_title_not_empty(self, security_patterns):
        for entry in security_patterns:
            assert entry.get("title"), \
                f"Security pattern '{entry.get('id', '?')}' hat leeres title"

    def test_quality_title_not_empty(self, quality_patterns):
        for entry in quality_patterns:
            assert entry.get("title"), \
                f"Quality pattern '{entry.get('id', '?')}' hat leeres title"

    def test_security_languages_not_empty(self, security_patterns):
        for entry in security_patterns:
            langs = entry.get("languages", [])
            assert isinstance(langs, list) and len(langs) > 0, \
                f"Security pattern '{entry.get('id', '?')}' hat keine languages"


class TestCweValidation:
    """Valide CWE-IDs."""

    def test_security_cwe_format(self, security_patterns):
        for entry in security_patterns:
            cwe = entry.get("cwe", "")
            assert CWE_PATTERN.match(cwe), \
                f"Security pattern '{entry.get('id', '?')}' hat ungültiges CWE: '{cwe}'"

    def test_quality_cwe_format(self, quality_patterns):
        for entry in quality_patterns:
            cwe = entry.get("cwe", "")
            assert CWE_PATTERN.match(cwe), \
                f"Quality pattern '{entry.get('id', '?')}' hat ungültiges CWE: '{cwe}'"


class TestSeverityValidation:
    """Valide Severity-Werte."""

    VALID_SEVERITIES = frozenset({"critical", "high", "medium", "low", "info"})

    def test_security_severity(self, security_patterns):
        for entry in security_patterns:
            sev = entry.get("severity", "")
            assert sev in self.VALID_SEVERITIES, \
                f"Security pattern '{entry.get('id', '?')}' hat ungültiges severity: '{sev}'"

    def test_quality_severity(self, quality_patterns):
        for entry in quality_patterns:
            sev = entry.get("severity", "")
            assert sev in self.VALID_SEVERITIES, \
                f"Quality pattern '{entry.get('id', '?')}' hat ungültiges severity: '{sev}'"


class TestConfidenceValidation:
    """Valide Confidence-Werte."""

    VALID_CONFIDENCES = frozenset({"high", "medium", "low"})

    def test_security_confidence(self, security_patterns):
        for entry in security_patterns:
            conf = entry.get("confidence", "")
            assert conf in self.VALID_CONFIDENCES, \
                f"Security pattern '{entry.get('id', '?')}' hat ungültiges confidence: '{conf}'"

    def test_quality_confidence(self, quality_patterns):
        for entry in quality_patterns:
            conf = entry.get("confidence", "")
            assert conf in self.VALID_CONFIDENCES, \
                f"Quality pattern '{entry.get('id', '?')}' hat ungültiges confidence: '{conf}'"


class TestLoaderIntegration:
    """Integration mit PatternLoader."""

    def test_loader_loads_all_semgrep_patterns(self):
        """PatternLoader kann alle Semgrep-Patterns laden."""
        from shared.pattern_loader import PatternLoader

        loader = PatternLoader.get_instance()
        loader.clear()
        patterns = loader.load_all()

        semgrep_patterns = [p for p in patterns if p.id.startswith("semgrep-")]
        assert len(semgrep_patterns) >= 100, \
            f"Zu wenige semgrep patterns geladen: {len(semgrep_patterns)}"

    def test_loader_categories(self):
        """Security und correctness patterns sind vorhanden."""
        from shared.pattern_loader import PatternLoader

        loader = PatternLoader.get_instance()
        loader.clear()
        patterns = loader.load_all()

        cats = {p.category for p in patterns if p.id.startswith("semgrep-")}
        assert "security" in cats, "Keine security patterns gefunden"
        assert "code-quality" in cats, "Keine code-quality patterns gefunden"

    def test_loader_filter_by_language(self):
        """Filtern nach Sprachen funktioniert."""
        from shared.pattern_loader import PatternLoader

        loader = PatternLoader.get_instance()
        loader.clear()

        py_patterns = loader.get_by_language("python")
        semgrep_py = [p for p in py_patterns if p.id.startswith("semgrep-")]
        assert len(semgrep_py) > 0, "Keine python semgrep patterns"

        js_patterns = loader.get_by_language("javascript")
        semgrep_js = [p for p in js_patterns if p.id.startswith("semgrep-")]
        assert len(semgrep_js) > 0, "Keine javascript semgrep patterns"
