"""Tests für manuell kuratierte Bug-Patterns (Top-100 Security + Medusa + Next.js + React).

Testet:
- Alle Pattern-IDs haben korrekte Prefixe (CWE-, MEDUSA-, NEXT-, REACT-)
- Alle Pflichtfelder sind vorhanden und nicht leer
- YAML-Dateien sind valide
- Pattern-IDs sind eindeutig
- CWE-Format: CWE-XXXX
- Medusa-Patterns nur language: typescript
- Severity/Confidence valid
- Alle haben fix_description
- Integration mit PatternLoader
"""

from __future__ import annotations

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
TOP100_YAML = PLUGIN_ROOT / "data" / "patterns" / "security" / "top100.yaml"
MEDUSA_YAML = PLUGIN_ROOT / "data" / "patterns" / "medusa" / "medusa.yaml"
NEXTJS_YAML = PLUGIN_ROOT / "data" / "patterns" / "nextjs" / "nextjs.yaml"
REACT_YAML = PLUGIN_ROOT / "data" / "patterns" / "nextjs" / "react.yaml"

# Erwartete Pattern-Zahlen
EXPECTED_COUNTS = {
    "CWE-": 90,   # Top-100: mindestens 90
    "MEDUSA": 20,
    "NEXT-": 15,
    "REACT-": 15,
}

# Erwartete Prefixe pro Datei
PREFIX_MAP = {
    "top100.yaml": "CWE-",
    "medusa.yaml": "MEDUSA-",
    "nextjs.yaml": "NEXT-",
    "react.yaml": "REACT-",
}

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def top100_data() -> list[dict]:
    """Lädt die Top-100 Security YAML-Datei."""
    with open(TOP100_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, list), "Top-100 YAML muss eine Liste sein"
    return data


@pytest.fixture(scope="session")
def medusa_data() -> list[dict]:
    """Lädt die Medusa v2 YAML-Datei."""
    with open(MEDUSA_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, list), "Medusa YAML muss eine Liste sein"
    return data


@pytest.fixture(scope="session")
def nextjs_data() -> list[dict]:
    """Lädt die Next.js YAML-Datei."""
    with open(NEXTJS_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, list), "Next.js YAML muss eine Liste sein"
    return data


@pytest.fixture(scope="session")
def react_data() -> list[dict]:
    """Lädt die React YAML-Datei."""
    with open(REACT_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, list), "React YAML muss eine Liste sein"
    return data


@pytest.fixture(scope="session")
def all_patterns(top100_data, medusa_data, nextjs_data, react_data) -> list[dict]:
    """Alle manuell kuratierten Patterns."""
    return top100_data + medusa_data + nextjs_data + react_data


# ---------------------------------------------------------------------------
# Struktur-Tests: YAML Validität
# ---------------------------------------------------------------------------


class TestYamlValidity:
    """Tests für die YAML-Struktur aller Pattern-Dateien."""

    @pytest.mark.parametrize("name, path", [
        ("top100.yaml", TOP100_YAML),
        ("medusa.yaml", MEDUSA_YAML),
        ("nextjs.yaml", NEXTJS_YAML),
        ("react.yaml", REACT_YAML),
    ])
    def test_yaml_files_exist(self, name: str, path: Path) -> None:
        """Alle YAML-Dateien existieren."""
        assert path.exists(), f"{name} existiert nicht unter {path}"

    @pytest.mark.parametrize("name, path", [
        ("top100.yaml", TOP100_YAML),
        ("medusa.yaml", MEDUSA_YAML),
        ("nextjs.yaml", NEXTJS_YAML),
        ("react.yaml", REACT_YAML),
    ])
    def test_yaml_files_valid(self, name: str, path: Path) -> None:
        """YAML-Dateien sind syntaktisch valide."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, list), f"{name}: muss eine Liste sein (yaml-Top-Level)"
        assert len(data) >= 1, f"{name}: mindestens 1 Pattern erwartet"

    @pytest.mark.parametrize("name, path, prefix", [
        ("top100.yaml", TOP100_YAML, "CWE-"),
        ("medusa.yaml", MEDUSA_YAML, "MEDUSA-"),
        ("nextjs.yaml", NEXTJS_YAML, "NEXT-"),
        ("react.yaml", REACT_YAML, "REACT-"),
    ])
    def test_id_prefix(self, name: str, path: Path, prefix: str) -> None:
        """Alle Pattern-IDs in einer Datei haben den korrekten Prefix."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        for pat in data:
            pid = pat.get("id", "")
            assert pid.startswith(prefix), (
                f"{name}: Pattern-ID '{pid}' beginnt nicht mit '{prefix}'"
            )


