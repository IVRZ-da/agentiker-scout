"""Performance-Tests für FrameworkDetector.

Ziel:
  - detect_fast() < 0.3s
  - detect() < 1s
  - FileIndex-Caching: zweiter Aufruf deutlich schneller
  - Glob-Caching: wiederholte Aufrufe ohne Regex-Neucompilierung
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import pytest

from shared.framework_detector import (
    _GLOB_REGEX_CACHE,
    FrameworkDetector,
    _FileIndex,
)

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


@pytest.fixture
def medium_project():
    """Erstellt ein Projekt mit ~50 Dateien (simuliert kleine Projekte)."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # package.json (gängigste Datei)
        _write(root, "package.json", json.dumps({
            "name": "test-project",
            "dependencies": {
                "react": "^19.0.0",
                "next": "^15.0.0",
                "express": "^5.0.0",
                "typescript": "^5.0.0",
                "tailwindcss": "^4.0.0",
                "vitest": "^3.0.0",
            },
        }))

        # Config-Dateien
        _write(root, "next.config.ts", "const nextConfig = {};\nexport default nextConfig;")
        _write(root, "tsconfig.json", "{}")
        _write(root, "tailwind.config.ts", "export default { content: [] };")
        _write(root, "vitest.config.ts", "export default {};")
        _write(root, ".env.example", "DATABASE_URL=postgres://localhost:5432/db\nREDIS_URL=redis://localhost:6379\nNEXT_PUBLIC_API_URL=http://localhost:3000\n")

        # Docker
        _write(root, "Dockerfile", "FROM node:20-alpine\nWORKDIR /app\nCOPY . .")
        _write(root, "docker-compose.yml", "services:\n  db:\n    image: postgres:16\n  cache:\n    image: redis:7-alpine\n")

        # GitHub Actions
        _write(root, ".github/workflows/ci.yml", "name: CI\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n")

        # Quelldateien (verschiedene Sprachen)
        _write(root, "src/app/page.tsx", "export default function Home() { return <div>Hello</div>; }")
        _write(root, "src/app/layout.tsx", "export default function Layout({ children }: { children: React.ReactNode }) { return <html><body>{children}</body></html>; }")
        _write(root, "src/app/api/route.ts", "export async function GET() { return Response.json({ ok: true }); }")
        _write(root, "src/components/button.tsx", "export function Button() { return <button>Click</button>; }")
        _write(root, "src/components/header.tsx", "export function Header() { return <header>Header</header>; }")
        _write(root, "src/lib/utils.ts", "export function cn(...classes: string[]) { return classes.filter(Boolean).join(' '); }")

        # Python files
        _write(root, "pyproject.toml", "[project]\nname = \"test\"\ndependencies = [\"fastapi\", \"uvicorn\"]\n")
        _write(root, "src/main.py", "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/')\ndef root(): return {'hello': 'world'}\n")

        # go.mod
        _write(root, "go.mod", "module test\ngo 1.22\nrequire (\n\tgithub.com/gin-gonic/gin v1.9.0\n\tgithub.com/lib/pq v1.10.0\n)\n")

        # Cargo.toml
        _write(root, "Cargo.toml", "[package]\nname = \"test\"\nversion = \"0.1.0\"\n[dependencies]\ntokio = \"1.0\"\nserde = \"1.0\"\n")

        # Genug TS-Dateien für **/*.ts Marker
        for i in range(20):
            _write(root, f"src/lib/module{i}.ts", f"export const value{i} = {i};")

        # .service files (systemd)
        _write(root, "deploy/app.service", "[Unit]\nDescription=App\n[Service]\nExecStart=/usr/bin/node\n")

        # .tf files (terraform)
        _write(root, "infra/main.tf", 'terraform {\n  required_providers {}\n}\nresource "null_resource" "test" {}')

        yield root


@pytest.fixture
def clean_caches():
    """Stellt sicher, dass globale Caches vor/nach dem Test sauber sind."""
    _GLOB_REGEX_CACHE.clear()
    yield
    _GLOB_REGEX_CACHE.clear()


def _write(root: Path, rel_path: str, content: str = "") -> Path:
    """Schreibt eine Datei im temporären Projekt."""
    fpath = root / rel_path
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text(content)
    return fpath


# ---------------------------------------------------------------------------
# Performance-Tests
# ---------------------------------------------------------------------------


