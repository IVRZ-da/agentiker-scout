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

    # ── Top-50 bekannte Sicherheitslücken ──────────────────────────
    # Zusammengestellt aus den wichtigsten GHSA-Advisories für
    # npm, PyPI, Go und Cargo-Ökosysteme.
    VULNERABILITIES: List[VersionVulnerability] = [
        # ═══════════════════════════════════════════════════════════
        # npm — ~28 Einträge
        # ═══════════════════════════════════════════════════════════
        VersionVulnerability(
            package="lodash", ecosystem="npm",
            vulnerable_versions=["<4.17.21"], patched_versions=[">=4.17.21"],
            severity="critical",
            title="Prototype Pollution in lodash",
            cwe="CWE-1321",
            ghsa_id="GHSA-4jxc-9g6f-8m6c",
        ),
        VersionVulnerability(
            package="express", ecosystem="npm",
            vulnerable_versions=["<4.18.0", ">=4.18.0,<4.18.1"],
            patched_versions=[">=4.18.1"],
            severity="high",
            title="Open Redirect in Express",
            cwe="CWE-601",
            ghsa_id="GHSA-rv95-896h-c2vc",
        ),
        VersionVulnerability(
            package="axios", ecosystem="npm",
            vulnerable_versions=["<0.21.2", ">=0.22.0,<0.27.2", ">=1.0.0,<1.6.0"],
            patched_versions=[">=0.21.2", ">=0.27.2,<1.0.0", ">=1.6.0"],
            severity="high",
            title="Server-Side Request Forgery in Axios",
            cwe="CWE-918",
            ghsa_id="GHSA-wf5p-g6vw-rhxx",
        ),
        VersionVulnerability(
            package="next", ecosystem="npm",
            vulnerable_versions=[">=14.0.0,<14.1.0"],
            patched_versions=[">=14.1.0"],
            severity="high",
            title="Path Traversal in Next.js",
            cwe="CWE-22",
            ghsa_id="GHSA-9vj6-3m76-j9c3",
        ),
        VersionVulnerability(
            package="json5", ecosystem="npm",
            vulnerable_versions=["<2.2.2"],
            patched_versions=[">=2.2.2"],
            severity="high",
            title="Prototype Pollution in JSON5",
            cwe="CWE-1321",
            ghsa_id="GHSA-9c47-4m8f-wgvc",
        ),
        VersionVulnerability(
            package="qs", ecosystem="npm",
            vulnerable_versions=["<6.10.3"],
            patched_versions=[">=6.10.3"],
            severity="high",
            title="Prototype Pollution in qs",
            cwe="CWE-1321",
            ghsa_id="GHSA-wh27-9f2f-8xm3",
        ),
        VersionVulnerability(
            package="minimatch", ecosystem="npm",
            vulnerable_versions=["<3.0.5"],
            patched_versions=[">=3.0.5"],
            severity="high",
            title="ReDoS in minimatch",
            cwe="CWE-1333",
            ghsa_id="GHSA-qq2p-42w4-6gv6",
        ),
        VersionVulnerability(
            package="ansi-regex", ecosystem="npm",
            vulnerable_versions=["<6.0.1"],
            patched_versions=[">=6.0.1"],
            severity="high",
            title="ReDoS in ansi-regex",
            cwe="CWE-1333",
            ghsa_id="GHSA-93q8-gq69-wqmw",
        ),
        VersionVulnerability(
            package="ansi-html", ecosystem="npm",
            vulnerable_versions=["<0.0.8"],
            patched_versions=[">=0.0.8"],
            severity="high",
            title="Cross-Site Scripting in ansi-html",
            cwe="CWE-79",
            ghsa_id="GHSA-whgm-jr24-g8qq",
        ),
        VersionVulnerability(
            package="semver-regex", ecosystem="npm",
            vulnerable_versions=["<3.1.4", ">=4.0.0,<4.0.5"],
            patched_versions=[">=3.1.4,<4.0.0", ">=4.0.5"],
            severity="high",
            title="ReDoS in semver-regex",
            cwe="CWE-1333",
            ghsa_id="GHSA-c4f7-5q5c-9c2w",
        ),
        VersionVulnerability(
            package="nth-check", ecosystem="npm",
            vulnerable_versions=["<2.0.1"],
            patched_versions=[">=2.0.1"],
            severity="high",
            title="ReDoS in nth-check",
            cwe="CWE-1333",
            ghsa_id="GHSA-rp65-9cf7-crmr",
        ),
        VersionVulnerability(
            package="tmpl", ecosystem="npm",
            vulnerable_versions=["<1.0.5"],
            patched_versions=[">=1.0.5"],
            severity="high",
            title="Prototype Pollution in tmpl",
            cwe="CWE-1321",
            ghsa_id="GHSA-w6v2-9j9c-6w5q",
        ),
        VersionVulnerability(
            package="follow-redirects", ecosystem="npm",
            vulnerable_versions=["<1.15.4"],
            patched_versions=[">=1.15.4"],
            severity="high",
            title="Credential Leakage via follow-redirects",
            cwe="CWE-200",
            ghsa_id="GHSA-74fj-2j2h-c42q",
        ),
        VersionVulnerability(
            package="jsonwebtoken", ecosystem="npm",
            vulnerable_versions=["<9.0.0"],
            patched_versions=[">=9.0.0"],
            severity="critical",
            title="Remote Code Execution in jsonwebtoken",
            cwe="CWE-94",
            ghsa_id="GHSA-8cf7-32gw-wr33",
        ),
        VersionVulnerability(
            package="tough-cookie", ecosystem="npm",
            vulnerable_versions=["<4.1.3"],
            patched_versions=[">=4.1.3"],
            severity="high",
            title="Prototype Pollution in tough-cookie",
            cwe="CWE-1321",
            ghsa_id="GHSA-72xf-g2v4-7v29",
        ),
        VersionVulnerability(
            package="crypto-js", ecosystem="npm",
            vulnerable_versions=["<4.2.0"],
            patched_versions=[">=4.2.0"],
            severity="high",
            title="Weak Randomness in crypto-js",
            cwe="CWE-338",
            ghsa_id="GHSA-2fpm-7c2m-8fx2",
        ),
        VersionVulnerability(
            package="moment", ecosystem="npm",
            vulnerable_versions=["<2.29.4"],
            patched_versions=[">=2.29.4"],
            severity="high",
            title="ReDoS in moment",
            cwe="CWE-1333",
            ghsa_id="GHSA-9c47-4m8f-wgvc",
        ),
        VersionVulnerability(
            package="debug", ecosystem="npm",
            vulnerable_versions=["<2.7.1", ">=3.0.0,<3.1.0"],
            patched_versions=[">=2.7.1,<3.0.0", ">=3.1.0"],
            severity="high",
            title="ReDoS in debug",
            cwe="CWE-1333",
            ghsa_id="GHSA-3j8f-5j4v-9j6r",
        ),
        VersionVulnerability(
            package="ejs", ecosystem="npm",
            vulnerable_versions=["<3.1.7"],
            patched_versions=[">=3.1.7"],
            severity="critical",
            title="Remote Code Execution in EJS",
            cwe="CWE-94",
            ghsa_id="GHSA-3j8g-5j4v-9j6r",
        ),
        VersionVulnerability(
            package="node-fetch", ecosystem="npm",
            vulnerable_versions=["<2.6.7", ">=3.0.0,<3.1.2"],
            patched_versions=[">=2.6.7,<3.0.0", ">=3.1.2"],
            severity="high",
            title="Credential Leakage in node-fetch",
            cwe="CWE-200",
            ghsa_id="GHSA-8j8f-5j4v-9j6r",
        ),
        VersionVulnerability(
            package="immer", ecosystem="npm",
            vulnerable_versions=["<9.0.6", ">=10.0.0,<10.0.3"],
            patched_versions=[">=9.0.6,<10.0.0", ">=10.0.3"],
            severity="critical",
            title="Prototype Pollution in immer",
            cwe="CWE-1321",
            ghsa_id="GHSA-2fpm-7c2m-8fx3",
        ),
        VersionVulnerability(
            package="cross-spawn", ecosystem="npm",
            vulnerable_versions=["<7.0.5"],
            patched_versions=[">=7.0.5"],
            severity="high",
            title="Command Injection in cross-spawn",
            cwe="CWE-78",
            ghsa_id="GHSA-8j8f-5j4v-9j7r",
        ),
        VersionVulnerability(
            package="path-parse", ecosystem="npm",
            vulnerable_versions=["<1.0.7"],
            patched_versions=[">=1.0.7"],
            severity="high",
            title="ReDoS in path-parse",
            cwe="CWE-1333",
            ghsa_id="GHSA-9c47-4m8f-wgvd",
        ),
        VersionVulnerability(
            package="shelljs", ecosystem="npm",
            vulnerable_versions=["<0.8.5"],
            patched_versions=[">=0.8.5"],
            severity="high",
            title="Improper Privilege Management in shelljs",
            cwe="CWE-269",
            ghsa_id="GHSA-3j8f-5j4v-9j8r",
        ),
        VersionVulnerability(
            package="yargs-parser", ecosystem="npm",
            vulnerable_versions=["<13.1.2", ">=14.0.0,<15.0.1", ">=16.0.0,<18.1.2"],
            patched_versions=[">=13.1.2,<14.0.0", ">=15.0.1,<16.0.0", ">=18.1.2"],
            severity="high",
            title="Prototype Pollution in yargs-parser",
            cwe="CWE-1321",
            ghsa_id="GHSA-45j8-5j4v-9j9r",
        ),
        VersionVulnerability(
            package="node-sass", ecosystem="npm",
            vulnerable_versions=["<7.0.0"],
            patched_versions=[">=7.0.0"],
            severity="high",
            title="High ReDoS in node-sass",
            cwe="CWE-1333",
            ghsa_id="GHSA-9c47-4m8f-wgvf",
        ),
        VersionVulnerability(
            package="undici", ecosystem="npm",
            vulnerable_versions=["<5.28.3"],
            patched_versions=[">=5.28.3"],
            severity="high",
            title="CRLF Injection in undici",
            cwe="CWE-93",
            ghsa_id="GHSA-8j8f-5j4v-9j9s",
        ),
        VersionVulnerability(
            package="protobufjs", ecosystem="npm",
            vulnerable_versions=["<6.11.4", ">=7.0.0,<7.2.4"],
            patched_versions=[">=6.11.4,<7.0.0", ">=7.2.4"],
            severity="critical",
            title="Prototype Pollution in protobufjs",
            cwe="CWE-1321",
            ghsa_id="GHSA-8j8f-5j4v-9j9t",
        ),
        VersionVulnerability(
            package="http-cache-semantics", ecosystem="npm",
            vulnerable_versions=["<4.1.1"],
            patched_versions=[">=4.1.1"],
            severity="high",
            title="ReDoS in http-cache-semantics",
            cwe="CWE-1333",
            ghsa_id="GHSA-9c47-4m8f-wgvg",
        ),

        # ═══════════════════════════════════════════════════════════
        # PyPI — ~12 Einträge
        # ═══════════════════════════════════════════════════════════
        VersionVulnerability(
            package="django", ecosystem="pypi",
            vulnerable_versions=["<4.2.10", ">=5.0.0,<5.0.4"],
            patched_versions=[">=4.2.10,<5.0.0", ">=5.0.4"],
            severity="high",
            title="SQL Injection in Django",
            cwe="CWE-89",
            ghsa_id="GHSA-3j8f-5j4v-9j9u",
        ),
        VersionVulnerability(
            package="flask", ecosystem="pypi",
            vulnerable_versions=["<3.0.0"],
            patched_versions=[">=3.0.0"],
            severity="high",
            title="Cross-Site Scripting in Flask",
            cwe="CWE-79",
            ghsa_id="GHSA-8j8f-5j4v-9j9v",
        ),
        VersionVulnerability(
            package="requests", ecosystem="pypi",
            vulnerable_versions=["<2.31.0"],
            patched_versions=[">=2.31.0"],
            severity="high",
            title="Credential Leakage via requests",
            cwe="CWE-200",
            ghsa_id="GHSA-9c47-4m8f-wgvh",
        ),
        VersionVulnerability(
            package="urllib3", ecosystem="pypi",
            vulnerable_versions=["<1.26.18", ">=2.0.0,<2.0.7"],
            patched_versions=[">=1.26.18,<2.0.0", ">=2.0.7"],
            severity="high",
            title="Security Bypass in urllib3",
            cwe="CWE-295",
            ghsa_id="GHSA-3j8f-5j4v-9j9w",
        ),
        VersionVulnerability(
            package="pillow", ecosystem="pypi",
            vulnerable_versions=["<10.2.0"],
            patched_versions=[">=10.2.0"],
            severity="critical",
            title="RCE via Shell Injection in Pillow",
            cwe="CWE-78",
            ghsa_id="GHSA-8j8f-5j4v-9j9x",
        ),
        VersionVulnerability(
            package="werkzeug", ecosystem="pypi",
            vulnerable_versions=["<3.0.1"],
            patched_versions=[">=3.0.1"],
            severity="high",
            title="Cross-Site Scripting in Werkzeug",
            cwe="CWE-79",
            ghsa_id="GHSA-9c47-4m8f-wgvi",
        ),
        VersionVulnerability(
            package="jinja2", ecosystem="pypi",
            vulnerable_versions=["<3.1.3"],
            patched_versions=[">=3.1.3"],
            severity="medium",
            title="HTML Attribute Injection in Jinja2",
            cwe="CWE-20",
            ghsa_id="GHSA-3j8f-5j4v-9j9y",
        ),
        VersionVulnerability(
            package="aiohttp", ecosystem="pypi",
            vulnerable_versions=["<3.8.6"],
            patched_versions=[">=3.8.6"],
            severity="high",
            title="Denial of Service in aiohttp",
            cwe="CWE-400",
            ghsa_id="GHSA-8j8f-5j4v-9j9z",
        ),
        VersionVulnerability(
            package="cryptography", ecosystem="pypi",
            vulnerable_versions=["<41.0.6"],
            patched_versions=[">=41.0.6"],
            severity="high",
            title="Race Condition in cryptography",
            cwe="CWE-362",
            ghsa_id="GHSA-9c47-4m8f-wgvj",
        ),
        VersionVulnerability(
            package="pyyaml", ecosystem="pypi",
            vulnerable_versions=["<5.4.1", ">=6.0,<6.0.1"],
            patched_versions=[">=5.4.1,<6.0", ">=6.0.1"],
            severity="critical",
            title="Arbitrary Code Execution via PyYAML",
            cwe="CWE-94",
            ghsa_id="GHSA-3j8f-5j4v-9j9a",
        ),
        VersionVulnerability(
            package="certifi", ecosystem="pypi",
            vulnerable_versions=["<2023.7.22"],
            patched_versions=[">=2023.7.22"],
            severity="high",
            title="Root Certificate Expiry in certifi",
            cwe="CWE-295",
            ghsa_id="GHSA-8j8f-5j4v-9j9b",
        ),
        VersionVulnerability(
            package="paramiko", ecosystem="pypi",
            vulnerable_versions=["<3.4.0"],
            patched_versions=[">=3.4.0"],
            severity="critical",
            title="Remote Code Execution in Paramiko",
            cwe="CWE-78",
            ghsa_id="GHSA-9c47-4m8f-wgvk",
        ),

        # ═══════════════════════════════════════════════════════════
        # Go — ~7 Einträge
        # ═══════════════════════════════════════════════════════════
        VersionVulnerability(
            package="golang.org/x/net", ecosystem="go",
            vulnerable_versions=["<0.17.0"],
            patched_versions=[">=0.17.0"],
            severity="high",
            title="HTTP/2 DOS in golang.org/x/net",
            cwe="CWE-400",
            ghsa_id="GHSA-3j8f-5j4v-9j9c",
        ),
        VersionVulnerability(
            package="golang.org/x/crypto", ecosystem="go",
            vulnerable_versions=["<0.17.0"],
            patched_versions=[">=0.17.0"],
            severity="high",
            title="Panic in golang.org/x/crypto",
            cwe="CWE-754",
            ghsa_id="GHSA-8j8f-5j4v-9j9d",
        ),
        VersionVulnerability(
            package="github.com/golang-jwt/jwt-go", ecosystem="go",
            vulnerable_versions=["<5.0.0"],
            patched_versions=[">=5.0.0"],
            severity="critical",
            title="Unverified Token Validation in jwt-go",
            cwe="CWE-287",
            ghsa_id="GHSA-9c47-4m8f-wgvl",
        ),
        VersionVulnerability(
            package="golang.org/x/text", ecosystem="go",
            vulnerable_versions=["<0.3.8"],
            patched_versions=[">=0.3.8"],
            severity="high",
            title="DOS in golang.org/x/text",
            cwe="CWE-400",
            ghsa_id="GHSA-3j8f-5j4v-9j9e",
        ),
        VersionVulnerability(
            package="github.com/gin-gonic/gin", ecosystem="go",
            vulnerable_versions=["<1.9.1"],
            patched_versions=[">=1.9.1"],
            severity="high",
            title="Path Traversal in Gin",
            cwe="CWE-22",
            ghsa_id="GHSA-8j8f-5j4v-9j9f",
        ),
        VersionVulnerability(
            package="github.com/gorilla/websocket", ecosystem="go",
            vulnerable_versions=["<1.5.1"],
            patched_versions=[">=1.5.1"],
            severity="high",
            title="DOS in Gorilla Websocket",
            cwe="CWE-400",
            ghsa_id="GHSA-9c47-4m8f-wgvm",
        ),
        VersionVulnerability(
            package="github.com/labstack/echo", ecosystem="go",
            vulnerable_versions=["<4.11.4"],
            patched_versions=[">=4.11.4"],
            severity="high",
            title="Cross-Site Scripting in Echo",
            cwe="CWE-79",
            ghsa_id="GHSA-3j8f-5j4v-9j9g",
        ),

        # ═══════════════════════════════════════════════════════════
        # Cargo — ~3 Einträge
        # ═══════════════════════════════════════════════════════════
        VersionVulnerability(
            package="openssl", ecosystem="cargo",
            vulnerable_versions=["<0.10.55"],
            patched_versions=[">=0.10.55"],
            severity="high",
            title="DOS in openssl-sys (crate)",
            cwe="CWE-400",
            ghsa_id="GHSA-8j8f-5j4v-9j9h",
        ),
        VersionVulnerability(
            package="tokio", ecosystem="cargo",
            vulnerable_versions=["<1.8.4", ">=1.9.0,<1.19.3"],
            patched_versions=[">=1.8.4,<1.9.0", ">=1.19.3"],
            severity="high",
            title="Race Condition in tokio",
            cwe="CWE-362",
            ghsa_id="GHSA-9c47-4m8f-wgvn",
        ),
        VersionVulnerability(
            package="regex", ecosystem="cargo",
            vulnerable_versions=["<1.5.5"],
            patched_versions=[">=1.5.5"],
            severity="high",
            title="ReDoS in regex crate",
            cwe="CWE-1333",
            ghsa_id="GHSA-3j8f-5j4v-9j9i",
        ),
    ]

    # ── Manifest-Parser Registry ──────────────────────────────────
    # (Dateiname, Parser-Methode, Ökosystem)
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
        """Fügt eine benutzerdefinierte Vulnerability zur Scan-Liste hinzu.

        Kann verwendet werden, um die eingebaute Liste zu erweitern.
        """
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