# ---------------------------------------------------------------------------
# Top-100 Security Tests
# ---------------------------------------------------------------------------


class TestTop100Security:
    """Tests für die Top-100 Security Patterns."""

    def test_count(self, top100_data) -> None:
        """Mindestens 90 Patterns (Ziel: ~100)."""
        assert len(top100_data) >= 90, (
            f"Top-100: erwarte >= 90 Patterns, habe {len(top100_data)}"
        )

    def test_all_ids_unique(self, top100_data) -> None:
        """Alle Pattern-IDs sind eindeutig."""
        ids = [pat.get("id", "") for pat in top100_data]
        dups = [id_ for id_ in ids if ids.count(id_) > 1]
        assert not dups, f"Doppelte Pattern-IDs: {set(dups)}"

    def test_all_have_required_fields(self, top100_data) -> None:
        """Jedes Pattern hat alle Pflichtfelder."""
        required = {"id", "cwe", "category", "severity", "languages",
                    "title", "scan_query", "fix_description", "confidence"}
        for pat in top100_data:
            missing = required - set(pat.keys())
            assert not missing, (
                f"Pattern '{pat.get('id', '?')}': fehlende Felder {missing}"
            )

    def test_all_fields_non_empty(self, top100_data) -> None:
        """Pflichtfelder sind nicht leer."""
        for pat in top100_data:
            pid = pat.get("id", "?")
            assert pat.get("title"), f"{pid}: title ist leer"
            assert pat.get("scan_query"), f"{pid}: scan_query ist leer"
            assert pat.get("fix_description"), f"{pid}: fix_description ist leer"
            assert pat.get("cwe"), f"{pid}: cwe ist leer"
            assert pat.get("category"), f"{pid}: category ist leer"
            assert pat.get("severity"), f"{pid}: severity ist leer"
            assert pat.get("confidence"), f"{pid}: confidence ist leer"
            assert pat.get("languages"), f"{pid}: languages ist leer"

    def test_severity_valid(self, top100_data) -> None:
        """Severity ist nur critical/high/medium/low/info."""
        for pat in top100_data:
            sev = pat.get("severity", "")
            assert sev in VALID_SEVERITIES, (
                f"Pattern '{pat.get('id', '?')}': severity '{sev}' ungueltig"
            )

    def test_confidence_valid(self, top100_data) -> None:
        """Confidence ist nur high/medium/low."""
        for pat in top100_data:
            conf = pat.get("confidence", "")
            assert conf in VALID_CONFIDENCES, (
                f"Pattern '{pat.get('id', '?')}': confidence '{conf}' ungueltig"
            )

    def test_cwe_format(self, top100_data) -> None:
        """CWE-ID hat Format CWE-XXXX."""
        for pat in top100_data:
            cwe = pat.get("cwe", "")
            assert cwe.startswith("CWE-"), (
                f"Pattern '{pat.get('id', '?')}': CWE '{cwe}' beginnt nicht mit CWE-"
            )
            parts = cwe.split("-")
            assert len(parts) == 2 and parts[1].isdigit(), (
                f"Pattern '{pat.get('id', '?')}': CWE '{cwe}' Format ungueltig"
            )

    def test_languages_is_list(self, top100_data) -> None:
        """Languages-Feld ist eine Liste."""
        for pat in top100_data:
            langs = pat.get("languages", [])
            assert isinstance(langs, list), (
                f"Pattern '{pat.get('id', '?')}': languages kein list"
            )
            assert len(langs) >= 1, (
                f"Pattern '{pat.get('id', '?')}': mindestens eine Sprache"
            )

    def test_category_is_security(self, top100_data) -> None:
        """Alle Top-100 Patterns haben category=security."""
        for pat in top100_data:
            assert pat.get("category") == "security", (
                f"Pattern '{pat.get('id', '?')}': category != security"
            )

    def test_critical_patterns_exist(self, top100_data) -> None:
        """Mindestens 15 critical Patterns."""
        critical = [p for p in top100_data if p.get("severity") == "critical"]
        assert len(critical) >= 15, (
            f"Nur {len(critical)} critical Patterns, erwarte >= 15"
        )


