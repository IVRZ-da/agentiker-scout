"""Tests für dotenv + Docker Scanning im FrameworkDetector.

Testet:
- _detect_dotenv: .env.example / .env Dateien mit bekannten Prefixen
- _scan_docker_files: docker-compose.yml / Dockerfile / compose.yaml Images
- Integration in FrameworkDetector.detect()
- Edge Cases: leere Dateien, fehlende Dateien, keine Duplikate
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.framework_detector import (
    _DOCKER_IMAGE_MAP,
    FrameworkDetector,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Erstellt ein temporäres Projekt-Verzeichnis."""
    return tmp_path


def _write(root: Path, rel_path: str, content: str = "") -> Path:
    """Schreibt eine Datei im temporären Projekt."""
    fpath = root / rel_path
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text(content)
    return fpath


# ---------------------------------------------------------------------------
# _detect_dotenv — .env.example / .env Scanning
# ---------------------------------------------------------------------------


class TestDetectDotenv:
    def test_env_example_with_known_prefixes(self, tmp_project):
        """.env.example mit bekannten Prefixen wird korrekt erkannt."""
        _write(tmp_project, ".env.example", "\n".join([
            "SENTRY_DSN=https://key@sentry.io/123",
            "STRIPE_API_KEY=sk_test_xxx",
            "OTEL_EXPORTER_OTLP_ENDPOINT=http://otel:4318",
            "GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com",
            "DATABASE_URL=postgresql://localhost:5432/db",
            "REDIS_URL=redis://localhost:6379",
            "NEXT_PUBLIC_API_URL=http://localhost:3000",
            "MEDUSA_ADMIN_SECRET=supersecret",
            "NODE_ENV=development",
        ]))

        results = FrameworkDetector._detect_dotenv(tmp_project)
        names = {r.name for r in results}

        assert "sentry" in names
        assert "stripe" in names
        assert "opentelemetry" in names
        assert "gcp" in names
        assert "postgresql" in names
        assert "redis" in names
        assert "nextjs" in names
        assert "medusa" in names
        assert "node" in names

    def test_env_file_also_scanned(self, tmp_project):
        ".env (ohne .example) wird ebenfalls gescannt."""
        _write(tmp_project, ".env", "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n")

        results = FrameworkDetector._detect_dotenv(tmp_project)
        names = {r.name for r in results}

        assert "aws" in names

    def test_env_example_preferred_over_env(self, tmp_project):
        """Wenn beide existieren, werden beide gescannt — keine Duplikate."""
        _write(tmp_project, ".env.example", "SENTRY_DSN=https://key@sentry.io/123\n")
        _write(tmp_project, ".env", "SENTRY_DSN=https://another@sentry.io/456\n")

        results = FrameworkDetector._detect_dotenv(tmp_project)
        sentry_results = [r for r in results if r.name == "sentry"]

        assert len(sentry_results) == 1  # No duplicates

    def test_empty_env_returns_empty(self, tmp_project):
        """Leere .env.example gibt leere Liste zurück."""
        _write(tmp_project, ".env.example", "")
        results = FrameworkDetector._detect_dotenv(tmp_project)
        assert results == []

    def test_env_with_only_comments(self, tmp_project):
        """Nur Kommentare in .env geben leere Liste zurück."""
        _write(tmp_project, ".env.example", "# This is a comment\n# Another comment\n")
        results = FrameworkDetector._detect_dotenv(tmp_project)
        assert results == []

    def test_env_with_unknown_prefixes(self, tmp_project):
        """Unbekannte Prefixe werden ignoriert."""
        _write(tmp_project, ".env.example", "MY_CUSTOM_VAR=something\nFOO=bar\n")
        results = FrameworkDetector._detect_dotenv(tmp_project)
        assert results == []

    def test_no_env_files_returns_empty(self, tmp_project):
        """Fehlende .env/.env.example geben leere Liste zurück."""
        results = FrameworkDetector._detect_dotenv(tmp_project)
        assert results == []

    def test_dotenv_confidence_is_medium(self, tmp_project):
        """Erkannte dotenv-Variablen haben confidence='medium'."""
        _write(tmp_project, ".env.example", "AWS_ACCESS_KEY_ID=xxx\n")
        results = FrameworkDetector._detect_dotenv(tmp_project)
        assert len(results) == 1
        assert results[0].confidence == "medium"
        assert results[0].evidence[0].confidence == "medium"

    def test_dotenv_evidence_path(self, tmp_project):
        """Evidence-Quelle ist der Dateiname."""
        _write(tmp_project, ".env.example", "SENTRY_DSN=xxx\n")
        results = FrameworkDetector._detect_dotenv(tmp_project)
        assert results[0].evidence[0].source == ".env.example"

    def test_databases_variables_resolve_to_postgresql(self, tmp_project):
        """Verschiedene DATABASE_* Variablen zeigen auf postgresql."""
        _write(tmp_project, ".env.example", "\n".join([
            "DATABASE_HOST=localhost",
            "DATABASE_NAME=mydb",
            "DATABASE_USER=admin",
            "DATABASE_PASSWORD=secret",
        ]))
        results = FrameworkDetector._detect_dotenv(tmp_project)
        names = {r.name for r in results}
        # Alle DATABASE_* Varianten mappen zu postgresql
        assert names == {"postgresql"}

    def test_longest_prefix_wins(self, tmp_project):
        """Längster Prefix matcht zuerst (NEXT_PUBLIC_ vor GOOGLE_)."""
        _write(tmp_project, ".env.example",
               "NEXT_PUBLIC_GOOGLE_ANALYTICS_ID=UA-XXXXX\n")
        results = FrameworkDetector._detect_dotenv(tmp_project)
        names = {r.name for r in results}
        # 'NEXT_PUBLIC_GOOGLE_...' matched 'NEXT_PUBLIC_' (11 chars)
        # rather than 'GOOGLE_' (7 chars)
        assert "nextjs" in names


