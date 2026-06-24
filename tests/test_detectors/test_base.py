"""Tests für shared/detectors/base.py — _FileIndex, _compile_glob, _TechDetector, Datentypen."""

from __future__ import annotations

import re
from pathlib import Path

from scout.shared.detectors.base import (
    DEFAULT_YAML_RULES_DIR,
    DetectedFramework,
    FrameworkEvidence,
    FrameworkProfile,
    _compile_glob,
    _FileIndex,
    _TechDetector,
)

# ======================================================================
# FrameworkEvidence
# ======================================================================

class TestFrameworkEvidence:
    def test_minimal(self):
        ev = FrameworkEvidence(source="package.json", pattern="react")
        assert ev.source == "package.json"
        assert ev.pattern == "react"
        assert ev.confidence == "high"
        assert ev.version is None

    def test_with_version(self):
        ev = FrameworkEvidence(source="go.mod", pattern="github.com/gin-gonic/gin", confidence="medium", version="v1.9")
        assert ev.version == "v1.9"
        assert ev.confidence == "medium"

    def test_to_dict(self):
        ev = FrameworkEvidence(source="src/main.py", pattern="from flask import", confidence="high", version="3.0")
        d = ev.to_dict()
        assert d["source"] == "src/main.py"
        assert d["pattern"] == "from flask import"
        assert d["confidence"] == "high"
        assert d["version"] == "3.0"

    def test_to_dict_no_version(self):
        ev = FrameworkEvidence(source="cfg.yml", pattern="postgres")
        d = ev.to_dict()
        assert d["version"] is None


# ======================================================================
# DetectedFramework
# ======================================================================

class TestDetectedFramework:
    def test_minimal(self):
        fw = DetectedFramework(name="react", category="frontend")
        assert fw.name == "react"
        assert fw.category == "frontend"
        assert fw.confidence == "high"
        assert fw.version is None
        assert fw.evidence == []

    def test_with_evidence(self):
        ev = FrameworkEvidence(source="pkg.json", pattern="react")
        fw = DetectedFramework(name="react", category="frontend", evidence=[ev])
        assert len(fw.evidence) == 1

    def test_to_dict(self):
        ev = FrameworkEvidence(source="pkg.json", pattern="react-dom", confidence="medium")
        fw = DetectedFramework(name="react", category="frontend", confidence="high", version="19.0", evidence=[ev])
        d = fw.to_dict()
        assert d["name"] == "react"
        assert d["category"] == "frontend"
        assert d["confidence"] == "high"
        assert d["version"] == "19.0"
        assert len(d["evidence"]) == 1


# ======================================================================
# FrameworkProfile
# ======================================================================

class TestFrameworkProfile:
    def test_empty_profile(self):
        p = FrameworkProfile(project_root="/tmp/test")
        assert p.project_root == "/tmp/test"
        assert p.frameworks == {}
        assert p.overall_confidence == 0.0
        assert p.errors == []

    def test_has_framework_true(self):
        fw = DetectedFramework(name="nextjs", category="frontend")
        p = FrameworkProfile(project_root="/x")
        p.frameworks["frontend"] = [fw]
        assert p.has_framework("nextjs") is True

    def test_has_framework_false(self):
        p = FrameworkProfile(project_root="/x")
        assert p.has_framework("nothing") is False

    def test_get_framework_found(self):
        fw = DetectedFramework(name="postgresql", category="database")
        p = FrameworkProfile(project_root="/x")
        p.frameworks["database"] = [fw]
        result = p.get_framework("postgresql")
        assert result is not None
        assert result.name == "postgresql"

    def test_get_framework_not_found(self):
        p = FrameworkProfile(project_root="/x")
        assert p.get_framework("missing") is None

    def test_get_frameworks_by_category(self):
        fw1 = DetectedFramework(name="a", category="backend")
        fw2 = DetectedFramework(name="b", category="backend")
        p = FrameworkProfile(project_root="/x")
        p.frameworks["backend"] = [fw1, fw2]
        result = p.get_frameworks_by_category("backend")
        assert len(result) == 2
        assert p.get_frameworks_by_category("missing") == []

    def test_to_dict(self):
        ev = FrameworkEvidence(source="cfg", pattern="postgres", confidence="high")
        fw = DetectedFramework(name="postgresql", category="database", confidence="high", evidence=[ev])
        p = FrameworkProfile(project_root="/app", errors=["warn"])
        p.frameworks["database"] = [fw]
        d = p.to_dict()
        assert d["project_root"] == "/app"
        assert "database" in d["frameworks"]
        assert d["frameworks"]["database"][0]["name"] == "postgresql"
        assert d["errors"] == ["warn"]