# ---------------------------------------------------------------------------
# Medusa v2 Tests
# ---------------------------------------------------------------------------


class TestMedusaPatterns:
    """Tests für die Medusa v2 Patterns."""

    def test_count(self, medusa_data) -> None:
        """20 Medusa-Patterns."""
        assert len(medusa_data) == 20, (
            f"Medusa: erwarte 20 Patterns, habe {len(medusa_data)}"
        )

    def test_all_ids_unique(self, medusa_data) -> None:
        """Alle Pattern-IDs sind eindeutig."""
        ids = [pat.get("id", "") for pat in medusa_data]
        dups = [id_ for id_ in ids if ids.count(id_) > 1]
        assert not dups, f"Doppelte Pattern-IDs: {set(dups)}"

    def test_all_have_required_fields(self, medusa_data) -> None:
        """Jedes Pattern hat alle Pflichtfelder."""
        required = {"id", "cwe", "category", "severity", "languages",
                    "title", "scan_query", "fix_description", "confidence"}
        for pat in medusa_data:
            missing = required - set(pat.keys())
            assert not missing, (
                f"Pattern '{pat.get('id', '?')}': fehlende Felder {missing}"
            )

    def test_language_typescript_only(self, medusa_data) -> None:
        """Alle Medusa-Patterns haben nur language: typescript."""
        for pat in medusa_data:
            pid = pat.get("id", "?")
            langs = pat.get("languages", [])
            assert langs == ["typescript"], (
                f"{pid}: language {langs}, erwarte ['typescript']"
            )

    def test_id_prefix_and_format(self, medusa_data) -> None:
        """Pattern-IDs folgen MEDUSA-{KAT}-{NR} Schema."""
        valid_categories = {"SVC", "WKF", "MOD", "ADM"}
        for pat in medusa_data:
            pid = pat.get("id", "")
            parts = pid.split("-")
            assert len(parts) == 3, (
                f"Medusa-ID '{pid}' hat nicht 3 Teile (MEDUSA-KATEGORIE-NR)"
            )
            assert parts[0] == "MEDUSA"
            assert parts[1] in valid_categories, (
                f"Medusa-ID '{pid}': unbekannte Kategorie '{parts[1]}'"
            )
            assert parts[2].isdigit(), (
                f"Medusa-ID '{pid}': Nummer '{parts[2]}' ist keine Zahl"
            )

    def test_severity_valid(self, medusa_data) -> None:
        """Severity ist nur critical/high/medium/low/info."""
        for pat in medusa_data:
            sev = pat.get("severity", "")
            assert sev in VALID_SEVERITIES, (
                f"Pattern '{pat.get('id', '?')}': severity '{sev}' ungueltig"
            )

    def test_fix_description_exists(self, medusa_data) -> None:
        """Jedes Medusa-Pattern hat eine fix_description."""
        for pat in medusa_data:
            pid = pat.get("id", "?")
            fd = pat.get("fix_description", "")
            assert fd, f"{pid}: fix_description fehlt oder ist leer"
            assert len(fd) >= 30, (
                f"{pid}: fix_description zu kurz ({len(fd)} Zeichen)"
            )


# ---------------------------------------------------------------------------
# Next.js Tests
# ---------------------------------------------------------------------------