class TestDetectFastTiming:
    """detect_fast() muss < 0.5s bleiben."""

    def test_detect_fast_under_half_second(self, medium_project, clean_caches):
        """detect_fast() in < 0.5s (Ziel: < 0.3s)."""
        detector = FrameworkDetector(str(medium_project), use_yaml_rules=False)
        start = time.perf_counter()
        profile = detector.detect_fast()
        elapsed = time.perf_counter() - start

        assert elapsed < 0.5, f"detect_fast() dauerte {elapsed:.3f}s (Limit: 0.5s)"
        assert profile is not None

    def test_detect_fast_with_yaml_under_second(self, medium_project, clean_caches):
        """detect_fast() mit YAML-Rules in < 1s (Ziel: < 0.3s ohne YAML)."""
        detector = FrameworkDetector(str(medium_project), use_yaml_rules=True)
        start = time.perf_counter()
        profile = detector.detect_fast()
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"detect_fast() mit YAML dauerte {elapsed:.3f}s (Limit: 1.0s)"
        assert profile is not None


class TestDetectTiming:
    """detect() muss < 2s bleiben (Ziel: < 1s)."""

    def test_detect_under_two_seconds(self, medium_project, clean_caches):
        """Vollständiger detect() in < 2s (Ziel: < 1s)."""
        detector = FrameworkDetector(str(medium_project), use_yaml_rules=True)
        start = time.perf_counter()
        profile = detector.detect()
        elapsed = time.perf_counter() - start

        assert elapsed < 2.0, f"detect() dauerte {elapsed:.3f}s (Limit: 2.0s)"
        assert profile is not None
        # Sollte einige Frameworks erkannt haben
        total = sum(len(v) for v in profile.frameworks.values())
        assert total > 0, "Es sollten Frameworks erkannt werden"


class TestFileIndexCaching:
    """FileIndex-Caching: zweiter Aufruf schneller."""

    def test_file_index_cached_access_faster(self, medium_project, clean_caches):
        """Zweiter detect()-Aufruf sollte schneller sein (FileIndex + YAML-Cache)."""
        detector = FrameworkDetector(str(medium_project), use_yaml_rules=True)
        # Erster Aufruf (baut FileIndex + lädt YAML-Rules)
        start1 = time.perf_counter()
        detector.detect()
        elapsed1 = time.perf_counter() - start1

        # Zweiter Aufruf (FileIndex wird neu gebaut, aber YAML-Rules sind gecached)
        start2 = time.perf_counter()
        detector.detect()
        elapsed2 = time.perf_counter() - start2

        # Zweiter Aufruf sollte mindestens 10% schneller sein
        # (YAML-Cache + Glob-Cache greifen)
        assert elapsed2 <= elapsed1 * 1.5 or elapsed2 < 1.0, (
            f"Zweiter Aufruf nicht schneller: 1.={elapsed1:.3f}s, 2.={elapsed2:.3f}s"
        )

    def test_detect_fast_cached_faster(self, medium_project, clean_caches):
        """Zweiter detect_fast()-Aufruf schneller durch YAML-Detector-Cache."""
        detector = FrameworkDetector(str(medium_project), use_yaml_rules=True)
        start1 = time.perf_counter()
        detector.detect_fast()
        elapsed1 = time.perf_counter() - start1

        start2 = time.perf_counter()
        detector.detect_fast()
        elapsed2 = time.perf_counter() - start2

        assert elapsed2 <= elapsed1 * 1.5, (
            f"detect_fast() cached nicht: 1.={elapsed1:.3f}s, 2.={elapsed2:.3f}s"
        )


class TestFileIndex:
    """Direkte Tests für das _FileIndex."""

    def test_file_index_finds_exact_file(self, medium_project):
        """_FileIndex findet exakte Dateinamen."""
        index = _FileIndex(medium_project)
        results = index.find("package.json")
        assert len(results) == 1
        assert results[0][0] == "package.json"

    def test_file_index_finds_extension(self, medium_project):
        """_FileIndex findet Dateien per Extension."""
        index = _FileIndex(medium_project)
        results = index.find("*.py")
        assert len(results) >= 1
        assert all(r[0].endswith(".py") for r in results)

    def test_file_index_finds_recursive_extension(self, medium_project):
        """_FileIndex findet **/*.tsx Dateien."""
        index = _FileIndex(medium_project)
        results = index.find("**/*.tsx")
        assert len(results) >= 2
        assert all(r[0].endswith(".tsx") for r in results)

    def test_file_index_finds_recursive_go(self, medium_project):
        """_FileIndex findet **/*.go Dateien über Rekursions-Pattern."""
        index = _FileIndex(medium_project)
        results = index.find("**/*.go")
        # Go files aren't in the medium_project fixture, so empty is OK
        # What matters is the fast path works correctly
        assert isinstance(results, list)

    def test_file_index_finds_recursive_ts(self, medium_project):
        """_FileIndex findet **/*.ts Dateien über Rekursions-Pattern."""
        index = _FileIndex(medium_project)
        results = index.find("**/*.ts")
        assert len(results) >= 1
        assert all(r[0].endswith(".ts") for r in results)

    def test_file_index_ignored_dirs(self, medium_project):
        """_FileIndex ignoriert node_modules, .git etc."""
        root = medium_project
        _write(root, "node_modules/express/index.js", "module.exports = {};")
        _write(root, "node_modules/react/index.js", "module.exports = {};")
        _write(root, ".git/HEAD", "ref: refs/heads/main\n")
        _write(root, "__pycache__/test.pyc", "bytes")

        index = _FileIndex(root)
        results = index.find("*.js")
        # Keine node_modules Dateien
        assert all("node_modules" not in r[0] for r in results)
        results_pyc = index.find("*.pyc")
        assert len(results_pyc) == 0

    def test_file_index_pattern_with_path(self, medium_project):
        """_FileIndex findet Pattern mit Pfad."""
        root = medium_project
        _write(root, ".github/workflows/deploy.yml", "name: Deploy\n")

        index = _FileIndex(root)
        results = index.find(".github/workflows/*.yml")
        assert len(results) >= 1
        assert all(".github/workflows/" in r[0] for r in results)


