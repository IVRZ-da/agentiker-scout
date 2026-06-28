"""Dependency Version Scanner — Version-basierte Vulnerability-Erkennung.

Scannt package.json, requirements.txt, go.mod, Cargo.toml nach Abhängigkeiten
mit bekannten verwundbaren Versionen (Top-50 GHSA-Einträge).

Usage:
    scanner = DependencyVersionScanner()
    findings = scanner.scan(Path("/path/to/project"))

Das Modul ist standalone und hat keinen Import-Circular zu bughunt.
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from shared.framework_detector import DetectedFramework, FrameworkEvidence

logger = logging.getLogger("scout.dependency_scanner")


# ---------------------------------------------------------------------------
# Datenmodell: VersionVulnerability
# ---------------------------------------------------------------------------


@dataclass
class VersionVulnerability:
    """Bekannte Sicherheitslücke mit Version-Range.

    Attributes:
        package: Paketname (z.B. "lodash").
        ecosystem: Ökosystem (npm | pypi | go | cargo).
        vulnerable_versions: SemVer Ranges die verwundbar sind (z.B. ["<4.17.21"]).
        patched_versions: SemVer Ranges die als gefixt gelten (z.B. [">=4.17.21"]).
        severity: Schweregrad (critical | high | medium | low).
        title: Menschlesbarer Titel der Lücke.
        cwe: CWE-Kennung (z.B. "CWE-1321").
        ghsa_id: GitHub Security Advisory ID (z.B. "GHSA-xxxx-xxxx-xxxx").
    """

    package: str
    ecosystem: str
    vulnerable_versions: List[str]
    patched_versions: List[str]
    severity: str
    title: str
    cwe: str
    ghsa_id: str


# ---------------------------------------------------------------------------
# Dependency Version Scanner
# ---------------------------------------------------------------------------


class DependencyVersionScanner:
    """Scannt Dependency-Manifeste auf bekannte verwundbare Versionen.

    Der Scanner durchsucht package.json, requirements.txt, go.mod und
    Cargo.toml nach installierten Abhängigkeiten und vergleicht deren
    Versionen mit einer eingebauten Liste von Top-50 GHSA-Einträgen.
    """

    # ── Vulnerability-Daten (lazy aus vulnerabilities.json) ────────
    VULNERABILITIES: List[VersionVulnerability] = []
    _VULNERABILITIES_LOADED: bool = False

    @classmethod
    def _ensure_vulnerabilities_loaded(cls) -> None:
        """Lade Vulnerability-Daten lazy aus vulnerabilities.json."""
        if cls._VULNERABILITIES_LOADED:
            return
        cls._VULNERABILITIES_LOADED = True
        _vuln_path = Path(__file__).resolve().parent / "vulnerabilities.json"
        if not _vuln_path.exists():
            logger.warning("vulnerabilities.json nicht gefunden: %s", _vuln_path)
            return
        try:
            import json
            data = json.loads(_vuln_path.read_text(encoding="utf-8"))
            for entry in data:
                cls.VULNERABILITIES.append(VersionVulnerability(
                    package=entry.get("package", ""),
                    ecosystem=entry.get("ecosystem", ""),
                    vulnerable_versions=entry.get("vulnerable_versions", []),
                    patched_versions=entry.get("patched_versions", []),
                    severity=entry.get("severity", ""),
                    title=entry.get("title", ""),
                    cwe=entry.get("cwe", ""),
                    ghsa_id=entry.get("ghsa_id", ""),
                ))
            logger.debug("dependency_scanner: %d vulnerabilities geladen", len(data))
        except Exception as e:
            logger.warning("vulnerabilities.json konnte nicht geladen werden: %s", e)

    # ── Manifest-Parser Registry ──────────────────────────────────
    _MANIFEST_PARSERS: List[Tuple[str, str]] = [
        ("package.json", "npm"),
        ("requirements.txt", "pypi"),
        ("go.mod", "go"),
        ("Cargo.toml", "cargo"),
    ]

    def scan(self, root: Path) -> List[Dict]:
        """Scannt Dependency-Manifeste im Root-Verzeichnis.

        Parst package.json, requirements.txt, go.mod, Cargo.toml
        und vergleicht alle gefundenen Abhängigkeiten mit den
        bekannten Vulnerabilities.

        Args:
            root: Projekt-Wurzelverzeichnis.

        Returns:
            Liste von Finding-Dicts mit Schlüsseln:
            - package, ecosystem, installed_version
            - title, severity, cwe, ghsa_id
            - evidence (installierte Version)
            - manifest_file
        """
        findings: List[Dict] = []

        for filename, ecosystem in self._MANIFEST_PARSERS:
            filepath = root / filename
            if not filepath.exists():
                logger.debug("Kein %s gefunden in %s", filename, root)
                continue

            try:
                deps = self._parse_manifest(filename, filepath)
            except Exception as e:
                logger.warning("Fehler beim Parsen von %s: %s", filename, e)
                continue

            for pkg_name, installed_version in deps:
                vuln_results = self._check_vulnerabilities(
                    pkg_name, installed_version, ecosystem, filename,
                )
                findings.extend(vuln_results)

        return findings

    # ── Öffentliche Klassenmethode ────────────────────────────────

    @classmethod
    def add_vulnerability(cls, vuln: VersionVulnerability) -> None:
        """Fügt eine benutzerdefinierte Vulnerability zur Scan-Liste hinzu."""
        cls._ensure_vulnerabilities_loaded()
        cls.VULNERABILITIES.append(vuln)

    # ── Interne Prüflogik ─────────────────────────────────────────

    def _check_vulnerabilities(
        self,
        pkg: str,
        version: str,
        ecosystem: str,
        manifest_file: str,
    ) -> List[Dict]:
        """Prüft eine Package-Version gegen alle bekannten Vulnerabilities."""
        self.__class__._ensure_vulnerabilities_loaded()
        results: List[Dict] = []

        for vuln in self.VULNERABILITIES:
            if vuln.package != pkg:
                continue
            if vuln.ecosystem != ecosystem:
                continue
            if not self._version_in_range(version, vuln.vulnerable_versions):
                continue

            results.append({
                "package": pkg,
                "ecosystem": ecosystem,
                "installed_version": version,
                "title": vuln.title,
                "severity": vuln.severity,
                "cwe": vuln.cwe,
                "ghsa_id": vuln.ghsa_id,
                "evidence": f"{pkg}@{version} ist verwundbar",
                "patched_versions": vuln.patched_versions,
                "manifest_file": manifest_file,
            })

        return results

    # ── Manifest-Parser ───────────────────────────────────────────

    def _parse_manifest(self, filename: str, path: Path) -> List[Tuple[str, str]]:
        """Leitet an den passenden Parser weiter."""
        parser_map = {
            "package.json": self._parse_package_json,
            "requirements.txt": self._parse_requirements_txt,
            "go.mod": self._parse_go_mod,
            "Cargo.toml": self._parse_cargo_toml,
        }
        parser = parser_map.get(filename)
        if parser is None:
            raise ValueError(f"Unbekanntes Manifest: {filename}")
        return parser(path)

    @staticmethod
    def _parse_package_json(path: Path) -> List[Tuple[str, str]]:
        """Parst package.json → [(package, version), ...].

        Unterstützt dependencies, devDependencies, peerDependencies,
        sowie SemVer-Präfixe ^, ~, >=, <=.
        """
        data = json.loads(path.read_text(encoding="utf-8"))
        result: List[Tuple[str, str]] = []

        for section in ("dependencies", "devDependencies", "peerDependencies"):
            deps = data.get(section, {})
            if not isinstance(deps, dict):
                continue
            for pkg_name, ver_spec in deps.items():
                if not isinstance(ver_spec, str):
                    continue
                clean = DependencyVersionScanner._clean_semver(ver_spec)
                if clean:
                    result.append((pkg_name, clean))

        return result

    @staticmethod
    def _parse_requirements_txt(path: Path) -> List[Tuple[str, str]]:
        """Parst requirements.txt → [(package, version), ...].

        Unterstützt Formate:
          package==1.0.0
          package>=1.0.0
          package<=1.0.0
          package~=1.0.0
          package!=1.0.0
        """
        result: List[Tuple[str, str]] = []
        content = path.read_text(encoding="utf-8", errors="ignore")

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # Entferne Inline-Kommentare
            if " #" in line:
                line = line.split(" #")[0].strip()
            if "  #" in line:
                line = line.split("  #")[0].strip()

            m = re.match(
                r"^([a-zA-Z0-9_.-]+)\s*((?:===?|>=?|<=?|!=|~=)\s*"
                r"([a-zA-Z0-9_.*-]+(?:\.[a-zA-Z0-9_.*-]+)*))",
                line,
            )
            if m:
                pkg = m.group(1).lower()
                ver = m.group(3)
                # Wildcard handling: 2.* → 2.0
                ver = ver.replace("*", "0")
                if ver:
                    result.append((pkg, ver))

        return result

    @staticmethod
    def _parse_go_mod(path: Path) -> List[Tuple[str, str]]:
        """Parst go.mod → [(package, version), ...].

        Unterstützt single-line und multi-line require-Blöcke.
        """
        result: List[Tuple[str, str]] = []
        content = path.read_text(encoding="utf-8", errors="ignore")
        in_require_block = False

        for line in content.splitlines():
            raw = line.strip()
            if not raw:
                continue
            if raw.startswith("require (") or raw == "require":
                in_require_block = True
                continue
            if in_require_block and raw == ")":
                in_require_block = False
                continue

            # Nur verarbeiten wenn wir im require-Kontext sind
            if not in_require_block and not raw.startswith("require "):
                continue

            # Single-line: require golang.org/x/net v0.17.0
            if raw.startswith("require ") and "(" not in raw:
                parts = raw[len("require "):].strip().split()
                if len(parts) >= 2:
                    pkg = parts[0]
                    ver = DependencyVersionScanner._clean_go_version(
                        parts[-1],
                    )
                    if ver:
                        result.append((pkg, ver))
                continue

            # Block-content (nur innerhalb require-Block):
            # golang.org/x/net v0.17.0
            if in_require_block:
                parts = raw.split()
                if len(parts) >= 2:
                    pkg = parts[0]
                    ver = DependencyVersionScanner._clean_go_version(parts[-1])
                    if ver:
                        result.append((pkg, ver))

        return result

    @staticmethod
    def _clean_go_version(raw: str) -> Optional[str]:
        """Bereinigt Go-Module-Versionen.

        Go-Versionen haben Präfix 'v', optional +incompatible,
        oder Pseudo-Versionen mit commit hash.
        """
        ver = raw.lstrip("v")
        # Pseudo-Versionen: v0.0.0-20230101000000-abcdef123456
        # Nur die reine SemVer nutzen
        if ver.count("-") >= 2:
            # Pseudo-Version → extract base version
            parts = ver.split("-")
            ver = parts[0]
        # +incompatible suffix
        ver = ver.split("+")[0]
        return ver if ver else None

    @staticmethod
    def _parse_cargo_toml(path: Path) -> List[Tuple[str, str]]:
        """Parst Cargo.toml → [(package, version), ...].

        Unterstützt:
          [dependencies]
          serde = "1.0"
          tokio = { version = "1.19", features = ["full"] }
        """
        result: List[Tuple[str, str]] = []
        content = path.read_text(encoding="utf-8", errors="ignore")
        current_section: Optional[str] = None
        skip_section = False

        for line in content.splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue

            # Section header: [dependencies], [dev-dependencies]
            if raw.startswith("["):
                section_name = raw[1:].rstrip("]").strip()
                current_section = section_name
                skip_section = section_name not in (
                    "dependencies", "dev-dependencies", "build-dependencies",
                )
                continue

            if skip_section or current_section is None:
                continue

            # Simple: serde = "1.0"
            simple_m = re.match(r'^([a-zA-Z0-9_-]+)\s*=\s*"([^"]+)"', raw)
            if simple_m:
                pkg = simple_m.group(1)
                ver = simple_m.group(2)
                clean = DependencyVersionScanner._clean_semver(ver)
                if clean:
                    result.append((pkg, clean))
                continue

            # Table-style: tokio = { version = "1.19", features = [...] }
            table_m = re.match(
                r'^([a-zA-Z0-9_-]+)\s*=\s*\{.*version\s*=\s*"([^"]+)".*\}',
                raw,
            )
            if table_m:
                pkg = table_m.group(1)
                ver = table_m.group(2)
                clean = DependencyVersionScanner._clean_semver(ver)
                if clean:
                    result.append((pkg, clean))

        return result

    # ── SemVer Utilities ──────────────────────────────────────────

    @staticmethod
    def _clean_semver(version_str: str) -> Optional[str]:
        """Entfernt SemVer-Präfixe (^, ~, >=, <=) und Wildcards.

        Wandelt "^1.2.3" → "1.2.3", "~1.2" → "1.2", ">=1.0.0" → "1.0.0".
        Gibt None zurück wenn nach Clean nichts übrig bleibt.
        """
        ver = version_str.strip()
        # Remove common prefixes
        ver = re.sub(r"^[\^~<>=! ]+", "", ver).strip()
        # Handle "||" (OR) — take first alternative
        if "||" in ver:
            ver = ver.split("||")[0].strip()
        # Handle spaces like ">= 1.0.0" → cleanup
        ver = ver.split()[0] if " " in ver else ver
        # Wildcard
        ver = ver.replace("*", "0")
        return ver if ver else None

    @staticmethod
    def _version_in_range(version: str, ranges: List[str]) -> bool:
        """Prüft ob Version innerhalb einer der angegebenen Ranges liegt.

        Unterstützt: >=1.0.0, <1.0.0, >1.0.0 <=2.0.0, ==1.0.0, !=1.0.0,
        sowie komplexe Ausdrücke wie ">=1.0.0,<2.0.0".

        Nutzt packaging.specifiers.SpecifierSet für robusten Vergleich.

        Args:
            version: Zu prüfende Version (z.B. "1.2.3").
            ranges: Liste von SemVer-Range-Strings (z.B. ["<4.17.21"]).

        Returns:
            True wenn die Version in mindestens einem Range liegt.
        """
        try:
            ver = Version(version)
        except InvalidVersion:
            logger.debug("Ungültige Version: %s", version)
            return False

        for range_str in ranges:
            if not range_str or not range_str.strip():
                continue
            try:
                spec = SpecifierSet(range_str)
                if ver in spec:
                    return True
            except InvalidSpecifier:
                logger.debug("Ungültiger Range: %s", range_str)
                continue

        return False

    # ── Integration mit DetectedFramework ─────────────────────────

    def scan_as_frameworks(self, root: Path) -> List[DetectedFramework]:
        """Alternative scan-Methode, die DetectedFramework-Objekte liefert.

        Wird für die Integration in bug_hunt_scan verwendet,
        wo scan_type='version' aufgerufen wird.
        """
        findings = self.scan(root)
        frameworks: List[DetectedFramework] = []

        for f in findings:
            evidence = FrameworkEvidence(
                source=f.get("manifest_file", f.get("package", "")),
                pattern=f["ghsa_id"],
                confidence="high",
                version=f.get("installed_version", ""),
            )
            frameworks.append(DetectedFramework(
                name=f["title"],
                category="vulnerability",
                confidence="high",
                version=f.get("installed_version", ""),
                evidence=[evidence],
            ))

        return frameworks
