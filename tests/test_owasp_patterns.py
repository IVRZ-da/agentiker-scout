"""Tests für OWASP Secure Coding Patterns + CWE Taxonomie.

Testet:
- Alle 86 Patterns haben valide OWASP-IDs
- Pro Kategorie mindestens die erforderliche Anzahl Patterns
- Alle CWE-IDs existieren im CWE-Katalog
- Alle Pflichtfelder sind vorhanden
- Severity nur critical/high/medium/low/info
- Confidence nur high/medium/low
- Pattern-IDs sind eindeutig
- YAML-Datei ist valide
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from shared.pattern_loader import (
    VALID_CONFIDENCES,
    VALID_SEVERITIES,
    BugPattern,
    PatternLoader,
)

# ---------------------------------------------------------------------------
# Pfade
# ---------------------------------------------------------------------------

PLUGIN_ROOT = Path(__file__).parent.parent
OWASP_YAML = PLUGIN_ROOT / "data" / "patterns" / "security" / "owasp.yaml"
CWE_JSON = PLUGIN_ROOT / "data" / "cwe_categories.json"

# OWASP Kategorie-Präfixe
OWASP_CATEGORIES = {
    "OWASP-IV": "Input Validation",
    "OWASP-AU": "Authentication",
    "OWASP-SM": "Session Management",
    "OWASP-AC": "Access Control",
    "OWASP-CR": "Cryptography",
    "OWASP-EH": "Error Handling / Logging",
    "OWASP-FS": "File / Data Security",
}

# Mindestanzahl Patterns pro Kategorie
MIN_PATTERNS_PER_CATEGORY = {
    "OWASP-IV": 10,
    "OWASP-AU": 10,
    "OWASP-SM": 8,
    "OWASP-AC": 10,
    "OWASP-CR": 10,
    "OWASP-EH": 10,
    "OWASP-FS": 10,
}

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def owasp_data() -> list[dict]:
    """Lädt die OWASP YAML-Datei."""
    with open(OWASP_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, list), "OWASP YAML muss eine Liste sein"
    return data


@pytest.fixture(scope="session")
def cwe_catalog() -> dict:
    """Lädt das CWE-Katalog-JSON."""
    with open(CWE_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict), "CWE JSON muss ein Dict sein"
    return data


@pytest.fixture(scope="session")
def pattern_ids_by_category(owasp_data) -> dict[str, list[str]]:
    """Gruppiert Pattern-IDs nach OWASP-Kategorie."""
    categories: dict[str, list[str]] = {}
    for pat in owasp_data:
        pid: str = pat.get("id", "")
        prefix = "-".join(pid.split("-")[:2])  # z.B. OWASP-IV
        categories.setdefault(prefix, []).append(pid)
    return categories


# ---------------------------------------------------------------------------
# Struktur-Tests: YAML
# ---------------------------------------------------------------------------


class TestOwaspYamlStructure:
    """Tests für die OWASP YAML-Struktur."""

    def test_yaml_is_valid(self, owasp_data):
        """YAML-Datei ist valide und enthält Patterns."""
        assert len(owasp_data) >= 86, (
            f"Erwarte mindestens 86 Patterns, habe {len(owasp_data)}"
        )

    def test_total_patterns(self, owasp_data):
        """Es gibt genau 86 OWASP Patterns."""
        assert len(owasp_data) == 86, (
            f"Erwarte 86 Patterns, habe {len(owasp_data)}"
        )

    def test_all_have_valid_owasp_prefix(self, owasp_data):
        """Jedes Pattern hat eine ID mit OWASP-Prefix."""
        for pat in owasp_data:
            pid = pat.get("id", "")
            assert pid.startswith("OWASP-"), (
                f"Pattern-ID '{pid}' beginnt nicht mit OWASP-"
            )

    def test_all_ids_unique(self, owasp_data):
        """Alle Pattern-IDs sind eindeutig."""
        ids = [pat.get("id", "") for pat in owasp_data]
        dups = [id_ for id_ in ids if ids.count(id_) > 1]
        assert not dups, f"Doppelte Pattern-IDs gefunden: {set(dups)}"

    def test_all_have_required_fields(self, owasp_data):
        """Jedes Pattern hat alle Pflichtfelder."""
        required = {"id", "cwe", "category", "severity", "languages",
                    "title", "scan_query", "fix_description", "confidence"}
        for pat in owasp_data:
            missing = required - set(pat.keys())
            assert not missing, (
                f"Pattern '{pat.get('id', '?')}': fehlende Felder {missing}"
            )

    def test_all_fields_non_empty(self, owasp_data):
        """Pflichtfelder sind nicht leer."""
        for pat in owasp_data:
            pid = pat.get("id", "?")
            assert pat.get("title"), f"{pid}: title ist leer"
            assert pat.get("scan_query"), f"{pid}: scan_query ist leer"
            assert pat.get("fix_description"), f"{pid}: fix_description ist leer"
            assert pat.get("cwe"), f"{pid}: cwe ist leer"
            assert pat.get("category"), f"{pid}: category ist leer"
            assert pat.get("severity"), f"{pid}: severity ist leer"
            assert pat.get("confidence"), f"{pid}: confidence ist leer"
            assert pat.get("languages"), f"{pid}: languages ist leer"

    def test_severity_valid(self, owasp_data):
        """Severity ist nur critical/high/medium/low/info."""
        for pat in owasp_data:
            sev = pat.get("severity", "")
            assert sev in VALID_SEVERITIES, (
                f"Pattern '{pat.get('id', '?')}': "
                f"severity '{sev}' ungültig"
            )

    def test_confidence_valid(self, owasp_data):
        """Confidence ist nur high/medium/low."""
        for pat in owasp_data:
            conf = pat.get("confidence", "")
            assert conf in VALID_CONFIDENCES, (
                f"Pattern '{pat.get('id', '?')}': "
                f"confidence '{conf}' ungültig"
            )

    def test_cwe_format(self, owasp_data):
        """CWE-ID hat Format CWE-XXXX."""
        for pat in owasp_data:
            cwe = pat.get("cwe", "")
            assert cwe.startswith("CWE-"), (
                f"Pattern '{pat.get('id', '?')}': "
                f"CWE '{cwe}' beginnt nicht mit CWE-"
            )
            parts = cwe.split("-")
            assert len(parts) == 2 and parts[1].isdigit(), (
                f"Pattern '{pat.get('id', '?')}': "
                f"CWE '{cwe}' Format ungültig"
            )

    def test_languages_is_list(self, owasp_data):
        """Languages-Feld ist eine Liste."""
        for pat in owasp_data:
            langs = pat.get("languages", [])
            assert isinstance(langs, list), (
                f"Pattern '{pat.get('id', '?')}': "
                f"languages ist kein list, sondern {type(langs).__name__}"
            )
            assert len(langs) >= 1, (
                f"Pattern '{pat.get('id', '?')}': "
                f"mindestens eine Sprache erforderlich"
            )

    def test_category_is_security(self, owasp_data):
        """Alle OWASP-Patterns haben category=security."""
        for pat in owasp_data:
            assert pat.get("category") == "security", (
                f"Pattern '{pat.get('id', '?')}': "
                f"category '{pat.get('category')}' != 'security'"
            )


# ---------------------------------------------------------------------------
# Kategorie-Tests
# ---------------------------------------------------------------------------


class TestOwaspCategories:
    """Tests für die OWASP-Kategorien."""

    def test_all_categories_present(self, pattern_ids_by_category):
        """Alle 7 OWASP-Kategorien sind vorhanden."""
        for prefix in OWASP_CATEGORIES:
            assert prefix in pattern_ids_by_category, (
                f"Kategorie {prefix} ({OWASP_CATEGORIES[prefix]}) fehlt"
            )

    def test_min_patterns_per_category(self, pattern_ids_by_category):
        """Jede Kategorie hat mindestens die erforderliche Mindestanzahl."""
        for prefix, min_count in MIN_PATTERNS_PER_CATEGORY.items():
            count = len(pattern_ids_by_category.get(prefix, []))
            assert count >= min_count, (
                f"Kategorie {prefix} ({OWASP_CATEGORIES[prefix]}): "
                f"erwarte mindestens {min_count} Patterns, habe {count}"
            )

    def test_category_id_format(self, pattern_ids_by_category):
        """Alle Pattern-IDs folgen dem Schema OWASP-{KAT}-{NR}."""
        valid_prefixes = set(OWASP_CATEGORIES.keys())
        for prefix, ids in pattern_ids_by_category.items():
            assert prefix in valid_prefixes, (
                f"Unbekanntes Kategorie-Präfix: {prefix}"
            )
            for pid in ids:
                parts = pid.split("-")
                assert len(parts) == 3, (
                    f"Pattern-ID '{pid}' hat nicht das Format OWASP-{prefix}-NR"
                )
                assert parts[2].isdigit(), (
                    f"Pattern-ID '{pid}': Nummer '{parts[2]}' ist keine Zahl"
                )

    def test_category_counts_sum_to_86(self, pattern_ids_by_category):
        """Die Summe aller Patterns ist 86."""
        total = sum(len(ids) for ids in pattern_ids_by_category.values())
        assert total == 86, (
            f"Pattern-Summe ist {total}, erwarte 86"
        )

    def test_owasp_iv_category(self, pattern_ids_by_category):
        """Input Validation Kategorie hat 13 Patterns."""
        assert len(pattern_ids_by_category["OWASP-IV"]) == 13

    def test_owasp_au_category(self, pattern_ids_by_category):
        """Authentication Kategorie hat 13 Patterns."""
        assert len(pattern_ids_by_category["OWASP-AU"]) == 13

    def test_owasp_sm_category(self, pattern_ids_by_category):
        """Session Management Kategorie hat 11 Patterns."""
        assert len(pattern_ids_by_category["OWASP-SM"]) == 11

    def test_owasp_ac_category(self, pattern_ids_by_category):
        """Access Control Kategorie hat 13 Patterns."""
        assert len(pattern_ids_by_category["OWASP-AC"]) == 13

    def test_owasp_cr_category(self, pattern_ids_by_category):
        """Cryptography Kategorie hat 13 Patterns."""
        assert len(pattern_ids_by_category["OWASP-CR"]) == 13

    def test_owasp_eh_category(self, pattern_ids_by_category):
        """Error Handling Kategorie hat 11 Patterns."""
        assert len(pattern_ids_by_category["OWASP-EH"]) == 11

    def test_owasp_fs_category(self, pattern_ids_by_category):
        """File/Data Security Kategorie hat 12 Patterns."""
        assert len(pattern_ids_by_category["OWASP-FS"]) == 12


# ---------------------------------------------------------------------------
# CWE Taxonomie Tests
# ---------------------------------------------------------------------------


class TestCweCatalog:
    """Tests für den CWE-Katalog."""

    def test_cwe_catalog_exists(self, cwe_catalog):
        """CWE-Katalog existiert und ist nicht leer."""
        assert len(cwe_catalog) >= 50, (
            f"Erwarte mindestens 50 CWE-Einträge, habe {len(cwe_catalog)}"
        )

    def test_cwe_entries_have_required_fields(self, cwe_catalog):
        """Jeder CWE-Eintrag hat alle Pflichtfelder."""
        required = {"name", "description", "detection_methods",
                    "severity", "languages"}
        for cwe_id, entry in cwe_catalog.items():
            missing = required - set(entry.keys())
            assert not missing, (
                f"{cwe_id}: fehlende Felder {missing}"
            )

    def test_cwe_severity_valid(self, cwe_catalog):
        """CWE-Severity ist nur critical/high/medium/low."""
        valid = {"critical", "high", "medium", "low"}
        for cwe_id, entry in cwe_catalog.items():
            sev = entry.get("severity", "")
            assert sev in valid, (
                f"{cwe_id}: severity '{sev}' ungültig"
            )

    def test_cwe_detection_methods_valid(self, cwe_catalog):
        """Detection-Methods sind valide."""
        valid = {"static", "dynamic", "manual"}
        for cwe_id, entry in cwe_catalog.items():
            methods = entry.get("detection_methods", [])
            assert isinstance(methods, list), (
                f"{cwe_id}: detection_methods ist kein list"
            )
            for m in methods:
                assert m in valid, (
                    f"{cwe_id}: detection_method '{m}' ungültig"
                )

    def test_cwe_languages_valid(self, cwe_catalog):
        """Languages enthält 'all' oder bekannte Sprachen."""
        for cwe_id, entry in cwe_catalog.items():
            langs = entry.get("languages", [])
            assert isinstance(langs, list), (
                f"{cwe_id}: languages ist kein list"
            )
            assert len(langs) >= 1, (
                f"{cwe_id}: mindestens eine Sprache erforderlich"
            )

    def test_all_owasp_cwes_in_catalog(self, owasp_data, cwe_catalog):
        """Alle in OWASP-Patterns verwendeten CWE-IDs sind im Katalog."""
        used_cwes = {pat.get("cwe", "") for pat in owasp_data}
        missing = used_cwes - set(cwe_catalog.keys())
        assert not missing, (
            f"CWE-IDs nicht im Katalog: {missing}"
        )

    def test_cwe_catalog_covers_top_owasp(self, cwe_catalog):
        """Wichtige OWASP-relevante CWEs sind im Katalog."""
        important_cwes = {
            "CWE-20", "CWE-22", "CWE-79", "CWE-89", "CWE-94",
            "CWE-200", "CWE-287", "CWE-321", "CWE-327", "CWE-434",
            "CWE-502", "CWE-601", "CWE-611", "CWE-639", "CWE-798",
            "CWE-862", "CWE-863", "CWE-1004", "CWE-1321",
        }
        missing = important_cwes - set(cwe_catalog.keys())
        assert not missing, (
            f"Wichtige CWE-IDs fehlen im Katalog: {missing}"
        )


# ---------------------------------------------------------------------------
# Integration Tests: PatternLoader
# ---------------------------------------------------------------------------


class TestOwaspPatternLoader:
    """Tests für das Laden der OWASP-Patterns durch den PatternLoader."""

    @pytest.fixture(autouse=True)
    def setup(self):
        PatternLoader.reset_singleton()

    def test_loader_loads_all_owasp_patterns(self):
        """PatternLoader lädt alle 86 OWASP-Patterns."""
        loader = PatternLoader(
            patterns_dir=str(PLUGIN_ROOT / "data" / "patterns")
        )
        all_pats = loader.load_all()
        owasp_pats = [p for p in all_pats if p.id.startswith("OWASP-")]
        assert len(owasp_pats) == 86, (
            f"PatternLoader lädt {len(owasp_pats)} OWASP-Patterns, erwarte 86"
        )

    def test_loader_returns_valid_bugpatterns(self):
        """Alle geladenen OWASP-Patterns sind valide BugPattern-Objekte."""
        loader = PatternLoader(
            patterns_dir=str(PLUGIN_ROOT / "data" / "patterns")
        )
        all_pats = loader.load_all()
        for pat in all_pats:
            if pat.id.startswith("OWASP-"):
                assert isinstance(pat, BugPattern)
                assert pat.id.startswith("OWASP-")

    def test_get_by_category_security(self):
        """get_by_category('security') enthält alle OWASP-Patterns."""
        loader = PatternLoader(
            patterns_dir=str(PLUGIN_ROOT / "data" / "patterns")
        )
        security_pats = loader.get_by_category("security")
        owasp_pats = [p for p in security_pats if p.id.startswith("OWASP-")]
        assert len(owasp_pats) == 86, (
            f"Security-Kategorie hat {len(owasp_pats)} OWASP-Patterns"
        )

    def test_get_by_language(self):
        """Patterns sind nach Sprache abfragbar."""
        loader = PatternLoader(
            patterns_dir=str(PLUGIN_ROOT / "data" / "patterns")
        )
        all_pats = loader.get_by_language("python")
        python_owasp = [p for p in all_pats if p.id.startswith("OWASP-")]
        assert len(python_owasp) >= 80, (
            f"Erwarte >= 80 Python-kompatible OWASP-Patterns, "
            f"habe {len(python_owasp)}"
        )

    def test_get_by_id(self):
        """Einzelne OWASP-Patterns sind per ID abfragbar."""
        loader = PatternLoader(
            patterns_dir=str(PLUGIN_ROOT / "data" / "patterns")
        )
        for pid in ["OWASP-IV-01", "OWASP-AU-01", "OWASP-SM-01",
                     "OWASP-AC-01", "OWASP-CR-01", "OWASP-EH-01",
                     "OWASP-FS-01"]:
            pat = loader.get_by_id(pid)
            assert pat is not None, f"Pattern {pid} nicht geladen"
            assert pat.id == pid

    def test_filter_by_severity_critical(self):
        """Filter für critical Severity funktioniert."""
        loader = PatternLoader(
            patterns_dir=str(PLUGIN_ROOT / "data" / "patterns")
        )
        critical = loader.filter(severities=["critical"])
        owasp_critical = [p for p in critical if p.id.startswith("OWASP-")]
        assert len(owasp_critical) >= 10, (
            f"Erwarte >= 10 critical OWASP-Patterns, habe {len(owasp_critical)}"
        )

    def test_all_ids_loaded_without_duplicates(self):
        """Keine doppelten IDs im gesamten PatternLoader."""
        loader = PatternLoader(
            patterns_dir=str(PLUGIN_ROOT / "data" / "patterns")
        )
        all_pats = loader.load_all()
        ids = [p.id for p in all_pats]
        dups = [id_ for id_ in ids if ids.count(id_) > 1]
        assert not dups, (
            f"Doppelte Pattern-IDs im PatternLoader: {set(dups)}"
        )


# ---------------------------------------------------------------------------
# Daten-Integrität
# ---------------------------------------------------------------------------


class TestOwaspDataIntegrity:
    """Tests für die Datenintegrität der OWASP-Patterns."""

    def test_all_ids_have_correct_prefix(self, owasp_data):
        """Jede Pattern-ID hat das Schema OWASP-{KATEGORIE}-{NR}."""
        for pat in owasp_data:
            pid = pat.get("id", "")
            parts = pid.split("-")
            assert len(parts) == 3, (
                f"Pattern-ID '{pid}' hat nicht 3 Teile (OWASP-KATEGORIE-NR)"
            )
            assert parts[0] == "OWASP", (
                f"Pattern-ID '{pid}': Prefix ist nicht OWASP"
            )
            assert parts[1] in {
                "IV", "AU", "SM", "AC", "CR", "EH", "FS"
            }, f"Pattern-ID '{pid}': unbekannte Kategorie '{parts[1]}'"
            assert parts[2].isdigit(), (
                f"Pattern-ID '{pid}': Nummer '{parts[2]}' ist keine Zahl"
            )

    def test_sequential_numbering(self, pattern_ids_by_category):
        """Pattern-Nummern jeder Kategorie sind fortlaufend (beginnend bei 01)."""
        for prefix, ids in pattern_ids_by_category.items():
            numbers = sorted(
                int(pid.split("-")[2]) for pid in ids
            )
            expected = list(range(1, len(numbers) + 1))
            assert numbers == expected, (
                f"Kategorie {prefix}: "
                f"Nummern {numbers} sind nicht fortlaufend {expected}"
            )

    def test_no_missing_patterns(self, pattern_ids_by_category):
        """Es gibt keine Lücken in den Pattern-Nummern."""
        for prefix, ids in pattern_ids_by_category.items():
            numbers = sorted(
                int(pid.split("-")[2]) for pid in ids
            )
            for i, num in enumerate(numbers, 1):
                assert num == i, (
                    f"Kategorie {prefix}: fehlt Pattern-Nummer {i} "
                    f"(hat Nummern {numbers})"
                )

    def test_all_cwes_exist(self, owasp_data):
        """CWE-Felder sind nicht 'CWE-000' oder 'CWE-0'."""
        for pat in owasp_data:
            cwe = pat.get("cwe", "")
            assert cwe not in ("CWE-000", "CWE-0", ""), (
                f"Pattern '{pat.get('id', '?')}': "
                f"ungültige CWE '{cwe}'"
            )

    def test_scan_query_not_empty(self, owasp_data):
        """scan_query ist nicht nur Whitespace."""
        for pat in owasp_data:
            query = pat.get("scan_query", "")
            assert query.strip(), (
                f"Pattern '{pat.get('id', '?')}': "
                f"scan_query ist leer"
            )

    def test_fix_description_not_empty(self, owasp_data):
        """fix_description ist nicht nur Whitespace."""
        for pat in owasp_data:
            fix = pat.get("fix_description", "")
            assert fix.strip(), (
                f"Pattern '{pat.get('id', '?')}': "
                f"fix_description ist leer"
            )

    def test_title_not_empty(self, owasp_data):
        """title ist nicht nur Whitespace."""
        for pat in owasp_data:
            title = pat.get("title", "")
            assert title.strip(), (
                f"Pattern '{pat.get('id', '?')}': title ist leer"
            )

    def test_all_languages_known(self, owasp_data):
        """Nur bekannte Sprachen in den Patterns."""
        from shared.pattern_loader import KNOWN_LANGUAGES
        for pat in owasp_data:
            for lang in pat.get("languages", []):
                assert lang in KNOWN_LANGUAGES, (
                    f"Pattern '{pat.get('id', '?')}': "
                    f"unbekannte Sprache '{lang}'"
                )