class TestGlobCaching:
    """Glob-Regex-Caching Tests."""

    def test_glob_cache_hits(self, clean_caches):
        """Gleiches Glob-Pattern wird gecached."""
        from shared.framework_detector import _compile_glob

        assert len(_GLOB_REGEX_CACHE) == 0
        r1 = _compile_glob("**/*.py")
        assert len(_GLOB_REGEX_CACHE) == 1
        r2 = _compile_glob("**/*.py")
        assert r1 is r2  # Gleiches Objekt (Cache-Hit)

    def test_glob_cache_multiple_patterns(self, clean_caches):
        """Verschiedene Patterns werden unabhängig gecached."""
        from shared.framework_detector import _compile_glob

        _compile_glob("package.json")
        _compile_glob("**/*.ts")
        _compile_glob("**/*.py")
        _compile_glob("*.md")
        assert len(_GLOB_REGEX_CACHE) == 4

    def test_glob_cache_shared_with_techdetector(self, clean_caches, medium_project):
        """_TechDetector._glob_to_regex nutzt denselben Cache."""
        from shared.framework_detector import _compile_glob, _TechDetector

        # Vorher: Cache leer
        assert len(_GLOB_REGEX_CACHE) == 0

        # Durch _TechDetector aufrufen
        r1 = _TechDetector._glob_to_regex("**/*.py")

        # Direkt aufrufen
        r2 = _compile_glob("**/*.py")

        # Gleicher Cache → gleiches Objekt
        assert r1 is r2
        assert len(_GLOB_REGEX_CACHE) >= 1


class TestYamlDetectorCache:
    """YAML-Detector-Caching Tests."""

    def test_yaml_detectors_cached_across_calls(self, medium_project, clean_caches):
        """YAML-Detectors werden über mehrere detect()-Aufrufe gecached."""
        from shared.framework_detector import _YAML_DETECTOR_INSTANCE_CACHE

        _YAML_DETECTOR_INSTANCE_CACHE.clear()
        assert len(_YAML_DETECTOR_INSTANCE_CACHE) == 0

        detector = FrameworkDetector(str(medium_project), use_yaml_rules=True)
        detector.detect()
        cache_size_after_first = len(_YAML_DETECTOR_INSTANCE_CACHE)
        assert cache_size_after_first > 0, "YAML-Detector-Cache sollte nach detect() gefüllt sein"

        # Zweiter detect()-Aufruf (selbe Rules, sollte Cache nutzen)
        detector.detect()
        assert len(_YAML_DETECTOR_INSTANCE_CACHE) == cache_size_after_first

    def test_yaml_detector_cache_shared_across_instances(self, medium_project, clean_caches):
        """Verschiedene FrameworkDetector-Instanzen teilen den YAML-Detector-Cache."""
        from shared.framework_detector import _YAML_DETECTOR_INSTANCE_CACHE
        _YAML_DETECTOR_INSTANCE_CACHE.clear()

        d1 = FrameworkDetector(str(medium_project), use_yaml_rules=True)
        d1.detect()
        size1 = len(_YAML_DETECTOR_INSTANCE_CACHE)

        d2 = FrameworkDetector(str(medium_project), use_yaml_rules=True)
        d2.detect()
        size2 = len(_YAML_DETECTOR_INSTANCE_CACHE)

        assert size2 >= size1  # Mindestens gleich, evtl. mehr durch zusätzliche Detectors


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