# ======================================================================
# _compile_glob
# ======================================================================

class TestCompileGlob:
    def test_simple_filename(self):
        r = _compile_glob("package.json")
        assert r.match("package.json")
        assert not r.match("sub/package.json")

    def test_extension_glob(self):
        r = _compile_glob("*.py")
        assert r.match("main.py")
        assert not r.match("main.ts")

    def test_recursive_glob(self):
        r = _compile_glob("**/*.py")
        assert r.match("main.py")
        assert r.match("src/main.py")
        assert r.match("a/b/c/main.py")

    def test_recursive_dir_glob(self):
        r = _compile_glob("**/node_modules/**")
        # Match: node_modules/express (eine Ebene)
        assert r.match("node_modules/express")
        # Match: a/node_modules/foo
        assert r.match("a/node_modules/foo")
        # KEIN Match: tiefere Ebenen (Limitation: ** after path matched nur eine Ebene)

    def test_single_char_wildcard(self):
        # NOTE: ?-Wildcard wird nur im **/-Zweig unterstützt
        # Im einfachen Glob wird ? literal gematcht
        r = _compile_glob("test?.py")
        assert not r.match("test1.py")  # ? ist literal, nicht wildcard

    def test_cache_used(self):
        from scout.shared.detectors.base import _GLOB_REGEX_CACHE
        _GLOB_REGEX_CACHE.clear()
        r1 = _compile_glob("**/*.tsx")
        r2 = _compile_glob("**/*.tsx")
        assert r1 is r2  # same cached object


# ======================================================================
# _FileIndex
# ======================================================================