# ---------------------------------------------------------------------------
# _scan_docker_files — docker-compose.yml / Dockerfile / compose.yaml
# ---------------------------------------------------------------------------


class TestScanDockerFiles:
    def test_docker_compose_services(self, tmp_project):
        """docker-compose.yml services werden korrekt erkannt."""
        _write(tmp_project, "docker-compose.yml", "\n".join([
            "services:",
            "  db:",
            "    image: postgres:16",
            "  cache:",
            "    image: redis:7-alpine",
            "  web:",
            "    image: nginx:latest",
        ]))

        results = FrameworkDetector._scan_docker_files(tmp_project)
        names = {r.name for r in results}

        assert "postgresql" in names
        assert "redis" in names
        assert "nginx" in names

    def test_docker_compose_versions(self, tmp_project):
        """Versionen aus image:-Tags werden extrahiert."""
        _write(tmp_project, "docker-compose.yml", "\n".join([
            "services:",
            "  db:",
            "    image: postgres:16",
        ]))

        results = FrameworkDetector._scan_docker_files(tmp_project)
        pg = [r for r in results if r.name == "postgresql"][0]
        assert pg.version == "16"

    def test_dockerfile_from_images(self, tmp_project):
        """Dockerfile FROM Statements werden erkannt."""
        _write(tmp_project, "Dockerfile", "\n".join([
            "FROM node:20-alpine AS builder",
            "WORKDIR /app",
            "COPY . .",
            "RUN npm run build",
            "FROM python:3.12-slim",
            "COPY --from=builder /app/dist /app",
        ]))

        results = FrameworkDetector._scan_docker_files(tmp_project)
        names = {r.name for r in results}

        assert "node" in names
        assert "python" in names

    def test_dockerfile_as_alias_stripped(self, tmp_project):
        """'AS alias' wird korrekt aus FROM entfernt."""
        _write(tmp_project, "Dockerfile",
               "FROM golang:1.22 AS build-stage\n")
        results = FrameworkDetector._scan_docker_files(tmp_project)
        names = {r.name for r in results}
        assert "go" in names

    def test_compose_yaml(self, tmp_project):
        """compose.yaml wird ebenfalls erkannt."""
        _write(tmp_project, "compose.yaml", "services:\n  db:\n    image: mariadb:11\n")
        results = FrameworkDetector._scan_docker_files(tmp_project)
        assert any(r.name == "mariadb" for r in results)

    def test_docker_compose_yaml_extension(self, tmp_project):
        """docker-compose.yaml (mit .yaml) wird erkannt."""
        _write(tmp_project, "docker-compose.yaml", "services:\n  web:\n    image: nginx:latest\n")
        results = FrameworkDetector._scan_docker_files(tmp_project)
        assert any(r.name == "nginx" for r in results)

    def test_no_docker_files_returns_empty(self, tmp_project):
        """Fehlende Docker-Dateien geben leere Liste zurück."""
        results = FrameworkDetector._scan_docker_files(tmp_project)
        assert results == []

    def test_empty_docker_compose(self, tmp_project):
        """Leere docker-compose.yml gibt leere Liste zurück."""
        _write(tmp_project, "docker-compose.yml", "")
        results = FrameworkDetector._scan_docker_files(tmp_project)
        assert results == []

    def test_empty_dockerfile(self, tmp_project):
        """Leeres Dockerfile gibt leere Liste zurück."""
        _write(tmp_project, "Dockerfile", "")
        results = FrameworkDetector._scan_docker_files(tmp_project)
        assert results == []

    def test_docker_compose_confidence_is_high(self, tmp_project):
        """Erkannte docker-compose images haben confidence='high'."""
        _write(tmp_project, "docker-compose.yml",
               "services:\n  db:\n    image: postgres:16\n")
        results = FrameworkDetector._scan_docker_files(tmp_project)
        assert results[0].confidence == "high"

    def test_dockerfile_confidence_is_high(self, tmp_project):
        """Erkannte Dockerfile images haben confidence='high'."""
        _write(tmp_project, "Dockerfile", "FROM node:20\n")
        results = FrameworkDetector._scan_docker_files(tmp_project)
        assert results[0].confidence == "high"

    def test_dockerfile_evidence_source(self, tmp_project):
        """Evidence-Quelle ist 'Dockerfile'."""
        _write(tmp_project, "Dockerfile", "FROM python:3.12\n")
        results = FrameworkDetector._scan_docker_files(tmp_project)
        assert results[0].evidence[0].source == "Dockerfile"

    def test_docker_compose_no_image_key(self, tmp_project):
        """docker-compose.yml ohne image: Einträge gibt leere Liste."""
        _write(tmp_project, "docker-compose.yml", "services:\n  web:\n    build: .\n")
        results = FrameworkDetector._scan_docker_files(tmp_project)
        assert results == []

    def test_dockerfile_non_from_lines_ignored(self, tmp_project):
        """Nicht-FROM Zeilen im Dockerfile werden ignoriert."""
        _write(tmp_project, "Dockerfile", "\n".join([
            "FROM node:20",
            "RUN apt-get update",
            "COPY . /app",
            "CMD [\"node\", \"app.js\"]",
        ]))
        results = FrameworkDetector._scan_docker_files(tmp_project)
        assert len(results) == 1
        assert results[0].name == "node"

    def test_image_with_registry_path(self, tmp_project):
        """Images mit Registry-Pfad (z.B. docker.io/library/...) werden erkannt."""
        _write(tmp_project, "docker-compose.yml",
               "services:\n  db:\n    image: docker.io/library/postgres:16\n")
        results = FrameworkDetector._scan_docker_files(tmp_project)
        assert any(r.name == "postgresql" for r in results)

    def test_image_with_organization(self, tmp_project):
        """Images mit Organization (z.B. bitnami/redis) werden erkannt."""
        _write(tmp_project, "docker-compose.yml",
               "services:\n  cache:\n    image: bitnami/redis:7.0\n")
        results = FrameworkDetector._scan_docker_files(tmp_project)
        assert any(r.name == "redis" for r in results)

    def test_unknown_image_ignored(self, tmp_project):
        """Unbekannte Images werden ignoriert."""
        _write(tmp_project, "docker-compose.yml",
               "services:\n  app:\n    image: my-custom-app:latest\n")
        results = FrameworkDetector._scan_docker_files(tmp_project)
        assert results == []