class TestNextJsPatterns:
    """Tests für die Next.js Patterns."""

    def test_count(self, nextjs_data) -> None:
        """15 Next.js Patterns."""
        assert len(nextjs_data) == 15, (
            f"Next.js: erwarte 15 Patterns, habe {len(nextjs_data)}"
        )

    def test_all_ids_unique(self, nextjs_data) -> None:
        """Alle Pattern-IDs sind eindeutig."""
        ids = [pat.get("id", "") for pat in nextjs_data]
        dups = [id_ for id_ in ids if ids.count(id_) > 1]
        assert not dups, f"Doppelte Pattern-IDs: {set(dups)}"

    def test_all_have_required_fields(self, nextjs_data) -> None:
        """Jedes Pattern hat alle Pflichtfelder."""
        required = {"id", "cwe", "category", "severity", "languages",
                    "title", "scan_query", "fix_description", "confidence"}
        for pat in nextjs_data:
            missing = required - set(pat.keys())
            assert not missing, (
                f"Pattern '{pat.get('id', '?')}': fehlende Felder {missing}"
            )

    def test_id_prefix_and_format(self, nextjs_data) -> None:
        """Pattern-IDs folgen NEXT-{KAT}-{NR} Schema."""
        valid_categories = {"PR", "AR", "MW", "API"}
        for pat in nextjs_data:
            pid = pat.get("id", "")
            parts = pid.split("-")
            assert len(parts) == 3, (
                f"Next.js-ID '{pid}' hat nicht 3 Teile (NEXT-KATEGORIE-NR)"
            )
            assert parts[0] == "NEXT"
            assert parts[1] in valid_categories, (
                f"Next.js-ID '{pid}': unbekannte Kategorie '{parts[1]}'"
            )
            assert parts[2].isdigit(), (
                f"Next.js-ID '{pid}': Nummer '{parts[2]}' ist keine Zahl"
            )

    def test_fix_description_exists(self, nextjs_data) -> None:
        """Jedes Next.js-Pattern hat eine fix_description."""
        for pat in nextjs_data:
            pid = pat.get("id", "?")
            fd = pat.get("fix_description", "")
            assert fd, f"{pid}: fix_description fehlt oder ist leer"
            assert len(fd) >= 30, (
                f"{pid}: fix_description zu kurz ({len(fd)} Zeichen)"
            )

    def test_severity_valid(self, nextjs_data) -> None:
        """Severity ist nur critical/high/medium/low/info."""
        for pat in nextjs_data:
            sev = pat.get("severity", "")
            assert sev in VALID_SEVERITIES, (
                f"Pattern '{pat.get('id', '?')}': severity '{sev}' ungueltig"
            )


# ---------------------------------------------------------------------------
# React Tests
# ---------------------------------------------------------------------------


class TestReactPatterns:
    """Tests für die React Patterns."""

    def test_count(self, react_data) -> None:
        """15 React Patterns."""
        assert len(react_data) == 15, (
            f"React: erwarte 15 Patterns, habe {len(react_data)}"
        )

    def test_all_ids_unique(self, react_data) -> None:
        """Alle Pattern-IDs sind eindeutig."""
        ids = [pat.get("id", "") for pat in react_data]
        dups = [id_ for id_ in ids if ids.count(id_) > 1]
        assert not dups, f"Doppelte Pattern-IDs: {set(dups)}"

    def test_all_have_required_fields(self, react_data) -> None:
        """Jedes Pattern hat alle Pflichtfelder."""
        required = {"id", "cwe", "category", "severity", "languages",
                    "title", "scan_query", "fix_description", "confidence"}
        for pat in react_data:
            missing = required - set(pat.keys())
            assert not missing, (
                f"Pattern '{pat.get('id', '?')}': fehlende Felder {missing}"
            )

    def test_id_prefix_and_format(self, react_data) -> None:
        """Pattern-IDs folgen REACT-{KAT}-{NR} Schema."""
        valid_categories = {"HU", "ST", "EF", "KY"}
        for pat in react_data:
            pid = pat.get("id", "")
            parts = pid.split("-")
            assert len(parts) == 3, (
                f"React-ID '{pid}' hat nicht 3 Teile (REACT-KATEGORIE-NR)"
            )
            assert parts[0] == "REACT", (
                f"React-ID '{pid}': Prefix ist nicht REACT"
            )
            assert parts[1] in valid_categories, (
                f"React-ID '{pid}': unbekannte Kategorie '{parts[1]}'"
            )
            assert parts[2].isdigit(), (
                f"React-ID '{pid}': Nummer '{parts[2]}' ist keine Zahl"
            )

    def test_fix_description_exists(self, react_data) -> None:
        """Jedes React-Pattern hat eine fix_description."""
        for pat in react_data:
            pid = pat.get("id", "?")
            fd = pat.get("fix_description", "")
            assert fd, f"{pid}: fix_description fehlt oder ist leer"
            assert len(fd) >= 30, (
                f"{pid}: fix_description zu kurz ({len(fd)} Zeichen)"
            )

    def test_severity_valid(self, react_data) -> None:
        """Severity ist nur critical/high/medium/low/info."""
        for pat in react_data:
            sev = pat.get("severity", "")
            assert sev in VALID_SEVERITIES, (
                f"Pattern '{pat.get('id', '?')}': severity '{sev}' ungueltig"
            )