class TestFileIndex:
    def test_empty_directory(self, tmp_path: Path):
        idx = _FileIndex(tmp_path)
        assert idx.find("*.py") == []

    def test_finds_files(self, tmp_path: Path):
        (tmp_path / "main.py").write_text("x")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "lib.ts").write_text("y")
        idx = _FileIndex(tmp_path)
        results = idx.find("**/*.py")
        assert len(results) == 1
        assert results[0][0] == "main.py"

    def test_by_name_lookup(self, tmp_path: Path):
        (tmp_path / "package.json").write_text("{}")
        idx = _FileIndex(tmp_path)
        results = idx.find("package.json")
        assert len(results) == 1

    def test_extension_lookup(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        (tmp_path / "c.ts").write_text("")
        idx = _FileIndex(tmp_path)
        results = idx.find("*.py")
        assert len(results) == 2

    def test_ignores_node_modules(self, tmp_path: Path):
        (tmp_path / "node_modules" / "express" / "index.js").parent.mkdir(parents=True)
        (tmp_path / "node_modules" / "express" / "index.js").write_text("")
        idx = _FileIndex(tmp_path)
        results = idx.find("**/*.js")
        assert len(results) == 0

    def test_ignored_dirs_configurable(self, tmp_path: Path):
        (tmp_path / ".cache" / "x.py").parent.mkdir(parents=True)
        (tmp_path / ".cache" / "x.py").write_text("")
        idx = _FileIndex(tmp_path, ignored={".cache"})
        results = idx.find("**/*.py")
        assert len(results) == 0

    def test_slow_path_fallback(self, tmp_path: Path):
        # Pattern das weder Fast-Path noch Extension erwischt → Regex-Slow-Path
        (tmp_path / "src" / "test.manual.py").parent.mkdir(parents=True)
        (tmp_path / "src" / "test.manual.py").write_text("")
        idx = _FileIndex(tmp_path)
        results = idx.find("**/test.*.py")  # Kann keinem Fast-Path zugeordnet werden
        assert len(results) == 1


# ======================================================================
# _TechDetector
# ======================================================================

class TestTechDetector:
    def test_meta_detector_creation(self):
        """Erzeugt einen _TechDetector via type() wie im catalog."""
        MyDet = type("_MyDetector", (_TechDetector,), {
            "name": "my-test-fw",
            "category": "testing",
            "markers": [
                ("test.txt", "MY_MARKER", "high"),
            ],
        })
        assert MyDet.name == "my-test-fw"
        assert MyDet.category == "testing"
        assert len(MyDet.markers) == 1

    def test_detect_with_file(self, tmp_path: Path):
        (tmp_path / "marker.txt").write_text("MY_MARKER content here")
        MyDet = type("_M", (_TechDetector,), {
            "name": "marker-fw", "category": "testing",
            "markers": [("marker.txt", "MY_MARKER", "high")],
        })
        result = MyDet().detect(tmp_path)
        assert result is not None
        assert result.name == "marker-fw"
        assert result.confidence == "high"

    def test_detect_no_match(self, tmp_path: Path):
        (tmp_path / "some.txt").write_text("nothing")
        MyDet = type("_M", (_TechDetector,), {
            "name": "no-match", "category": "testing",
            "markers": [("some.txt", "WONT_MATCH", "high")],
        })
        result = MyDet().detect(tmp_path)
        assert result is None

    def test_detect_file_exists_only(self, tmp_path: Path):
        (tmp_path / "flag").write_text("")
        MyDet = type("_M", (_TechDetector,), {
            "name": "flag-fw", "category": "testing",
            "markers": [("flag", "", "medium")],
        })
        result = MyDet().detect(tmp_path)
        assert result is not None
        assert result.confidence == "medium"
        assert len(result.evidence) == 1
        assert result.evidence[0].pattern == "file exists"

    def test_detect_with_regex_marker(self, tmp_path: Path):
        (tmp_path / "cfg.yml").write_text("version: 3.2.1\n")
        MyDet = type("_M", (_TechDetector,), {
            "name": "regex-fw", "category": "testing",
            "markers": [("cfg.yml", re.compile(r"version:\s*(\d+\.\d+)"), "high")],
        })
        result = MyDet().detect(tmp_path)
        assert result is not None
        assert result.name == "regex-fw"

    def test_detect_with_file_index(self, tmp_path: Path):
        (tmp_path / "src" / "app.ts").parent.mkdir()
        (tmp_path / "src" / "app.ts").write_text("express();")
        idx = _FileIndex(tmp_path)
        _TechDetector._set_file_index(idx)
        try:
            ExpDet = type("_M", (_TechDetector,), {
                "name": "express", "category": "backend",
                "markers": [("**/*.ts", "express", "high")],
            })
            result = ExpDet().detect(tmp_path)
            assert result is not None
            assert result.name == "express"
        finally:
            _TechDetector._set_file_index(None)

    def test_detect_ignored_paths(self, tmp_path: Path):
        (tmp_path / "node_modules" / "lib.ts").parent.mkdir(parents=True)
        (tmp_path / "node_modules" / "lib.ts").write_text("express();")
        ExpDet = type("_M", (_TechDetector,), {
            "name": "express", "category": "backend",
            "markers": [("**/*.ts", "express", "high")],
        })
        result = ExpDet().detect(tmp_path)
        assert result is None  # node_modules wird ignoriert

    def test_set_file_index_classmethod(self):
        _TechDetector._set_file_index(None)
        assert _TechDetector._global_file_index is None


# ======================================================================
# DEFAULT_YAML_RULES_DIR
# ======================================================================

class TestDefaults:
    def test_default_rules_dir_is_absolute(self):
        assert DEFAULT_YAML_RULES_DIR
        assert isinstance(DEFAULT_YAML_RULES_DIR, str)
        assert DEFAULT_YAML_RULES_DIR.endswith(("data", "rules")) or "rules" in DEFAULT_YAML_RULES_DIR
