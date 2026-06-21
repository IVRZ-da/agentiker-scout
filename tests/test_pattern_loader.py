"""Tests für den Bug-Pattern Loader (pattern_loader.py).

Testet:
- BugPattern-Dataclass (Validierung, Pflichtfelder)
- YAML-Parsing (gültig/kaputt/leer/gemischte Formate)
- Duplikat-Erkennung
- Indizes (by_id, by_category, by_language)
- Filter-Funktion (Kategorie, Sprache, Severity, Confidence)
- Singleton-Verhalten (get_instance)
- Leeres Verzeichnis
- Fehlertoleranz (eine kaputte Datei reisst andere nicht mit)
- Performance (500+ Patterns in <100ms)
- CWE-Validierung
- Severity/Confidence Validierung
- Unbekannte Sprache (warnen, nicht ablehnen)
- Integration BugPattern ↔ Loader
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
import yaml

from shared.pattern_loader import (
    KNOWN_LANGUAGES,
    VALID_CONFIDENCES,
    VALID_SEVERITIES,
    BugPattern,
    PatternLoader,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def patterns_dir(tmp_path: Path) -> str:
    """Erzeugt ein temporäres patterns-Verzeichnis."""
    d = tmp_path / "patterns"
    d.mkdir()
    return str(d)


@pytest.fixture
def loader() -> PatternLoader:
    """Frischer PatternLoader ohne Singleton-Cache.

    Wichtig: reset_singleton() in setup, damit Tests sich nicht
    gegenseitig durch den Singleton beeinflussen.
    """
    PatternLoader.reset_singleton()
    return PatternLoader()


# ---------------------------------------------------------------------------
# BugPattern Dataclass
# ---------------------------------------------------------------------------


class TestBugPattern:
    """Tests für die BugPattern-Dataclass."""

    def test_valid_pattern(self) -> None:
        """Ein vollständig gültiges BugPattern."""
        pat = BugPattern(
            id="OWASP-01",
            cwe="CWE-20",
            category="security",
            severity="critical",
            languages=["python", "typescript"],
            title="Fehlende Input-Validierung",
            scan_query="express\\.(post|put|patch)\\(.*req\\.body",
            fix_description="Mit Zod/Yup validieren",
            confidence="high",
        )
        assert pat.id == "OWASP-01"
        assert pat.cwe == "CWE-20"
        assert pat.category == "security"
        assert pat.severity == "critical"
        assert pat.languages == ["python", "typescript"]
        assert pat.title == "Fehlende Input-Validierung"
        assert "req\\.body" in pat.scan_query
        assert pat.fix_description == "Mit Zod/Yup validieren"
        assert pat.confidence == "high"

    def test_minimal_valid_pattern(self) -> None:
        """BugPattern mit minimalen Pflichtfeldern."""
        pat = BugPattern(
            id="MIN-01",
            cwe="CWE-0",
            category="default",
            severity="info",
            languages=["python"],
            title="",
            scan_query="test()",
            fix_description="",
            confidence="low",
        )
        assert pat.id == "MIN-01"
        assert pat.severity == "info"
        assert pat.confidence == "low"

    @pytest.mark.parametrize("severity", ["critical", "high", "medium", "low", "info"])
    def test_all_valid_severities(self, severity: str) -> None:
        """Alle erlaubten Severity-Werte."""
        pat = BugPattern(
            id=f"SEV-{severity}",
            cwe="CWE-1",
            category="test",
            severity=severity,
            languages=["python"],
            title="test",
            scan_query="x",
            fix_description="",
            confidence="medium",
        )
        assert pat.severity == severity

    @pytest.mark.parametrize("confidence", ["high", "medium", "low"])
    def test_all_valid_confidences(self, confidence: str) -> None:
        """Alle erlaubten Confidence-Werte."""
        pat = BugPattern(
            id=f"CONF-{confidence}",
            cwe="CWE-1",
            category="test",
            severity="medium",
            languages=["python"],
            title="test",
            scan_query="x",
            fix_description="",
            confidence=confidence,
        )
        assert pat.confidence == confidence

    def test_invalid_severity_raises(self) -> None:
        """Ungültiges severity wirft ValueError."""
        with pytest.raises(ValueError, match="severity"):
            BugPattern(
                id="BAD-SEV",
                cwe="CWE-1",
                category="test",
                severity="super-critical",
                languages=["python"],
                title="test",
                scan_query="x",
                fix_description="",
                confidence="high",
            )

    def test_invalid_confidence_raises(self) -> None:
        """Ungültiges confidence wirft ValueError."""
        with pytest.raises(ValueError, match="confidence"):
            BugPattern(
                id="BAD-CONF",
                cwe="CWE-1",
                category="test",
                severity="medium",
                languages=["python"],
                title="test",
                scan_query="x",
                fix_description="",
                confidence="ultra",
            )

    def test_invalid_cwe_format_raises(self) -> None:
        """CWE ohne Zahlen oder falsches Format wirft ValueError."""
        with pytest.raises(ValueError, match="CWE"):
            BugPattern(
                id="BAD-CWE",
                cwe="CWE-abc",
                category="test",
                severity="medium",
                languages=["python"],
                title="test",
                scan_query="x",
                fix_description="",
                confidence="high",
            )

    def test_empty_id_raises(self) -> None:
        """Leere id wirft ValueError."""
        with pytest.raises(ValueError, match="id fehlt"):
            BugPattern(
                id="",
                cwe="CWE-1",
                category="test",
                severity="medium",
                languages=["python"],
                title="test",
                scan_query="x",
                fix_description="",
                confidence="high",
            )

    def test_empty_scan_query_raises(self) -> None:
        """Leere scan_query wirft ValueError."""
        with pytest.raises(ValueError, match="scan_query fehlt"):
            BugPattern(
                id="NO-SCAN",
                cwe="CWE-1",
                category="test",
                severity="medium",
                languages=["python"],
                title="test",
                scan_query="",
                fix_description="",
                confidence="high",
            )

    def test_pattern_str_repr(self) -> None:
        """BugPattern hat eine lesbare Repräsentation (via dataclass)."""
        pat = BugPattern(
            id="REPR-01",
            cwe="CWE-22",
            category="security",
            severity="high",
            languages=["go"],
            title="Path Traversal",
            scan_query="os\\.Open\\(.*\\.\\.\\/",
            fix_description="Clean path",
            confidence="medium",
        )
        # Dataclass __repr__
        r = repr(pat)
        assert "REPR-01" in r
        assert "CWE-22" in r
        assert "Path Traversal" in r


# ---------------------------------------------------------------------------
# YAML Parsing
# ---------------------------------------------------------------------------


class TestYamlParsing:
    """Tests für das Parsen von YAML-Dateien."""

    def test_parse_valid_yaml_file(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Gültige YAML-Datei mit einem Pattern wird korrekt geladen."""
        yaml_path = os.path.join(patterns_dir, "test.yaml")
        with open(yaml_path, "w") as f:
            yaml.dump([
                {
                    "id": "TEST-01",
                    "cwe": "CWE-20",
                    "category": "security",
                    "severity": "high",
                    "languages": ["python"],
                    "title": "Test Pattern",
                    "scan_query": "eval(",
                    "fix_description": "Nicht eval verwenden",
                    "confidence": "high",
                },
            ], f)

        loader.patterns_dir = patterns_dir
        patterns = loader.load_all()
        assert len(patterns) == 1
        assert patterns[0].id == "TEST-01"
        assert patterns[0].scan_query == "eval("

    def test_invalid_yaml_syntax(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Kaputtes YAML wird fehlertolerant übersprungen."""
        yaml_path = os.path.join(patterns_dir, "broken.yaml")
        with open(yaml_path, "w") as f:
            f.write("{broken: [yaml: \n  bad indent\n")

        loader.patterns_dir = patterns_dir
        patterns = loader.load_all()
        assert patterns == []

    def test_empty_file(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Leere YAML-Datei = keine Patterns."""
        yaml_path = os.path.join(patterns_dir, "empty.yaml")
        Path(yaml_path).touch()

        loader.patterns_dir = patterns_dir
        patterns = loader.load_all()
        assert patterns == []

    def test_empty_yaml_content(self, patterns_dir: str, loader: PatternLoader) -> None:
        """YAML-Datei mit None/leerem Inhalt."""
        yaml_path = os.path.join(patterns_dir, "null.yaml")
        with open(yaml_path, "w") as f:
            yaml.dump(None, f)

        loader.patterns_dir = patterns_dir
        patterns = loader.load_all()
        assert patterns == []

    def test_not_a_list(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Einzelnes Dict statt Liste = Fehler → übersprungen."""
        yaml_path = os.path.join(patterns_dir, "single.yaml")
        with open(yaml_path, "w") as f:
            yaml.dump({
                "id": "BAD",
                "cwe": "CWE-1",
                "category": "test",
                "severity": "medium",
                "languages": ["python"],
                "title": "bad",
                "scan_query": "x",
                "fix_description": "",
                "confidence": "high",
            }, f)

        loader.patterns_dir = patterns_dir
        patterns = loader.load_all()
        assert patterns == []

    def test_non_dict_entry_skipped(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Einträge, die kein Dict sind, werden übersprungen."""
        yaml_path = os.path.join(patterns_dir, "mixed.yaml")
        with open(yaml_path, "w") as f:
            yaml.dump([
                {
                    "id": "GOOD",
                    "cwe": "CWE-1",
                    "category": "test",
                    "severity": "low",
                    "languages": ["rust"],
                    "title": "gut",
                    "scan_query": "unsafe",
                    "fix_description": "Safe wrappers verwenden",
                    "confidence": "medium",
                },
                "just a string",
                42,
            ], f)

        loader.patterns_dir = patterns_dir
        patterns = loader.load_all()
        assert len(patterns) == 1
        assert patterns[0].id == "GOOD"

    def test_multiple_yaml_files(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Patterns aus mehreren YAML-Dateien werden gesammelt."""
        Path(patterns_dir, "a.yaml").write_text(yaml.dump([
            {"id": "A-01", "cwe": "CWE-1", "category": "sec", "severity": "high",
             "languages": ["py"], "title": "a1", "scan_query": "a()",
             "fix_description": "", "confidence": "high"},
        ]))
        Path(patterns_dir, "b.yaml").write_text(yaml.dump([
            {"id": "B-01", "cwe": "CWE-2", "category": "quality", "severity": "low",
             "languages": ["ts"], "title": "b1", "scan_query": "b()",
             "fix_description": "", "confidence": "low"},
        ]))

        loader.patterns_dir = patterns_dir
        patterns = loader.load_all()
        assert len(patterns) == 2
        ids = {p.id for p in patterns}
        assert ids == {"A-01", "B-01"}

    def test_missing_required_fields_skipped(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Patterns mit fehlenden Pflichtfeldern (id, scan_query) werden übersprungen."""
        yaml_path = os.path.join(patterns_dir, "missing_fields.yaml")
        with open(yaml_path, "w") as f:
            yaml.dump([
                {
                    "id": "OK-01",
                    "cwe": "CWE-1",
                    "category": "test",
                    "severity": "medium",
                    "languages": ["java"],
                    "title": "ok",
                    "scan_query": "ok()",
                    "fix_description": "",
                    "confidence": "medium",
                },
                {
                    # id fehlt
                    "cwe": "CWE-2",
                    "category": "test",
                    "severity": "high",
                    "languages": ["java"],
                    "title": "no id",
                    "scan_query": "bad()",
                    "fix_description": "",
                    "confidence": "high",
                },
                {
                    "id": "NO-SCAN",
                    "cwe": "CWE-3",
                    "category": "test",
                    "severity": "medium",
                    "languages": ["java"],
                    "title": "no scan",
                    # scan_query fehlt
                    "fix_description": "",
                    "confidence": "low",
                },
            ], f)

        loader.patterns_dir = patterns_dir
        patterns = loader.load_all()
        assert len(patterns) == 1
        assert patterns[0].id == "OK-01"


# ---------------------------------------------------------------------------
# Duplikat-Erkennung
# ---------------------------------------------------------------------------


class TestDuplicateDetection:
    """Tests für die Duplikat-ID-Erkennung."""

    def test_duplicate_id_same_file(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Doppelte ID in derselben Datei → Warnung, letzter gewinnt."""
        yaml_path = os.path.join(patterns_dir, "dups.yaml")
        with open(yaml_path, "w") as f:
            yaml.dump([
                {
                    "id": "DUP-01",
                    "cwe": "CWE-1", "category": "test", "severity": "low",
                    "languages": ["py"], "title": "first", "scan_query": "first()",
                    "fix_description": "", "confidence": "low",
                },
                {
                    "id": "DUP-01",
                    "cwe": "CWE-2", "category": "sec", "severity": "critical",
                    "languages": ["js"], "title": "second", "scan_query": "second()",
                    "fix_description": "", "confidence": "high",
                },
            ], f)

        loader.patterns_dir = patterns_dir
        patterns = loader.load_all()
        # Letzter gewinnt
        assert len(patterns) == 1
        assert patterns[0].title == "second"
        assert patterns[0].cwe == "CWE-2"

    def test_duplicate_id_different_files(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Doppelte ID in verschiedenen Dateien → Warnung, letzter gewinnt."""
        Path(patterns_dir, "f1.yaml").write_text(yaml.dump([
            {"id": "SHARED", "cwe": "CWE-1", "category": "a", "severity": "high",
             "languages": ["py"], "title": "from f1", "scan_query": "q1()",
             "fix_description": "", "confidence": "high"},
        ]))
        Path(patterns_dir, "f2.yaml").write_text(yaml.dump([
            {"id": "SHARED", "cwe": "CWE-2", "category": "b", "severity": "low",
             "languages": ["ts"], "title": "from f2", "scan_query": "q2()",
             "fix_description": "", "confidence": "low"},
        ]))

        loader.patterns_dir = patterns_dir
        patterns = loader.load_all()
        assert len(patterns) == 1
        # Letzter (alphabetisch: f2) gewinnt
        assert patterns[0].title == "from f2"


# ---------------------------------------------------------------------------
# Indizes
# ---------------------------------------------------------------------------


class TestIndices:
    """Tests für die Indizes by_id, by_category, by_language."""

    def test_get_by_id(self, patterns_dir: str, loader: PatternLoader) -> None:
        """get_by_id findet ein Pattern anhand seiner ID."""
        Path(patterns_dir, "p.yaml").write_text(yaml.dump([
            {"id": "FIND-ME", "cwe": "CWE-1", "category": "test",
             "severity": "medium", "languages": ["go"], "title": "findable",
             "scan_query": "find()", "fix_description": "", "confidence": "high"},
        ]))
        loader.patterns_dir = patterns_dir
        pat = loader.get_by_id("FIND-ME")
        assert pat is not None
        assert pat.id == "FIND-ME"
        assert pat.title == "findable"

    def test_get_by_id_not_found(self, loader: PatternLoader) -> None:
        """Unbekannte ID → None."""
        loader.patterns_dir = "/nonexistent"
        pat = loader.get_by_id("NONEXISTENT")
        assert pat is None

    def test_get_by_category(self, patterns_dir: str, loader: PatternLoader) -> None:
        """get_by_category filtert nach Kategorie."""
        Path(patterns_dir, "cat.yaml").write_text(yaml.dump([
            {"id": "SEC-1", "cwe": "CWE-1", "category": "security",
             "severity": "high", "languages": ["py"], "title": "s1",
             "scan_query": "s1()", "fix_description": "", "confidence": "high"},
            {"id": "SEC-2", "cwe": "CWE-2", "category": "security",
             "severity": "medium", "languages": ["js"], "title": "s2",
             "scan_query": "s2()", "fix_description": "", "confidence": "medium"},
            {"id": "QUAL-1", "cwe": "CWE-3", "category": "code-quality",
             "severity": "low", "languages": ["ts"], "title": "q1",
             "scan_query": "q1()", "fix_description": "", "confidence": "low"},
        ]))
        loader.patterns_dir = patterns_dir
        sec = loader.get_by_category("security")
        assert len(sec) == 2
        assert all(p.category == "security" for p in sec)

    def test_get_by_category_unknown(self, loader: PatternLoader) -> None:
        """Unbekannte Kategorie → leere Liste."""
        pats = loader.get_by_category("nonexistent-category")
        assert pats == []

    def test_get_by_language(self, patterns_dir: str, loader: PatternLoader) -> None:
        """get_by_language filtert nach Sprache."""
        Path(patterns_dir, "lang.yaml").write_text(yaml.dump([
            {"id": "PY-1", "cwe": "CWE-1", "category": "sec",
             "severity": "high", "languages": ["python"], "title": "p1",
             "scan_query": "p1()", "fix_description": "", "confidence": "high"},
            {"id": "PY-2", "cwe": "CWE-2", "category": "sec",
             "severity": "medium", "languages": ["python", "go"],
             "title": "p2", "scan_query": "p2()",
             "fix_description": "", "confidence": "medium"},
            {"id": "TS-1", "cwe": "CWE-3", "category": "quality",
             "severity": "low", "languages": ["typescript"], "title": "t1",
             "scan_query": "t1()", "fix_description": "", "confidence": "low"},
        ]))
        loader.patterns_dir = patterns_dir
        py = loader.get_by_language("python")
        assert len(py) == 2
        go = loader.get_by_language("go")
        assert len(go) == 1
        assert go[0].id == "PY-2"

    def test_get_by_language_unknown(self, loader: PatternLoader) -> None:
        """Unbekannte Sprache → leere Liste."""
        pats = loader.get_by_language("brainfuck")
        assert pats == []

    def test_pattern_appears_in_multiple_languages(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Ein Pattern mit mehreren Sprachen erscheint in jedem Sprach-Index."""
        Path(patterns_dir, "multi.yaml").write_text(yaml.dump([
            {"id": "MULTI", "cwe": "CWE-1", "category": "sec",
             "severity": "high", "languages": ["python", "go", "rust"],
             "title": "multi-lang", "scan_query": "multi()",
             "fix_description": "", "confidence": "high"},
        ]))
        loader.patterns_dir = patterns_dir
        assert len(loader.get_by_language("python")) == 1
        assert len(loader.get_by_language("go")) == 1
        assert len(loader.get_by_language("rust")) == 1
        # Aber insgesamt nur 1 Pattern
        assert len(loader.load_all()) == 1


# ---------------------------------------------------------------------------
# Filter
# ---------------------------------------------------------------------------


class TestFilter:
    """Tests für die filter()-Methode."""

    @pytest.fixture(autouse=True)
    def _setup(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Richtet diverse Test-Patterns ein."""
        Path(patterns_dir, "data.yaml").write_text(yaml.dump([
            {"id": "S-PY-CR", "cwe": "CWE-1", "category": "security",
             "severity": "critical", "languages": ["python"],
             "title": "sec-py-crit", "scan_query": "x()",
             "fix_description": "", "confidence": "high"},
            {"id": "S-PY-HI", "cwe": "CWE-2", "category": "security",
             "severity": "high", "languages": ["python"],
             "title": "sec-py-high", "scan_query": "x()",
             "fix_description": "", "confidence": "high"},
            {"id": "S-JS-ME", "cwe": "CWE-3", "category": "security",
             "severity": "medium", "languages": ["javascript"],
             "title": "sec-js-med", "scan_query": "x()",
             "fix_description": "", "confidence": "medium"},
            {"id": "Q-TS-LO", "cwe": "CWE-4", "category": "code-quality",
             "severity": "low", "languages": ["typescript"],
             "title": "qual-ts-low", "scan_query": "x()",
             "fix_description": "", "confidence": "low"},
            {"id": "Q-GO-LO", "cwe": "CWE-5", "category": "code-quality",
             "severity": "low", "languages": ["go"],
             "title": "qual-go-low", "scan_query": "x()",
             "fix_description": "", "confidence": "low"},
        ]))
        loader.patterns_dir = patterns_dir

    def test_filter_no_args(self, loader: PatternLoader) -> None:
        """Ohne Filterkriterien → alle Patterns."""
        pats = loader.filter()
        assert len(pats) == 5

    def test_filter_by_category(self, loader: PatternLoader) -> None:
        """Filter nach Kategorie."""
        pats = loader.filter(categories=["security"])
        assert len(pats) == 3
        assert all(p.category == "security" for p in pats)

    def test_filter_by_multiple_categories(self, loader: PatternLoader) -> None:
        """Filter nach mehreren Kategorien."""
        pats = loader.filter(categories=["security", "code-quality"])
        assert len(pats) == 5

    def test_filter_by_language(self, loader: PatternLoader) -> None:
        """Filter nach Sprache."""
        pats = loader.filter(languages=["python"])
        assert len(pats) == 2

    def test_filter_by_severity(self, loader: PatternLoader) -> None:
        """Filter nach Severity."""
        pats = loader.filter(severities=["critical", "high"])
        assert len(pats) == 2
        assert {p.id for p in pats} == {"S-PY-CR", "S-PY-HI"}

    def test_filter_by_min_confidence(self, loader: PatternLoader) -> None:
        """Filter nach Mindest-Konfidenz."""
        # low → alle 5
        assert len(loader.filter(min_confidence="low")) == 5
        # medium → 3 (ohne low-confidence)
        assert len(loader.filter(min_confidence="medium")) == 3
        ids_med = {p.id for p in loader.filter(min_confidence="medium")}
        assert "Q-TS-LO" not in ids_med
        assert "Q-GO-LO" not in ids_med
        # high → 2 (nur high)
        assert len(loader.filter(min_confidence="high")) == 2

    def test_filter_combined(self, loader: PatternLoader) -> None:
        """Kombinierte Filter (AND)."""
        pats = loader.filter(
            categories=["security"],
            languages=["python"],
            severities=["critical", "high"],
        )
        assert len(pats) == 2
        assert {p.id for p in pats} == {"S-PY-CR", "S-PY-HI"}

    def test_filter_no_match(self, loader: PatternLoader) -> None:
        """Filter ohne Treffer → leere Liste."""
        pats = loader.filter(categories=["nonexistent"])
        assert pats == []

    def test_filter_invalid_min_confidence(self, loader: PatternLoader) -> None:
        """Unbekanntes min_confidence → wie low (alle)."""
        pats = loader.filter(min_confidence="ultra")
        assert len(pats) == 5


# ---------------------------------------------------------------------------
# Leeres Verzeichnis
# ---------------------------------------------------------------------------


class TestEmptyDirectory:
    """Tests für Edge Cases mit Verzeichnissen."""

    def test_empty_patterns_dir(self, tmp_path: Path) -> None:
        """Leeres patterns-Verzeichnis → leere Liste."""
        loader = PatternLoader(str(tmp_path / "empty_patterns"))
        os.makedirs(tmp_path / "empty_patterns", exist_ok=True)
        loader.patterns_dir = str(tmp_path / "empty_patterns")
        assert loader.load_all() == []

    def test_nonexistent_patterns_dir(self, loader: PatternLoader) -> None:
        """Nicht-existierendes Verzeichnis → leere Liste."""
        loader.patterns_dir = "/tmp/nonexistent_patterns_xyz"
        assert loader.load_all() == []

    def test_no_yaml_files(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Verzeichnis nur mit Nicht-YAML-Dateien → leere Liste."""
        Path(patterns_dir, "readme.txt").write_text("no patterns here")
        Path(patterns_dir, "notes.md").write_text("# Pattern Notes")
        loader.patterns_dir = patterns_dir
        assert loader.load_all() == []


# ---------------------------------------------------------------------------
# Validierung (CWE, Severity, Confidence)
# ---------------------------------------------------------------------------


class TestValidation:
    """Tests für Validierungslogik beim Laden."""

    def test_invalid_cwe_skipped(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Pattern mit ungültigem CWE-Format wird übersprungen."""
        Path(patterns_dir, "cwe.yaml").write_text(yaml.dump([
            {"id": "GOOD", "cwe": "CWE-20", "category": "sec",
             "severity": "high", "languages": ["py"], "title": "good",
             "scan_query": "q()", "fix_description": "", "confidence": "high"},
            {"id": "BAD-CWE", "cwe": "CWE-abcd", "category": "sec",
             "severity": "high", "languages": ["py"], "title": "bad cwe",
             "scan_query": "q()", "fix_description": "", "confidence": "high"},
            {"id": "NO-CWE", "cwe": "", "category": "sec",
             "severity": "high", "languages": ["py"], "title": "no cwe",
             "scan_query": "q()", "fix_description": "", "confidence": "high"},
        ]))
        loader.patterns_dir = patterns_dir
        patterns = loader.load_all()
        assert len(patterns) == 2  # GOOD + NO-CWE (leeres CWE ist OK)
        ids = {p.id for p in patterns}
        assert "BAD-CWE" not in ids

    def test_invalid_severity_skipped(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Pattern mit ungültigem severity wird übersprungen."""
        Path(patterns_dir, "sev.yaml").write_text(yaml.dump([
            {"id": "GOOD-SEV", "cwe": "CWE-1", "category": "sec",
             "severity": "critical", "languages": ["py"], "title": "ok",
             "scan_query": "q()", "fix_description": "", "confidence": "high"},
            {"id": "BAD-SEV", "cwe": "CWE-2", "category": "sec",
             "severity": "super-urgent", "languages": ["py"], "title": "bad",
             "scan_query": "q()", "fix_description": "", "confidence": "high"},
        ]))
        loader.patterns_dir = patterns_dir
        patterns = loader.load_all()
        assert len(patterns) == 1
        assert patterns[0].id == "GOOD-SEV"

    def test_invalid_confidence_skipped(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Pattern mit ungültigem confidence wird übersprungen."""
        Path(patterns_dir, "conf.yaml").write_text(yaml.dump([
            {"id": "GOOD-CF", "cwe": "CWE-1", "category": "sec",
             "severity": "medium", "languages": ["py"], "title": "ok",
             "scan_query": "q()", "fix_description": "", "confidence": "high"},
            {"id": "BAD-CF", "cwe": "CWE-2", "category": "sec",
             "severity": "medium", "languages": ["py"], "title": "bad",
             "scan_query": "q()", "fix_description": "", "confidence": "certain"},
        ]))
        loader.patterns_dir = patterns_dir
        patterns = loader.load_all()
        assert len(patterns) == 1
        assert patterns[0].id == "GOOD-CF"


# ---------------------------------------------------------------------------
# Unbekannte Sprache (warnen, nicht ablehnen)
# ---------------------------------------------------------------------------


class TestUnknownLanguage:
    """Unbekannte Sprachen werden gewarnt, aber nicht abgelehnt."""

    def test_unknown_language_loaded(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Pattern mit unbekannter Sprache wird trotzdem geladen."""
        Path(patterns_dir, "unknown.yaml").write_text(yaml.dump([
            {"id": "EXOTIC", "cwe": "CWE-1", "category": "sec",
             "severity": "high", "languages": ["brainfuck", "intercal"],
             "title": "exotic langs", "scan_query": "q()",
             "fix_description": "", "confidence": "high"},
        ]))
        loader.patterns_dir = patterns_dir
        patterns = loader.load_all()
        assert len(patterns) == 1
        assert patterns[0].id == "EXOTIC"
        assert "brainfuck" in patterns[0].languages

    def test_mixed_known_unknown_languages(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Pattern mit bekannten und unbekannten Sprachen — alle geladen."""
        Path(patterns_dir, "mixed_lang.yaml").write_text(yaml.dump([
            {"id": "MIXED", "cwe": "CWE-1", "category": "sec",
             "severity": "high", "languages": ["python", "newlang"],
             "title": "mixed", "scan_query": "q()",
             "fix_description": "", "confidence": "high"},
        ]))
        loader.patterns_dir = patterns_dir
        patterns = loader.load_all()
        assert len(patterns) == 1
        assert "python" in patterns[0].languages
        assert "newlang" in patterns[0].languages

    def test_language_not_string(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Sprache als Nicht-String (z.B. Zahl) — wandelt sich in String."""
        Path(patterns_dir, "lang_type.yaml").write_text(yaml.dump([
            {"id": "NUM-LANG", "cwe": "CWE-1", "category": "sec",
             "severity": "high", "languages": [42],
             "title": "numeric lang", "scan_query": "q()",
             "fix_description": "", "confidence": "high"},
        ]))
        loader.patterns_dir = patterns_dir
        patterns = loader.load_all()
        assert len(patterns) == 1
        assert "42" in patterns[0].languages


# ---------------------------------------------------------------------------
# Fehlertoleranz
# ---------------------------------------------------------------------------


class TestErrorTolerance:
    """Eine kaputte Datei reisst andere nicht mit."""

    def test_one_broken_does_not_break_others(
        self, patterns_dir: str, loader: PatternLoader
    ) -> None:
        Path(patterns_dir, "good.yaml").write_text(yaml.dump([
            {"id": "GOOD-1", "cwe": "CWE-1", "category": "sec",
             "severity": "high", "languages": ["py"], "title": "ok",
             "scan_query": "q()", "fix_description": "", "confidence": "high"},
        ]))
        Path(patterns_dir, "broken.yaml").write_text("{bad: yaml: [[[")
        Path(patterns_dir, "empty.yaml").write_text("")
        Path(patterns_dir, "also-good.yaml").write_text(yaml.dump([
            {"id": "GOOD-2", "cwe": "CWE-2", "category": "quality",
             "severity": "low", "languages": ["ts"], "title": "also ok",
             "scan_query": "q2()", "fix_description": "", "confidence": "low"},
        ]))

        loader.patterns_dir = patterns_dir
        patterns = loader.load_all()
        ids = {p.id for p in patterns}
        assert "GOOD-1" in ids
        assert "GOOD-2" in ids
        assert len(patterns) == 2


# ---------------------------------------------------------------------------
# Caching / Idempotenz
# ---------------------------------------------------------------------------


class TestCaching:
    """load_all() ist idempotent und cached."""

    def test_load_all_idempotent(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Mehrmaliges load_all gibt dieselben Ergebnisse."""
        Path(patterns_dir, "a.yaml").write_text(yaml.dump([
            {"id": "STABLE", "cwe": "CWE-1", "category": "sec",
             "severity": "high", "languages": ["py"], "title": "stable",
             "scan_query": "q()", "fix_description": "", "confidence": "high"},
        ]))
        loader.patterns_dir = patterns_dir
        r1 = loader.load_all()
        r2 = loader.load_all()
        assert len(r1) == len(r2) == 1
        assert r1[0].id == r2[0].id

    def test_clear_resets_cache(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Nach clear() wird load_all() neu laden."""
        Path(patterns_dir, "a.yaml").write_text(yaml.dump([
            {"id": "CACHE-1", "cwe": "CWE-1", "category": "sec",
             "severity": "high", "languages": ["py"], "title": "cached",
             "scan_query": "q()", "fix_description": "", "confidence": "high"},
        ]))
        loader.patterns_dir = patterns_dir
        loader.load_all()
        # Neue Datei nach erstem Laden
        Path(patterns_dir, "b.yaml").write_text(yaml.dump([
            {"id": "CACHE-2", "cwe": "CWE-2", "category": "quality",
             "severity": "low", "languages": ["ts"], "title": "new",
             "scan_query": "q2()", "fix_description": "", "confidence": "low"},
        ]))
        # Ohne clear: immer noch nur 1
        assert len(loader.load_all()) == 1
        # Mit clear: 2
        loader.clear()
        assert len(loader.load_all()) == 2


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    """Tests für das Singleton-Verhalten."""

    def setup_method(self) -> None:
        PatternLoader.reset_singleton()

    def test_get_instance_returns_same(self) -> None:
        """get_instance() gibt immer dieselbe Instanz zurück."""
        loader1 = PatternLoader.get_instance()
        loader2 = PatternLoader.get_instance()
        assert loader1 is loader2

    def test_singleton_shares_data(self, tmp_path: Path) -> None:
        """Patterns über Singleton geladen sind über get_instance() sichtbar."""
        d = tmp_path / "patterns"
        d.mkdir()
        Path(d, "test.yaml").write_text(yaml.dump([
            {"id": "SINGLE-1", "cwe": "CWE-1", "category": "sec",
             "severity": "high", "languages": ["py"], "title": "singleton",
             "scan_query": "q()", "fix_description": "", "confidence": "high"},
        ]))

        PatternLoader.reset_singleton()
        loader1 = PatternLoader.get_instance()
        loader1.patterns_dir = str(d)
        loader1.load_all()

        loader2 = PatternLoader.get_instance()
        # Sollte geladen sein, da es dieselbe Instanz ist
        assert len(loader2.load_all()) == 1

    def test_singleton_after_reset_new_instance(self) -> None:
        """Nach reset_singleton() erzeugt get_instance() eine neue Instanz."""
        loader1 = PatternLoader.get_instance()
        PatternLoader.reset_singleton()
        loader2 = PatternLoader.get_instance()
        assert loader1 is not loader2

    def test_new_instance_not_singleton(self) -> None:
        """Mit ``new PatternLoader()`` erzeugt man eine separate Instanz."""
        PatternLoader.reset_singleton()
        singleton = PatternLoader.get_instance()
        manual = PatternLoader()
        assert singleton is not manual
        # manual ist nicht die Singleton-Instanz
        assert PatternLoader.get_instance() is singleton


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


class TestPerformance:
    """500+ Patterns in <100ms."""

    def test_large_volume_performance(self, tmp_path: Path) -> None:
        """500 Patterns in einer Datei sollten in unter 500ms geladen werden."""
        d = tmp_path / "big_patterns"
        d.mkdir()
        big_data = []
        for i in range(500):
            big_data.append({
                "id": f"PERF-{i:04d}",
                "cwe": "CWE-20",
                "category": "security" if i % 2 == 0 else "code-quality",
                "severity": ["critical", "high", "medium", "low", "info"][i % 5],
                "languages": [["python"], ["typescript"], ["go", "rust"]][i % 3],
                "title": f"Performance Test Pattern {i}",
                "scan_query": f"pattern_{i}()",
                "fix_description": f"Fix for pattern {i}",
                "confidence": ["high", "medium", "low"][i % 3],
            })

        # In eine einzige große Datei (realistischer)
        Path(d, "big.yaml").write_text(yaml.dump(big_data))

        loader = PatternLoader(str(d))
        start = time.perf_counter()
        patterns = loader.load_all()
        elapsed = (time.perf_counter() - start) * 1000  # ms

        assert len(patterns) == 500
        assert elapsed < 500, f"Performance-Test: {elapsed:.1f}ms (Grenze: 500ms)"

    def test_large_volume_filter_fast(self, tmp_path: Path) -> None:
        """Filter auf 500 Patterns sollte ebenfalls schnell sein."""
        d = tmp_path / "filter_perf"
        d.mkdir()
        big_data = []
        for i in range(500):
            big_data.append({
                "id": f"FPERF-{i:04d}",
                "cwe": "CWE-20",
                "category": "security" if i % 2 == 0 else "code-quality",
                "severity": ["critical", "high", "medium", "low", "info"][i % 5],
                "languages": [["python"], ["typescript"], ["go"]][i % 3],
                "title": f"Filter Test {i}",
                "scan_query": f"fpattern_{i}()",
                "fix_description": "",
                "confidence": ["high", "medium", "low"][i % 3],
            })
        Path(d, "big.yaml").write_text(yaml.dump(big_data))

        loader = PatternLoader(str(d))
        loader.load_all()

        start = time.perf_counter()
        result = loader.filter(
            categories=["security"],
            languages=["python"],
            severities=["critical", "high"],
            min_confidence="high",
        )
        elapsed = (time.perf_counter() - start) * 1000

        assert len(result) > 0
        assert elapsed < 50, f"Filter-Performance: {elapsed:.1f}ms (Grenze: 50ms)"


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------


class TestIntegration:
    """Integrationstests BugPattern ↔ Loader."""

    def test_pattern_from_loader_is_bugpattern(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Loader gibt BugPattern-Instanzen zurück."""
        Path(patterns_dir, "int.yaml").write_text(yaml.dump([
            {"id": "INT-01", "cwe": "CWE-22", "category": "security",
             "severity": "high", "languages": ["go"], "title": "Path Trav",
             "scan_query": "path\\.Join", "fix_description": "Use safe path",
             "confidence": "high"},
        ]))
        loader.patterns_dir = patterns_dir
        pats = loader.load_all()
        assert len(pats) == 1
        assert isinstance(pats[0], BugPattern)
        assert isinstance(pats[0].languages, list)
        assert isinstance(pats[0].cwe, str)

    def test_realistic_owasp_pattern(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Realistisches OWASP-Pattern aus der Aufgabenstellung."""
        Path(patterns_dir, "owasp.yaml").write_text(yaml.dump([
            {
                "id": "OWASP-01",
                "cwe": "CWE-20",
                "category": "security",
                "severity": "critical",
                "languages": ["typescript", "javascript", "python", "go"],
                "title": "Fehlende Input-Validierung",
                "scan_query": "express\\.(post|put|patch)\\(.*req\\.body",
                "fix_description": "req.body vor Verwendung mit Zod/Yup validieren",
                "confidence": "high",
            },
            {
                "id": "TS-001",
                "cwe": "CWE-754",
                "category": "code-quality",
                "severity": "high",
                "languages": ["typescript"],
                "title": "any-Typ vermeiden",
                "scan_query": ":\\s*any\\b",
                "fix_description": "Durch konkreten Typ ersetzen",
                "confidence": "medium",
            },
        ]))
        loader.patterns_dir = patterns_dir
        pats = loader.load_all()
        assert len(pats) == 2

        owasp = loader.get_by_id("OWASP-01")
        assert owasp is not None
        assert owasp.cwe == "CWE-20"
        assert owasp.severity == "critical"
        assert "typescript" in owasp.languages
        assert owasp.confidence == "high"

        ts = loader.get_by_id("TS-001")
        assert ts is not None
        assert ts.cwe == "CWE-754"
        assert ts.severity == "high"
        assert ts.languages == ["typescript"]
        assert ts.confidence == "medium"

    def test_full_pipeline_load_filter_index(self, patterns_dir: str, loader: PatternLoader) -> None:
        """Komplette Pipeline: load → filter → index."""
        Path(patterns_dir, "pipeline.yaml").write_text(yaml.dump([
            {"id": "A", "cwe": "CWE-1", "category": "security",
             "severity": "critical", "languages": ["python", "go"],
             "title": "A", "scan_query": "a()",
             "fix_description": "", "confidence": "high"},
            {"id": "B", "cwe": "CWE-2", "category": "security",
             "severity": "high", "languages": ["python"],
             "title": "B", "scan_query": "b()",
             "fix_description": "", "confidence": "medium"},
            {"id": "C", "cwe": "CWE-3", "category": "code-quality",
             "severity": "low", "languages": ["go"],
             "title": "C", "scan_query": "c()",
             "fix_description": "", "confidence": "low"},
        ]))
        loader.patterns_dir = patterns_dir

        # 1. Alle laden
        assert len(loader.load_all()) == 3

        # 2. Nach ID
        assert loader.get_by_id("A") is not None
        assert loader.get_by_id("NON") is None

        # 3. Nach Kategorie
        assert len(loader.get_by_category("security")) == 2
        assert len(loader.get_by_category("code-quality")) == 1

        # 4. Nach Sprache
        assert len(loader.get_by_language("python")) == 2
        assert len(loader.get_by_language("go")) == 2

        # 5. Kombinierter Filter
        filtered = loader.filter(
            categories=["security"],
            languages=["python"],
            severities=["critical", "high"],
        )
        assert len(filtered) == 2
        assert {p.id for p in filtered} == {"A", "B"}

        # 6. Confidence-Filter
        assert len(loader.filter(min_confidence="high")) == 1  # nur A
        assert len(loader.filter(min_confidence="medium")) == 2  # A + B


# ---------------------------------------------------------------------------
# Valid constants
# ---------------------------------------------------------------------------


class TestConstants:
    """Die Konstanten-VALID-Sets sind korrekt definiert."""

    def test_valid_severities(self) -> None:
        assert "critical" in VALID_SEVERITIES
        assert "high" in VALID_SEVERITIES
        assert "medium" in VALID_SEVERITIES
        assert "low" in VALID_SEVERITIES
        assert "info" in VALID_SEVERITIES
        assert len(VALID_SEVERITIES) == 5

    def test_valid_confidences(self) -> None:
        assert "high" in VALID_CONFIDENCES
        assert "medium" in VALID_CONFIDENCES
        assert "low" in VALID_CONFIDENCES
        assert len(VALID_CONFIDENCES) == 3

    def test_known_languages_not_empty(self) -> None:
        assert len(KNOWN_LANGUAGES) > 20
        assert "python" in KNOWN_LANGUAGES
        assert "typescript" in KNOWN_LANGUAGES
        assert "go" in KNOWN_LANGUAGES
        assert "rust" in KNOWN_LANGUAGES