# ---------------------------------------------------------------------------
# Übergreifende Tests
# ---------------------------------------------------------------------------


class TestGlobalPatternValidity:
    """Übergreifende Tests für alle manuell kuratierten Patterns."""

    def test_all_ids_unique_globally(self, all_patterns) -> None:
        """Keine doppelten IDs über alle Dateien hinweg."""
        ids = [pat.get("id", "") for pat in all_patterns]
        dups = [id_ for id_ in ids if ids.count(id_) > 1]
        assert not dups, (
            f"Doppelte Pattern-IDs global: {set(dups)}"
        )

    def test_all_have_fix_description(self, all_patterns) -> None:
        """Jedes Pattern hat eine nicht-leere fix_description."""
        for pat in all_patterns:
            pid = pat.get("id", "?")
            fd = pat.get("fix_description", "")
            assert fd, f"{pid}: fix_description fehlt"
            # Mindestens ein Satz (20+ Zeichen)
            assert len(fd) >= 20, (
                f"{pid}: fix_description zu kurz: '{fd}'"
            )

    def test_all_have_scan_query(self, all_patterns) -> None:
        """Jedes Pattern hat eine nicht-leere scan_query."""
        for pat in all_patterns:
            pid = pat.get("id", "?")
            sq = pat.get("scan_query", "")
            assert sq, f"{pid}: scan_query fehlt"
            assert len(sq) >= 10, (
                f"{pid}: scan_query zu kurz: '{sq}'"
            )

    def test_all_cwe_valid(self, all_patterns) -> None:
        """Jedes Pattern hat ein valides CWE-XXXX Format."""
        for pat in all_patterns:
            cwe = pat.get("cwe", "")
            assert cwe.startswith("CWE-"), (
                f"Pattern '{pat.get('id', '?')}': CWE '{cwe}' invalid"
            )
            parts = cwe.split("-")
            assert len(parts) == 2 and parts[1].isdigit(), (
                f"Pattern '{pat.get('id', '?')}': CWE '{cwe}' format invalid"
            )

    def test_languages_valid(self, all_patterns) -> None:
        """Languages ist immer eine nicht-leere Liste."""
        for pat in all_patterns:
            langs = pat.get("languages", [])
            assert isinstance(langs, list), (
                f"Pattern '{pat.get('id', '?')}': languages kein list"
            )
            assert len(langs) >= 1, (
                f"Pattern '{pat.get('id', '?')}': leere languages"
            )

    def test_total_pattern_count(self, all_patterns) -> None:
        """Insgesamt mindestens 150 Patterns."""
        assert len(all_patterns) >= 150, (
            f"Nur {len(all_patterns)} Patterns, erwarte >= 150"
        )


# ---------------------------------------------------------------------------
# Integration Tests: PatternLoader
# ---------------------------------------------------------------------------


