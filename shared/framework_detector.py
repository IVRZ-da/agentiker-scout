"""Framework Detection Engine — Automatische Tech-Stack-Erkennung.

Erkennt den gesamten Technologie-Stack eines Projekts durch Analyse von
package.json, go.mod, Cargo.toml, requirements.txt, Config-Dateien,
Ordnerstruktur und CI/CD-Konfiguration. Inspiriert von specfy/stack-analyser.

Usage:
    detector = FrameworkDetector("/path/to/project")
    result = detector.detect()
    print(result.frameworks)
    print(result.confidence)
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("scout.framework_detector")

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass
class FrameworkEvidence:
    """Einzelner Evidenzpunkt für ein erkanntes Framework."""

    source: str  # Dateipfad relativ zum Projekt-Root
    pattern: str  # Was wurde gefunden (z.B. dependency name, config key)
    confidence: str = "high"  # high | medium | low
    version: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "pattern": self.pattern,
            "confidence": self.confidence,
            "version": self.version,
        }


@dataclass
class DetectedFramework:
    """Ein erkanntes Framework/Tech mit Metadaten."""

    name: str
    category: str  # backend | frontend | ui_library | database | language | testing | infra | ci | package_manager
    confidence: str = "high"  # high | medium | low
    version: Optional[str] = None
    evidence: List[FrameworkEvidence] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "confidence": self.confidence,
            "version": self.version,
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass
class FrameworkProfile:
    """Vollständiges Framework-Profil eines Projekts."""

    project_root: str
    frameworks: Dict[str, List[DetectedFramework]] = field(default_factory=dict)
    # categories: backend, frontend, ui_library, database, language, testing, infra, ci, package_manager
    overall_confidence: float = 0.0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_root": self.project_root,
            "frameworks": {
                cat: [fw.to_dict() for fw in fw_list]
                for cat, fw_list in self.frameworks.items()
            },
            "overall_confidence": self.overall_confidence,
            "errors": self.errors,
        }

    def has_framework(self, name: str) -> bool:
        """Prüft ob ein bestimmtes Framework erkannt wurde."""
        for fw_list in self.frameworks.values():
            for fw in fw_list:
                if fw.name == name:
                    return True
        return False

    def get_framework(self, name: str) -> Optional[DetectedFramework]:
        """Holt ein Framework-Detail."""
        for fw_list in self.frameworks.values():
            for fw in fw_list:
                if fw.name == name:
                    return fw
        return None

    def get_frameworks_by_category(self, category: str) -> List[DetectedFramework]:
        """Holt alle Frameworks einer Kategorie."""
        return self.frameworks.get(category, [])


# ---------------------------------------------------------------------------
# Detector Registry — Jeder Detector prüft eine bestimmte Tech
# ---------------------------------------------------------------------------


class _TechDetector:
    """Basis-Klasse für einen Technologie-Detector.

    Jeder Detector scannt bestimmte Dateien/Patterns und gibt
    einen DetectedFramework zurück wenn er fündig wird.
    """

    name: str = ""
    category: str = ""
    markers: List[Tuple[str, str, str]] = []
    # (file_path_glob, search_pattern, confidence) — (glob, regex/string, "high"|"medium"|"low")

    def detect(self, root: Path) -> Optional[DetectedFramework]:
        """Führt die Detektion aus. Gibt None zurück wenn nicht gefunden."""
        evidence: List[FrameworkEvidence] = []
        version: Optional[str] = None

        for file_glob, search_pat, conf in self.markers:
            # Dateien gezielt finden statt rglob("*") — viel schneller
            matched_files = self._find_files(root, file_glob)
            for rel_path, fpath in matched_files:
                if self._is_ignored(rel_path):
                    continue
                try:
                    content = fpath.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                if not search_pat:
                    # Nur Existenz der Datei prüfen
                    evidence.append(FrameworkEvidence(
                        source=rel_path, pattern="file exists", confidence=conf
                    ))
                    continue
                if isinstance(search_pat, str):
                    if search_pat in content:
                        evidence.append(FrameworkEvidence(
                            source=rel_path, pattern=search_pat, confidence=conf
                        ))
                        v = self._extract_version(content, search_pat)
                        if v:
                            version = v
                else:
                    if search_pat.search(content):
                        evidence.append(FrameworkEvidence(
                            source=rel_path,
                            pattern=search_pat.pattern[:60],
                            confidence=conf,
                        ))
        if not evidence:
            return None

        # Confidence aus der höchsten Evidenz
        conf_levels = {"high": 0, "medium": 1, "low": 2}
        best_conf = min(conf_levels.get(e.confidence, 2) for e in evidence)
        conf_map = {0: "high", 1: "medium", 2: "low"}

        return DetectedFramework(
            name=self.name,
            category=self.category,
            confidence=conf_map[best_conf],
            version=version,
            evidence=evidence,
        )

    def _find_files(self, root: Path, file_glob: str) -> List[Tuple[str, Path]]:
        """Findet Dateien die zu einem Glob passen — schnell und ohne node_modules."""
        results: List[Tuple[str, Path]] = []
        pattern_re = self._glob_to_regex(file_glob)

        # Für feste Dateinamen (kein wildcard): direkter exist-Check
        if "*" not in file_glob:
            fpath = root / file_glob
            if fpath.exists() and fpath.is_file():
                results.append((file_glob, fpath))
            return results

        # Für Pattern mit Pfad-Tiefe: rglob mit depth-Limit
        # Extrahiere den Dateinamen-Teil für schnelle Vorauswahl
        parts = file_glob.split("/")
        leaf_part = parts[-1] if parts else file_glob

        # Entscheide Suchstrategie basierend auf Pattern
        if leaf_part.startswith("*"):
            # Pattern wie **/*.ts → alle .ts Dateien
            ext = leaf_part.split(".")[-1] if "." in leaf_part else ""
            search_pattern = f"*.{ext}" if ext else "*"
        else:
            search_pattern = leaf_part

        scan_depth = 3 if file_glob.startswith("**/") or "**/" in file_glob else 5
        scanned = 0

        for fpath in root.rglob(search_pattern):
            scanned += 1
            if scanned > 200:  # Safety Limit
                break
            if fpath.is_dir() or fpath.is_symlink():
                continue
            rel = str(fpath.relative_to(root))
            if self._is_ignored(rel):
                continue
            # Tiefe prüfen
            depth = rel.count(os.sep)
            if depth > scan_depth:
                continue
            if pattern_re.match(rel):
                results.append((rel, fpath))

        return results

    def _glob_to_regex(self, glob_pat: str) -> re.Pattern:
        """Wandelt einfache File-Globs in Regex um.

        Unterstützt:
          - **/ für rekursive Suche
          - * für einzelne Segmente
          - ? für single chars
          - {a,b} für Alternativen
        """
        # **/ durch rekursiven Pfad-Matcher ersetzen
        parts = glob_pat.split("**/")
        if len(parts) > 1:
            # **/ → matcht 0 oder mehr Verzeichnisebenen
            regex_parts = []
            for i, part in enumerate(parts):
                if not part:
                    continue
                escaped = re.escape(part)
                escaped = escaped.replace(r"\*", "[^/]*").replace(r"\?", ".")
                regex_parts.append(escaped)
            # Entweder "nichts" (0 Ebenen) oder "irgendwas/"
            prefix = "(.*/)?" if glob_pat.startswith("**/") else ""
            suffix = "/?".join(regex_parts)
            regex_str = "^" + prefix + suffix + "$"
        else:
            parts = glob_pat.split("*")
            regex_str = "^" + re.escape(parts[0]) if parts else "^"
            for p in parts[1:]:
                regex_str += "[^/]*" + re.escape(p)
            regex_str += "$"

        return re.compile(regex_str)

    def _is_ignored(self, rel_path: str) -> bool:
        """Prüft ob eine Datei ignoriert werden soll."""
        ignore_dirs = {
            "node_modules", ".git", "__pycache__", ".venv", "venv",
            ".next", "dist", "build", ".medusa", ".cache", "target",
        }
        parts = rel_path.split(os.sep)
        return any(part in ignore_dirs for part in parts)

    def _extract_version(self, content: str, marker: str) -> Optional[str]:
        """Extrahiert eine Version aus package.json oder ähnlichen Dateien."""
        if '"version"' in content[:200] and '"name"' in content[:200]:
            try:
                data = json.loads(content)
                return data.get("version")
            except (json.JSONDecodeError, KeyError):
                pass
        return None


# ---------------------------------------------------------------------------
# Konkrete Detector-Definitionen
# ---------------------------------------------------------------------------

# ── Backend Frameworks ──────────────────────────────────────────────

MEDUSA_V2_DETECTOR = type("_MedusaV2Detector", (_TechDetector,), {
    "name": "medusa-v2",
    "category": "backend",
    "markers": [
        ("medusa-config.ts", "defineConfig", "high"),
        ("medusa-config.js", "defineConfig", "high"),
        ("medusa-config.ts", "modules", "high"),
        ("package.json", '"@medusajs/medusa"', "high"),
        ("src/modules/*/index.ts", "export default Module", "medium"),
        ("src/admin/routes/**/page.tsx", "@medusajs/ui", "medium"),
    ],
})()

NEXTJS_DETECTOR = type("_NextJSDetector", (_TechDetector,), {
    "name": "nextjs",
    "category": "frontend",
    "markers": [
        ("next.config.ts", "", "high"),
        ("next.config.mjs", "", "high"),
        ("next.config.js", "", "high"),
        ("package.json", '"next"', "high"),
        ("app/**/page.tsx", "export default", "medium"),
        ("src/app/**/page.tsx", "export default", "medium"),
    ],
})()

EXPRESS_DETECTOR = type("_ExpressDetector", (_TechDetector,), {
    "name": "express",
    "category": "backend",
    "markers": [
        ("package.json", '"express"', "high"),
    ],
})()

FASTIFY_DETECTOR = type("_FastifyDetector", (_TechDetector,), {
    "name": "fastify",
    "category": "backend",
    "markers": [
        ("package.json", '"fastify"', "high"),
    ],
})()

GO_DETECTOR = type("_GoDetector", (_TechDetector,), {
    "name": "go",
    "category": "language",
    "markers": [
        ("go.mod", "module ", "high"),
    ],
})()

GO_CHI_DETECTOR = type("_GoChiDetector", (_TechDetector,), {
    "name": "go-chi",
    "category": "backend",
    "markers": [
        ("go.mod", "chi", "medium"),
        ("**/*.go", "chi.NewRouter", "high"),
        ("**/*.go", "chi.NewMux", "high"),
    ],
})()

GO_FIBER_DETECTOR = type("_GoFiberDetector", (_TechDetector,), {
    "name": "go-fiber",
    "category": "backend",
    "markers": [
        ("go.mod", "fiber", "medium"),
        ("**/*.go", "fiber.New", "high"),
    ],
})()

FASTAPI_DETECTOR = type("_FastAPIDetector", (_TechDetector,), {
    "name": "fastapi",
    "category": "backend",
    "markers": [
        ("requirements.txt", "fastapi", "high"),
        ("pyproject.toml", '"fastapi"', "high"),
        ("**/*.py", "from fastapi import", "high"),
    ],
})()

DJANGO_DETECTOR = type("_DjangoDetector", (_TechDetector,), {
    "name": "django",
    "category": "backend",
    "markers": [
        ("requirements.txt", "django", "high"),
        ("manage.py", "django", "high"),
        ("**/settings.py", "django", "medium"),
    ],
})()

# ── Frontend Frameworks ────────────────────────────────────────────

REACT_DETECTOR = type("_ReactDetector", (_TechDetector,), {
    "name": "react",
    "category": "frontend",
    "markers": [
        ("package.json", '"react"', "high"),
        ("**/*.tsx", "from 'react'", "medium"),
        ("**/*.tsx", 'from "react"', "medium"),
    ],
})()

VUE_DETECTOR = type("_VueDetector", (_TechDetector,), {
    "name": "vue",
    "category": "frontend",
    "markers": [
        ("package.json", '"vue"', "high"),
        ("**/*.vue", "<template>", "medium"),
    ],
})()

SVELTE_DETECTOR = type("_SvelteDetector", (_TechDetector,), {
    "name": "svelte",
    "category": "frontend",
    "markers": [
        ("package.json", '"svelte"', "high"),
        ("**/*.svelte", "<script", "medium"),
    ],
})()

VITE_DETECTOR = type("_ViteDetector", (_TechDetector,), {
    "name": "vite",
    "category": "frontend",
    "markers": [
        ("vite.config.ts", "", "high"),
        ("vite.config.js", "", "high"),
        ("package.json", '"vite"', "high"),
    ],
})()

TAILWIND_DETECTOR = type("_TailwindDetector", (_TechDetector,), {
    "name": "tailwindcss",
    "category": "ui_library",
    "markers": [
        ("tailwind.config.ts", "", "high"),
        ("tailwind.config.js", "", "high"),
        ("package.json", '"tailwindcss"', "high"),
        ("**/*.css", "@tailwind", "medium"),
    ],
})()

SHADCN_DETECTOR = type("_ShadcnDetector", (_TechDetector,), {
    "name": "shadcn-ui",
    "category": "ui_library",
    "markers": [
        ("components.json", "", "high"),
        ("package.json", '"shadcn-ui"', "high"),
        ("package.json", '"@radix-ui/react-"', "medium"),
    ],
})()

MEDUSAJ_UI_DETECTOR = type("_MedusaJSUIDetector", (_TechDetector,), {
    "name": "@medusajs/ui",
    "category": "ui_library",
    "markers": [
        ("package.json", '"@medusajs/ui"', "high"),
        ("**/admin/**/*.tsx", "@medusajs/ui", "medium"),
    ],
})()

# ── Datenbanken ────────────────────────────────────────────────────

POSTGRESQL_DETECTOR = type("_PostgreSQLDetector", (_TechDetector,), {
    "name": "postgresql",
    "category": "database",
    "markers": [
        ("package.json", '"pg"', "high"),
        ("package.json", '"postgres"', "medium"),
        ("**/*.ts", "createConnection.*postgres", "medium"),
        ("docker-compose.yml", "postgres:", "medium"),
        ("docker-compose.yaml", "postgres:", "medium"),
    ],
})()

REDIS_DETECTOR = type("_RedisDetector", (_TechDetector,), {
    "name": "redis",
    "category": "database",
    "markers": [
        ("package.json", '"redis"', "high"),
        ("package.json", '"ioredis"', "high"),
        ("docker-compose.yml", "redis:", "medium"),
        ("docker-compose.yaml", "redis:", "medium"),
    ],
})()

# ── Sprachen ───────────────────────────────────────────────────────

TYPESCRIPT_DETECTOR = type("_TypeScriptDetector", (_TechDetector,), {
    "name": "typescript",
    "category": "language",
    "markers": [
        ("tsconfig.json", "", "high"),
        ("package.json", '"typescript"', "high"),
        ("**/*.ts", "", "medium"),
    ],
})()

JAVASCRIPT_DETECTOR = type("_JavaScriptDetector", (_TechDetector,), {
    "name": "javascript",
    "category": "language",
    "markers": [
        ("package.json", "", "high"),
    ],
})()

PYTHON_DETECTOR = type("_PythonDetector", (_TechDetector,), {
    "name": "python",
    "category": "language",
    "markers": [
        ("**/*.py", "", "medium"),
        ("requirements.txt", "", "medium"),
        ("pyproject.toml", "", "medium"),
        ("setup.py", "", "medium"),
    ],
})()

RUST_DETECTOR = type("_RustDetector", (_TechDetector,), {
    "name": "rust",
    "category": "language",
    "markers": [
        ("Cargo.toml", "", "high"),
        ("**/*.rs", "", "medium"),
    ],
})()

# ── Testing ────────────────────────────────────────────────────────

JEST_DETECTOR = type("_JestDetector", (_TechDetector,), {
    "name": "jest",
    "category": "testing",
    "markers": [
        ("package.json", '"jest"', "high"),
        ("jest.config.ts", "", "high"),
        ("jest.config.js", "", "high"),
    ],
})()

VITEST_DETECTOR = type("_VitestDetector", (_TechDetector,), {
    "name": "vitest",
    "category": "testing",
    "markers": [
        ("package.json", '"vitest"', "high"),
        ("vitest.config.ts", "", "high"),
    ],
})()

PLAYWRIGHT_DETECTOR = type("_PlaywrightDetector", (_TechDetector,), {
    "name": "playwright",
    "category": "testing",
    "markers": [
        ("package.json", '@playwright', "high"),
        ("playwright.config.ts", "", "high"),
        ("**/*.spec.ts", "playwright", "medium"),
    ],
})()

# ── Infrastructure ─────────────────────────────────────────────────

DOCKER_DETECTOR = type("_DockerDetector", (_TechDetector,), {
    "name": "docker",
    "category": "infra",
    "markers": [
        ("Dockerfile", "FROM", "high"),
        ("docker-compose.yml", "", "high"),
        ("docker-compose.yaml", "", "high"),
        (".dockerignore", "", "medium"),
    ],
})()

SYSTEMD_DETECTOR = type("_SystemdDetector", (_TechDetector,), {
    "name": "systemd",
    "category": "infra",
    "markers": [
        ("**/*.service", "[Unit]", "high"),
        ("**/*.service", "[Service]", "high"),
    ],
})()

NGINX_DETECTOR = type("_NginxDetector", (_TechDetector,), {
    "name": "nginx",
    "category": "infra",
    "markers": [
        ("**/nginx.conf", "server", "high"),
        ("**/nginx/*.conf", "server", "high"),
        (".nginx.conf", "", "medium"),
    ],
})()

# ── CI / CD ────────────────────────────────────────────────────────

GITHUB_ACTIONS_DETECTOR = type("_GitHubActionsDetector", (_TechDetector,), {
    "name": "github-actions",
    "category": "ci",
    "markers": [
        (".github/workflows/*.yml", "on:", "high"),
        (".github/workflows/*.yaml", "on:", "high"),
    ],
})()

FORGEJO_ACTIONS_DETECTOR = type("_ForgejoActionsDetector", (_TechDetector,), {
    "name": "forgejo-actions",
    "category": "ci",
    "markers": [
        (".forgejo/workflows/*.yml", "on:", "high"),
        (".forgejo/workflows/*.yaml", "on:", "high"),
    ],
})()

# ── Package Manager ────────────────────────────────────────────────

NPM_DETECTOR = type("_NpmDetector", (_TechDetector,), {
    "name": "npm",
    "category": "package_manager",
    "markers": [
        ("package-lock.json", "", "high"),
        ("package.json", "", "medium"),
    ],
})()

YARN_DETECTOR = type("_YarnDetector", (_TechDetector,), {
    "name": "yarn",
    "category": "package_manager",
    "markers": [
        ("yarn.lock", "", "high"),
        ("package.json", '"yarn"', "medium"),
    ],
})()

PNPM_DETECTOR = type("_PnpmDetector", (_TechDetector,), {
    "name": "pnpm",
    "category": "package_manager",
    "markers": [
        ("pnpm-lock.yaml", "", "high"),
    ],
})()

# ── Monorepo ───────────────────────────────────────────────────────

MONOREPO_NPM_DETECTOR = type("_MonorepoNpmDetector", (_TechDetector,), {
    "name": "npm-workspaces",
    "category": "infra",
    "markers": [
        ("package.json", '"workspaces"', "high"),
    ],
})()

MONOREPO_TURBO_DETECTOR = type("_MonorepoTurboDetector", (_TechDetector,), {
    "name": "turborepo",
    "category": "infra",
    "markers": [
        ("turbo.json", "", "high"),
        ("package.json", '"turbo"', "high"),
    ],
})()

# ── AWS / Cloud ────────────────────────────────────────────────────

TF_DETECTOR = type("_TerraformDetector", (_TechDetector,), {
    "name": "terraform",
    "category": "infra",
    "markers": [
        ("*.tf", 'terraform {', "high"),
        ("**/*.tf", 'required_providers', "high"),
    ],
})()

# ── Definierte Detectors ───────────────────────────────────────────

ALL_DETECTORS: List[_TechDetector] = [
    # Backend
    MEDUSA_V2_DETECTOR,
    NEXTJS_DETECTOR,
    EXPRESS_DETECTOR,
    FASTIFY_DETECTOR,
    GO_CHI_DETECTOR,
    GO_FIBER_DETECTOR,
    FASTAPI_DETECTOR,
    DJANGO_DETECTOR,
    # Frontend
    REACT_DETECTOR,
    VUE_DETECTOR,
    SVELTE_DETECTOR,
    VITE_DETECTOR,
    # UI Libs
    TAILWIND_DETECTOR,
    SHADCN_DETECTOR,
    MEDUSAJ_UI_DETECTOR,
    # DB
    POSTGRESQL_DETECTOR,
    REDIS_DETECTOR,
    # Languages
    TYPESCRIPT_DETECTOR,
    JAVASCRIPT_DETECTOR,
    PYTHON_DETECTOR,
    RUST_DETECTOR,
    GO_DETECTOR,
    # Testing
    JEST_DETECTOR,
    VITEST_DETECTOR,
    PLAYWRIGHT_DETECTOR,
    # Infra
    DOCKER_DETECTOR,
    SYSTEMD_DETECTOR,
    NGINX_DETECTOR,
    TF_DETECTOR,
    MONOREPO_NPM_DETECTOR,
    MONOREPO_TURBO_DETECTOR,
    # CI
    GITHUB_ACTIONS_DETECTOR,
    FORGEJO_ACTIONS_DETECTOR,
    # Package Manager
    NPM_DETECTOR,
    YARN_DETECTOR,
    PNPM_DETECTOR,
]


# ---------------------------------------------------------------------------
# Main Detection Engine
# ---------------------------------------------------------------------------


class FrameworkDetector:
    """Hauptklasse für die Framework-Erkennung.

    Analysiert ein Projekt-Root und erstellt ein FrameworkProfile
    mit allen erkannten Technologien, Evidenzen und Confidence-Leveln.

    Usage:
        >>> detector = FrameworkDetector("/path/to/project")
        >>> profile = detector.detect()
        >>> profile.has_framework("medusa-v2")
        True
        >>> profile.get_frameworks_by_category("backend")
        [DetectedFramework(name='medusa-v2', ...)]
    """

    def __init__(
        self,
        project_root: str,
        custom_detectors: Optional[List[_TechDetector]] = None,
    ):
        self.project_root = Path(project_root).resolve()
        if not self.project_root.is_dir():
            raise ValueError(f"Project root nicht gefunden: {project_root}")

        self._detectors = custom_detectors or ALL_DETECTORS
        self._profile = FrameworkProfile(project_root=str(self.project_root))

    # ── Public API ──────────────────────────────────────────────

    def detect(
        self,
        categories: Optional[List[str]] = None,
    ) -> FrameworkProfile:
        """Führt die vollständige Framework-Erkennung durch.

        Args:
            categories: Optional. Nur bestimmte Kategorien scannen
                        (z.B. ["backend", "frontend"]). None = alle.

        Returns:
            FrameworkProfile mit allen erkannten Frameworks.
        """
        self._profile = FrameworkProfile(project_root=str(self.project_root))

        detectors = self._detectors
        if categories:
            detectors = [d for d in self._detectors if d.category in categories]

        for detector in detectors:
            try:
                result = detector.detect(self.project_root)
                if result is not None:
                    cat = result.category
                    if cat not in self._profile.frameworks:
                        self._profile.frameworks[cat] = []
                    self._profile.frameworks[cat].append(result)
            except Exception as e:
                logger.debug("Detector %s fehlgeschlagen: %s", detector.name, e)
                self._profile.errors.append(
                    f"{detector.name}: {e}"
                )

        self._compute_confidence()
        return self._profile

    def detect_fast(self) -> FrameworkProfile:
        """Schnelle Erkennung nur via package.json / go.mod / Marker-Dateien.

        Überspringt aufwändige rekursive Scans. Gut für schnelle Orientierung.
        """
        # Nur Detectors mit high-confidence Markern
        fast_detectors = []
        for d in self._detectors:
            has_high = any(m[2] == "high" for m in d.markers)
            if has_high:
                fast_detectors.append(d)

        self._profile = FrameworkProfile(project_root=str(self.project_root))
        for detector in fast_detectors:
            try:
                result = detector.detect(self.project_root)
                if result is not None:
                    cat = result.category
                    if cat not in self._profile.frameworks:
                        self._profile.frameworks[cat] = []
                    self._profile.frameworks[cat].append(result)
            except Exception:
                pass

        self._compute_confidence()
        return self._profile

    @staticmethod
    def detect_from_profile(
        project_root: str,
        profile_data: dict,
    ) -> FrameworkProfile:
        """Erstellt ein FrameworkProfile aus bereits vorhandenen Daten.

        Nützlich wenn die Analyse schon gelaufen ist (z.B. aus analysis_ui_gap).
        """
        profile = FrameworkProfile(project_root=project_root)
        # Einfache Konvertierung
        for cat, fw_list in profile_data.get("frameworks", {}).items():
            profile.frameworks[cat] = [
                DetectedFramework(**fw) if isinstance(fw, dict) else fw
                for fw in fw_list
            ]
        profile.overall_confidence = profile_data.get("overall_confidence", 0.0)
        return profile

    # ── Interne Methoden ─────────────────────────────────────────

    def _compute_confidence(self) -> None:
        """Berechnet die Gesamt-Confidence basierend auf allen Evidenzen."""
        total = 0
        count = 0
        for fw_list in self._profile.frameworks.values():
            for fw in fw_list:
                weight = {"high": 1.0, "medium": 0.6, "low": 0.3}.get(
                    fw.confidence, 0.0
                )
                total += weight
                count += 1

        if count == 0:
            self._profile.overall_confidence = 0.0
        else:
            self._profile.overall_confidence = round(total / count, 2)


# ---------------------------------------------------------------------------
# Convenience-API
# ---------------------------------------------------------------------------


def detect_frameworks(
    project_root: str,
    categories: Optional[List[str]] = None,
    fast: bool = False,
) -> dict:
    """Einzige öffentliche Funktion — erkennt Frameworks und gibt Dict zurück.

    Args:
        project_root: Pfad zum Projekt-Root
        categories: Optionale Kategorie-Filter (["backend", "frontend", ...])
        fast: Wenn True, nur High-Confidence-Marker scannen

    Returns:
        Dict mit Framework-Profil (kann direkt an Bug-Hunt übergeben werden)
    """
    detector = FrameworkDetector(project_root)
    profile = detector.detect_fast() if fast else detector.detect(categories)
    return profile.to_dict()


def format_profile_summary(profile: dict) -> str:
    """Formatiert ein Framework-Profil als lesbaren String."""
    if not profile or not profile.get("frameworks"):
        return "Keine Frameworks erkannt."

    lines = [f"Framework-Profil: {profile['project_root']}"]
    lines.append(f"Confidence: {profile.get('overall_confidence', 0):.0%}")
    lines.append("")

    for category, fw_list in sorted(profile.get("frameworks", {}).items()):
        lines.append(f"  [{category}]")
        for fw in fw_list:
            ver = f" v{fw['version']}" if fw.get("version") else ""
            conf_icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(
                fw.get("confidence", ""), "⚪"
            )
            lines.append(f"    {conf_icon} {fw['name']}{ver}")
            for ev in fw.get("evidence", []):
                lines.append(f"      → {ev['source']} ({ev['confidence']})")
        lines.append("")

    return "\n".join(lines)