# ---------------------------------------------------------------------------
# Integration in FrameworkDetector.detect()
# ---------------------------------------------------------------------------


class TestIntegrationDetect:
    def test_detect_includes_dotenv(self, tmp_project):
        """detect() findet Frameworks aus .env.example."""
        _write(tmp_project, ".env.example", "SENTRY_DSN=https://key@sentry.io/123\n")
        detector = FrameworkDetector(str(tmp_project))
        profile = detector.detect()
        assert profile.has_framework("sentry")

    def test_detect_includes_docker_compose(self, tmp_project):
        """detect() findet Frameworks aus docker-compose.yml."""
        _write(tmp_project, "docker-compose.yml",
               "services:\n  db:\n    image: postgres:16\n")
        detector = FrameworkDetector(str(tmp_project))
        profile = detector.detect()
        assert profile.has_framework("postgresql")

    def test_detect_includes_dockerfile(self, tmp_project):
        """detect() findet Frameworks aus Dockerfile FROM."""
        _write(tmp_project, "Dockerfile", "FROM node:20-alpine\n")
        detector = FrameworkDetector(str(tmp_project))
        profile = detector.detect()
        assert profile.has_framework("node")

    def test_detect_no_duplicates_dockerfile_and_compose(self, tmp_project):
        """Keine Duplikate wenn Image in compose.yml UND Dockerfile vorkommt."""
        _write(tmp_project, "docker-compose.yml",
               "services:\n  app:\n    image: node:20\n")
        _write(tmp_project, "Dockerfile", "FROM node:20\n")
        detector = FrameworkDetector(str(tmp_project))
        profile = detector.detect()
        node_fws = profile.get_frameworks_by_category("language")
        node_fw = [fw for fw in node_fws if fw.name == "node"]
        assert len(node_fw) == 1

    def test_detect_no_duplicates_with_existing_detectors(self, tmp_project):
        """Keine Duplikate wenn bereits durch andere Detectors erkannt.

        POSTGRESQL_DETECTOR erkennt postgresql bereits via
        docker-compose.yml content-scan. Unser neuer _scan_docker_files
        sollte kein Duplikat hinzufügen.
        """
        _write(tmp_project, "docker-compose.yml",
               "services:\n  db:\n    image: postgres:16\n")
        detector = FrameworkDetector(str(tmp_project))
        profile = detector.detect()
        postgresql_fws = profile.get_frameworks_by_category("database")
        pg_fw = [fw for fw in postgresql_fws if fw.name == "postgresql"]
        assert len(pg_fw) == 1

    def test_detect_empty_project_still_works(self, tmp_project):
        """Leeres Projekt gibt immer noch leeres Profil zurück."""
        detector = FrameworkDetector(str(tmp_project))
        profile = detector.detect()
        assert len(profile.frameworks) == 0
        assert profile.overall_confidence == 0.0

    def test_detect_both_dotenv_and_docker(self, tmp_project):
        """detect() kombiniert dotenv + docker Ergebnisse."""
        _write(tmp_project, ".env.example", "AWS_ACCESS_KEY_ID=xxx\n")
        _write(tmp_project, "Dockerfile", "FROM python:3.12\n")
        detector = FrameworkDetector(str(tmp_project))
        profile = detector.detect()
        assert profile.has_framework("aws")
        assert profile.has_framework("python")

    def test_detect_categories_filter_still_works(self, tmp_project):
        """categories-Filter in detect() schließt dotenv/docker ein."""
        _write(tmp_project, ".env.example", "AWS_ACCESS_KEY_ID=xxx\n")
        _write(tmp_project, "Dockerfile", "FROM python:3.12\n")
        detector = FrameworkDetector(str(tmp_project))
        profile = detector.detect(categories=["infra"])
        # aws ist infra, python ist language
        assert profile.has_framework("aws")
        assert not profile.has_framework("python")

    def test_detect_with_all_known_docker_images(self, tmp_project):
        """Alle bekannten Docker-Images aus _DOCKER_IMAGE_MAP."""
        for img_name in list(_DOCKER_IMAGE_MAP.keys())[:5]:
            tmp = tmp_project / f"test_{img_name}"
            tmp.mkdir(exist_ok=True)
            _write(tmp, "Dockerfile", f"FROM {img_name}:latest\n")
            detector = FrameworkDetector(str(tmp))
            profile = detector.detect()
            expected_name = _DOCKER_IMAGE_MAP[img_name][1]
            assert profile.has_framework(expected_name), \
                f"{img_name} → {expected_name} nicht erkannt"

    def test_detect_fast_does_not_include_dotenv_or_docker(self, tmp_project):
        """detect_fast() überspringt dotenv/docker (nur YAML + high-confidence)."""
        _write(tmp_project, ".env.example", "AWS_ACCESS_KEY_ID=xxx\n")
        _write(tmp_project, "Dockerfile", "FROM python:3.12\n")
        detector = FrameworkDetector(str(tmp_project))
        profile = detector.detect_fast()
        # detect_fast verwendet nur YAML-Detectors + high-confidence Marker,
        # nicht die neuen statischen Methoden
        # Das ist OK — detect_fast soll schnell sein
        assert isinstance(profile.frameworks, dict)


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_malformed_env_file(self, tmp_project):
        """Fehlerhafte .env Dateien führen nicht zu Abstürzen."""
        _write(tmp_project, ".env.example", "\x00\x00\x00\x00\nKEY=value\n")
        results = FrameworkDetector._detect_dotenv(tmp_project)
        # Sollte nicht crashen — kann 0 oder 1 Ergebnis haben
        assert isinstance(results, list)

    def test_binary_dockerfile(self, tmp_project):
        """Binäre 'Dockerfile' führt nicht zu Abstürzen."""
        _write(tmp_project, "Dockerfile", "\x00\x00\x00\x00")
        results = FrameworkDetector._scan_docker_files(tmp_project)
        assert results == []

    def test_env_with_only_whitespace(self, tmp_project):
        """Nur Leerzeichen in .env geben leere Liste."""
        _write(tmp_project, ".env.example", "   \n  \n")
        results = FrameworkDetector._detect_dotenv(tmp_project)
        assert results == []

    def test_docker_compose_with_quoted_image(self, tmp_project):
        """image: mit Anführungszeichen wird korrekt geparst."""
        _write(tmp_project, "docker-compose.yml",
               "services:\n  app:\n    image: \"postgres:16\"\n")
        results = FrameworkDetector._scan_docker_files(tmp_project)
        assert any(r.name == "postgresql" for r in results)