class TestPatternLoaderIntegration:
    """Tests für das Laden der neuen Patterns durch den PatternLoader."""

    @pytest.fixture(autouse=True)
    def setup(self):
        PatternLoader.reset_singleton()

    def test_loader_loads_all_patterns_from_data_dir(self):
        """PatternLoader lädt alle Patterns aus data/patterns/."""
        loader = PatternLoader(
            patterns_dir=str(PLUGIN_ROOT / "data" / "patterns")
        )
        all_pats = loader.load_all()
        assert len(all_pats) >= 150, (
            f"PatternLoader laedt nur {len(all_pats)} Patterns"
        )

    def test_loader_loads_cwe_patterns(self):
        """CWE-79-01 etc. sind geladen."""
        loader = PatternLoader(
            patterns_dir=str(PLUGIN_ROOT / "data" / "patterns")
        )
        all_pats = loader.load_all()
        cwe_ids = [p.id for p in all_pats if p.id.startswith("CWE-")]
        assert len(cwe_ids) >= 90, (
            f"Nur {len(cwe_ids)} CWE-Patterns geladen, erwarte >= 90"
        )

    def test_loader_loads_medusa_patterns(self):
        """MEDUSA-IDs sind geladen."""
        loader = PatternLoader(
            patterns_dir=str(PLUGIN_ROOT / "data" / "patterns")
        )
        all_pats = loader.load_all()
        medusa_ids = [p.id for p in all_pats if p.id.startswith("MEDUSA-")]
        assert len(medusa_ids) == 20, (
            f"Nur {len(medusa_ids)} Medusa-Patterns geladen, erwarte 20"
        )

    def test_loader_loads_nextjs_patterns(self):
        """NEXT-IDs sind geladen."""
        loader = PatternLoader(
            patterns_dir=str(PLUGIN_ROOT / "data" / "patterns")
        )
        all_pats = loader.load_all()
        next_ids = [p.id for p in all_pats if p.id.startswith("NEXT-")]
        assert len(next_ids) == 15, (
            f"Nur {len(next_ids)} Next.js-Patterns geladen, erwarte 15"
        )

    def test_loader_loads_react_patterns(self):
        """REACT-IDs sind geladen."""
        loader = PatternLoader(
            patterns_dir=str(PLUGIN_ROOT / "data" / "patterns")
        )
        all_pats = loader.load_all()
        react_ids = [p.id for p in all_pats if p.id.startswith("REACT-")]
        assert len(react_ids) == 15, (
            f"Nur {len(react_ids)} React-Patterns geladen, erwarte 15"
        )

    def test_loader_returns_valid_bugpatterns(self):
        """Alle geladenen Patterns sind valide BugPattern-Objekte."""
        loader = PatternLoader(
            patterns_dir=str(PLUGIN_ROOT / "data" / "patterns")
        )
        all_pats = loader.load_all()
        for pat in all_pats:
            if pat.id.startswith(("CWE-", "MEDUSA-", "NEXT-", "REACT-")):
                assert isinstance(pat, BugPattern)
                assert pat.id
                assert pat.fix_description

    def test_filter_by_severity_critical(self):
        """Filter für critical Severity funktioniert."""
        loader = PatternLoader(
            patterns_dir=str(PLUGIN_ROOT / "data" / "patterns")
        )
        critical = loader.filter(severities=["critical"])
        new_critical = [
            p for p in critical
            if p.id.startswith(("CWE-", "MEDUSA-", "NEXT-", "REACT-"))
        ]
        assert len(new_critical) >= 15, (
            f"Erwarte >= 15 critical Patterns, habe {len(new_critical)}"
        )

    def test_loader_get_by_id(self):
        """Einzelne Patterns sind per ID abfragbar."""
        loader = PatternLoader(
            patterns_dir=str(PLUGIN_ROOT / "data" / "patterns")
        )
        for pid in [
            "CWE-79-01", "CWE-89-01", "CWE-22-01",
            "MEDUSA-SVC-01", "MEDUSA-WKF-01",
            "NEXT-PR-01", "NEXT-AR-01",
            "REACT-HU-01", "REACT-EF-01",
        ]:
            pat = loader.get_by_id(pid)
            assert pat is not None, f"Pattern {pid} nicht geladen"
            assert pat.id == pid

    def test_loader_no_duplicates(self):
        """Keine doppelten IDs im PatternLoader."""
        loader = PatternLoader(
            patterns_dir=str(PLUGIN_ROOT / "data" / "patterns")
        )
        all_pats = loader.load_all()
        ids = [p.id for p in all_pats]
        dups = [id_ for id_ in ids if ids.count(id_) > 1]
        assert not dups, (
            f"Doppelte Pattern-IDs: {set(dups)}"
        )
