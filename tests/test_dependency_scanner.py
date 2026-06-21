"""Tests für Dependency Version Scanner.

Deckt ab:
- SemVer-Vergleich (einfache, komplexe Ranges, Edge Cases)
- package.json Parsing
- requirements.txt Parsing
- go.mod Parsing
- Cargo.toml Parsing
- "Version gefunden → Finding"
- "Version nicht gefunden → kein Finding"
- Leere Manifeste
- VULNERABILITIES-Liste (alle haben package, severity, cwe)
"""

import json
from pathlib import Path

import pytest

from shared.dependency_scanner import (
    DependencyVersionScanner,
    VersionVulnerability,
)

# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def scanner() -> DependencyVersionScanner:
    """Eine frische Scanner-Instanz pro Test."""
    return DependencyVersionScanner()


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Temporäres Projektverzeichnis."""
    return tmp_path


# ======================================================================
# SemVer-Vergleich
# ======================================================================


class TestVersionInRange:
    """SemVer Range Matching — Kernlogik des Scanners."""

    def test_simple_less_than(self):
        """<X.Y.Z"""
        assert DependencyVersionScanner._version_in_range("4.17.20", ["<4.17.21"])
        assert not DependencyVersionScanner._version_in_range("4.17.21", ["<4.17.21"])
        assert not DependencyVersionScanner._version_in_range("4.18.0", ["<4.17.21"])

    def test_simple_greater_equal(self):
        """>=X.Y.Z"""
        assert DependencyVersionScanner._version_in_range("4.17.21", [">=4.17.21"])
        assert DependencyVersionScanner._version_in_range("4.18.0", [">=4.17.21"])
        assert not DependencyVersionScanner._version_in_range("4.17.20", [">=4.17.21"])

    def test_simple_equal(self):
        """==X.Y.Z"""
        assert DependencyVersionScanner._version_in_range("4.17.21", ["==4.17.21"])
        assert not DependencyVersionScanner._version_in_range("4.17.20", ["==4.17.21"])

    def test_complex_range(self):
        """>=X.Y.Z,<A.B.C"""
        assert DependencyVersionScanner._version_in_range(
            "1.2.3", [">=1.0.0,<2.0.0"],
        )
        assert DependencyVersionScanner._version_in_range(
            "1.9.9", [">=1.0.0,<2.0.0"],
        )
        assert not DependencyVersionScanner._version_in_range(
            "2.0.0", [">=1.0.0,<2.0.0"],
        )
        assert not DependencyVersionScanner._version_in_range(
            "0.9.9", [">=1.0.0,<2.0.0"],
        )

    def test_multiple_ranges_or(self):
        """Mehrere Ranges via Liste (implizites OR)."""
        assert DependencyVersionScanner._version_in_range(
            "0.21.1", ["<0.21.2", ">=0.22.0,<0.27.2", ">=1.0.0,<1.6.0"],
        )
        assert DependencyVersionScanner._version_in_range(
            "0.25.0", ["<0.21.2", ">=0.22.0,<0.27.2", ">=1.0.0,<1.6.0"],
        )
        assert DependencyVersionScanner._version_in_range(
            "1.5.9", ["<0.21.2", ">=0.22.0,<0.27.2", ">=1.0.0,<1.6.0"],
        )
        assert not DependencyVersionScanner._version_in_range(
            "0.21.2", ["<0.21.2", ">=0.22.0,<0.27.2", ">=1.0.0,<1.6.0"],
        )
        assert not DependencyVersionScanner._version_in_range(
            "0.27.2", ["<0.21.2", ">=0.22.0,<0.27.2", ">=1.0.0,<1.6.0"],
        )
        assert not DependencyVersionScanner._version_in_range(
            "1.6.0", ["<0.21.2", ">=0.22.0,<0.27.2", ">=1.0.0,<1.6.0"],
        )
        assert not DependencyVersionScanner._version_in_range(
            "2.0.0", ["<0.21.2", ">=0.22.0,<0.27.2", ">=1.0.0,<1.6.0"],
        )

    def test_greater_than(self):
        """>X.Y.Z"""
        assert DependencyVersionScanner._version_in_range("1.0.1", [">1.0.0"])
        assert not DependencyVersionScanner._version_in_range("1.0.0", [">1.0.0"])
        assert not DependencyVersionScanner._version_in_range("0.9.9", [">1.0.0"])

    def test_not_equal(self):
        """!=X.Y.Z"""
        assert DependencyVersionScanner._version_in_range("1.0.1", ["!=1.0.0"])
        assert not DependencyVersionScanner._version_in_range("1.0.0", ["!=1.0.0"])

    def test_invalid_version(self):
        """Ungültige Versionen → False."""
        assert not DependencyVersionScanner._version_in_range(
            "invalid", ["<1.0.0"],
        )
        assert not DependencyVersionScanner._version_in_range(
            "", ["<1.0.0"],
        )
        assert not DependencyVersionScanner._version_in_range(
            "abc.def.ghi", ["<1.0.0"],
        )
        assert not DependencyVersionScanner._version_in_range(
            "latest", ["<1.0.0"],
        )

    def test_invalid_range(self):
        """Ungültiger Range → False."""
        assert not DependencyVersionScanner._version_in_range(
            "1.0.0", ["not-a-range"],
        )
        # Leerer String wird von packaging.SpecifierSet("") nicht behandelt
        # und wird explizit von _version_in_range abgefangen
        assert not DependencyVersionScanner._version_in_range(
            "1.0.0", [],
        )

    def test_pre_release_handling(self):
        """Pre-Release Versionen.

        PEP 440: pre-releases sind standardmäßig NICHT in
        Nicht-Pre-Release-SpecifierSets enthalten.
        """
        # Pre-release < release, aber packaging schließt pre-releases
        # standardmäßig aus Nicht-Pre-Release-SpecifierSets aus
        assert not DependencyVersionScanner._version_in_range(
            "4.17.21-alpha.1", ["<4.17.21"],
        )
        # Pre-release-spezifischer Range matched pre-release
        assert DependencyVersionScanner._version_in_range(
            "4.17.21a1", [">=4.17.21a1"],
        )
        # Stable release matches pre-release specifier
        assert DependencyVersionScanner._version_in_range(
            "4.17.21", [">=4.17.21a1"],
        )

    def test_three_digit_edge_cases(self):
        """Versionen mit vielen Ziffern."""
        assert DependencyVersionScanner._version_in_range(
            "2023.7.21", ["<2023.7.22"],
        )
        assert not DependencyVersionScanner._version_in_range(
            "2023.7.22", ["<2023.7.22"],
        )
        assert not DependencyVersionScanner._version_in_range(
            "2023.7.23", ["<2023.7.22"],
        )

    def test_zero_major(self):
        """0.x Versionen."""
        assert DependencyVersionScanner._version_in_range(
            "0.0.1", ["<0.1.0"],
        )
        assert not DependencyVersionScanner._version_in_range(
            "0.1.0", ["<0.1.0"],
        )
        assert DependencyVersionScanner._version_in_range(
            "0.5.0", [">=0.1.0,<0.10.0"],
        )


# ======================================================================
# Manifest-Parsing
# ======================================================================


class TestParsePackageJson:
    """package.json Parser-Tests."""

    PROJECT_ROOT = Path("/")

    def test_basic_dependencies(self, tmp_path):
        """Einfache dependencies."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({
            "name": "test",
            "dependencies": {
                "lodash": "^4.17.20",
                "express": "~4.17.1",
            },
        }))
        result = DependencyVersionScanner._parse_package_json(pkg)
        assert ("lodash", "4.17.20") in result
        assert ("express", "4.17.1") in result

    def test_dev_and_peer_deps(self, tmp_path):
        """devDependencies und peerDependencies."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({
            "dependencies": {"lodash": "^4.17.21"},
            "devDependencies": {"jest": "^29.0.0"},
            "peerDependencies": {"react": "^18.0.0"},
        }))
        result = DependencyVersionScanner._parse_package_json(pkg)
        assert ("lodash", "4.17.21") in result
        assert ("jest", "29.0.0") in result
        assert ("react", "18.0.0") in result

    def test_empty_package_json(self, tmp_path):
        """Leeres package.json."""
        pkg = tmp_path / "package.json"
        pkg.write_text("{}")
        result = DependencyVersionScanner._parse_package_json(pkg)
        assert result == []

    def test_no_dependencies(self, tmp_path):
        """package.json ohne dependencies Abschnitt."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"name": "test", "version": "1.0.0"}))
        result = DependencyVersionScanner._parse_package_json(pkg)
        assert result == []

    def test_exact_version(self, tmp_path):
        """Exakte Version ohne Präfix."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({
            "dependencies": {"axios": "1.5.0"},
        }))
        result = DependencyVersionScanner._parse_package_json(pkg)
        assert ("axios", "1.5.0") in result

    def test_complex_version_ranges(self, tmp_path):
        """Komplexe SemVer-Ranges."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({
            "dependencies": {
                "next": "14.0.1",
                "qs": "^6.10.0",
                "json5": ">=2.2.0 <2.2.2",
                "immer": ">=9.0.0 <10.0.0",
            },
        }))
        result = DependencyVersionScanner._parse_package_json(pkg)
        print(result)  # noqa: T201
        # Clean extrahiert erste Zahl aus Range
        qs_found = [(p, v) for p, v in result if p == "qs"]
        assert len(qs_found) == 1
        assert qs_found[0][1] == "6.10.0"


class TestParseRequirementsTxt:
    """requirements.txt Parser-Tests."""

    def test_basic_deps(self, tmp_path):
        """package==version Format."""
        req = tmp_path / "requirements.txt"
        req.write_text("django==4.2.9\nrequests==2.30.0\n")
        result = DependencyVersionScanner._parse_requirements_txt(req)
        assert ("django", "4.2.9") in result
        assert ("requests", "2.30.0") in result

    def test_comparison_operators(self, tmp_path):
        """>=, <=, ~= Operatoren."""
        req = tmp_path / "requirements.txt"
        req.write_text(
            "flask>=2.3.0\n"
            "urllib3<=2.0.0\n"
            "aiohttp~=3.8.0\n"
        )
        result = DependencyVersionScanner._parse_requirements_txt(req)
        assert ("flask", "2.3.0") in result
        assert ("urllib3", "2.0.0") in result
        assert ("aiohttp", "3.8.0") in result

    def test_comments_and_options(self, tmp_path):
        """Kommentare und -r Flags ignorieren."""
        req = tmp_path / "requirements.txt"
        req.write_text(
            "# Dies ist ein Kommentar\n"
            "-r base.txt\n"
            "pillow==10.1.0\n"
            "--index-url https://example.com\n"
            "werkzeug==3.0.0\n"
        )
        result = DependencyVersionScanner._parse_requirements_txt(req)
        assert ("pillow", "10.1.0") in result
        assert ("werkzeug", "3.0.0") in result
        assert len(result) == 2

    def test_empty_file(self, tmp_path):
        """Leere Datei."""
        req = tmp_path / "requirements.txt"
        req.write_text("")
        result = DependencyVersionScanner._parse_requirements_txt(req)
        assert result == []

    def test_inline_comments(self, tmp_path):
        """Inline-Kommentare mit #."""
        req = tmp_path / "requirements.txt"
        req.write_text(
            "django==4.2.9  # main framework\n"
            "requests==2.30.0 # HTTP\n"
        )
        result = DependencyVersionScanner._parse_requirements_txt(req)
        assert ("django", "4.2.9") in result
        assert ("requests", "2.30.0") in result

    def test_wildcard_version(self, tmp_path):
        """Wildcard in Version."""
        req = tmp_path / "requirements.txt"
        req.write_text("numpy==1.*\n")
        result = DependencyVersionScanner._parse_requirements_txt(req)
        assert ("numpy", "1.0") in result


class TestParseGoMod:
    """go.mod Parser-Tests."""

    def test_single_require(self, tmp_path):
        """Single-line require."""
        gomod = tmp_path / "go.mod"
        gomod.write_text("module example.com/test\n\ngo 1.21\n\nrequire golang.org/x/net v0.17.0\n")
        result = DependencyVersionScanner._parse_go_mod(gomod)
        assert ("golang.org/x/net", "0.17.0") in result

    def test_require_block(self, tmp_path):
        """Multi-line require block."""
        gomod = tmp_path / "go.mod"
        gomod.write_text(
            "module example.com/test\n\ngo 1.21\n\nrequire (\n"
            "\tgolang.org/x/net v0.16.0\n"
            "\tgolang.org/x/crypto v0.15.0\n"
            ")\n"
        )
        result = DependencyVersionScanner._parse_go_mod(gomod)
        assert ("golang.org/x/net", "0.16.0") in result
        assert ("golang.org/x/crypto", "0.15.0") in result

    def test_incompatible_suffix(self, tmp_path):
        """+incompatible suffix."""
        gomod = tmp_path / "go.mod"
        gomod.write_text(
            "module example.com/test\n\nrequire (\n"
            "\tgithub.com/foo/bar v1.0.0+incompatible\n"
            ")\n"
        )
        result = DependencyVersionScanner._parse_go_mod(gomod)
        assert ("github.com/foo/bar", "1.0.0") in result

    def test_pseudo_version(self, tmp_path):
        """Pseudo-Version mit Datum/Commit."""
        gomod = tmp_path / "go.mod"
        gomod.write_text(
            "module example.com/test\n\nrequire (\n"
            "\tgithub.com/example/pkg v0.0.0-20230101000000-abcdef123456\n"
            ")\n"
        )
        result = DependencyVersionScanner._parse_go_mod(gomod)
        assert ("github.com/example/pkg", "0.0.0") in result

    def test_empty_go_mod(self, tmp_path):
        """Minimales go.mod ohne require."""
        gomod = tmp_path / "go.mod"
        gomod.write_text("module example.com/test\n\ngo 1.21\n")
        result = DependencyVersionScanner._parse_go_mod(gomod)
        assert result == []


class TestParseCargoToml:
    """Cargo.toml Parser-Tests."""

    def test_simple_deps(self, tmp_path):
        """Einfache String-Version."""
        cargo = tmp_path / "Cargo.toml"
        cargo.write_text(
            "[dependencies]\n"
            'serde = "1.0"\n'
            'tokio = "1.19"\n'
        )
        result = DependencyVersionScanner._parse_cargo_toml(cargo)
        assert ("serde", "1.0") in result
        assert ("tokio", "1.19") in result

    def test_table_deps(self, tmp_path):
        """Table-Format mit version und features."""
        cargo = tmp_path / "Cargo.toml"
        cargo.write_text(
            "[dependencies]\n"
            'tokio = { version = "1.19", features = ["full"] }\n'
            'serde = { version = "1.0", default-features = false }\n'
        )
        result = DependencyVersionScanner._parse_cargo_toml(cargo)
        assert ("tokio", "1.19") in result
        assert ("serde", "1.0") in result

    def test_dev_and_build_deps(self, tmp_path):
        """dev-dependencies und build-dependencies."""
        cargo = tmp_path / "Cargo.toml"
        cargo.write_text(
            "[dependencies]\n"
            'serde = "1.0"\n'
            "[dev-dependencies]\n"
            'criterion = "0.5"\n'
            "[build-dependencies]\n"
            'cc = "1.0"\n'
        )
        result = DependencyVersionScanner._parse_cargo_toml(cargo)
        assert ("serde", "1.0") in result
        assert ("criterion", "0.5") in result
        assert ("cc", "1.0") in result

    def test_ignore_other_sections(self, tmp_path):
        """Andere Sections ignorieren."""
        cargo = tmp_path / "Cargo.toml"
        cargo.write_text(
            "[package]\n"
            'name = "test"\n'
            "[dependencies]\n"
            'log = "0.4"\n'
            "[features]\n"
            'default = ["std"]\n'
            "[profile.release]\n"
            'opt-level = 3\n'
        )
        result = DependencyVersionScanner._parse_cargo_toml(cargo)
        assert ("log", "0.4") in result
        assert len(result) == 1

    def test_empty_cargo_toml(self, tmp_path):
        """Keine dependencies Section."""
        cargo = tmp_path / "Cargo.toml"
        cargo.write_text("[package]\nname = \"test\"\nversion = \"0.1.0\"\n")
        result = DependencyVersionScanner._parse_cargo_toml(cargo)
        assert result == []

    def test_inline_table_dep(self, tmp_path):
        """Inline table mit git/version."""
        cargo = tmp_path / "Cargo.toml"
        cargo.write_text(
            "[dependencies]\n"
            'regex = { version = "1.5.4", features = ["unicode"] }\n'
        )
        result = DependencyVersionScanner._parse_cargo_toml(cargo)
        assert ("regex", "1.5.4") in result


# ======================================================================
# Vulnerability Erkennung
# ======================================================================


class TestVulnerabilityDetection:
    """Integrationstests: Erkennung von verwundbaren Versionen."""

    def test_lodash_vulnerable(self, scanner, tmp_path):
        """lodash <4.17.21 → Finding."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({
            "dependencies": {"lodash": "^4.17.20"},
        }))
        findings = scanner.scan(tmp_path)
        assert len(findings) == 1
        f = findings[0]
        assert f["package"] == "lodash"
        assert f["installed_version"] == "4.17.20"
        assert f["severity"] == "critical"
        assert f["ghsa_id"] == "GHSA-4jxc-9g6f-8m6c"
        assert f["manifest_file"] == "package.json"

    def test_lodash_patched(self, scanner, tmp_path):
        """lodash >=4.17.21 → kein Finding."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({
            "dependencies": {"lodash": "^4.17.21"},
        }))
        findings = scanner.scan(tmp_path)
        lodash_findings = [f for f in findings if f["package"] == "lodash"]
        assert len(lodash_findings) == 0

    def test_axios_multiple_vulnerable(self, scanner, tmp_path):
        """Axios in verschiedenen verwundbaren Versionen."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({
            "dependencies": {"axios": "0.21.1"},
        }))
        findings = scanner.scan(tmp_path)
        axios_findings = [f for f in findings if f["package"] == "axios"]
        assert len(axios_findings) == 1
        assert axios_findings[0]["ghsa_id"] == "GHSA-wf5p-g6vw-rhxx"

    def test_axios_safe(self, scanner, tmp_path):
        """Axios in safe Version → kein Finding."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({
            "dependencies": {"axios": "1.6.0"},
        }))
        findings = scanner.scan(tmp_path)
        axios_findings = [f for f in findings if f["package"] == "axios"]
        assert len(axios_findings) == 0

    def test_django_vulnerable_scanner(self, scanner, tmp_path):
        """Django <4.2.10 → Finding (requirements.txt)."""
        req = tmp_path / "requirements.txt"
        req.write_text("django==4.2.9\n")
        findings = scanner.scan(tmp_path)
        django_findings = [f for f in findings if f["package"] == "django"]
        assert len(django_findings) == 1
        assert django_findings[0]["severity"] == "high"
        assert django_findings[0]["cwe"] == "CWE-89"

    def test_django_safe_scanner(self, scanner, tmp_path):
        """Django >=4.2.10 → kein Finding."""
        req = tmp_path / "requirements.txt"
        req.write_text("django==4.2.10\n")
        findings = scanner.scan(tmp_path)
        django_findings = [f for f in findings if f["package"] == "django"]
        assert len(django_findings) == 0

    def test_golang_vulnerable(self, scanner, tmp_path):
        """golang.org/x/net v0.16.0 → Finding (go.mod)."""
        gomod = tmp_path / "go.mod"
        gomod.write_text(
            "module test\n\nrequire (\n"
            "\tgolang.org/x/net v0.16.0\n"
            ")\n"
        )
        findings = scanner.scan(tmp_path)
        net_findings = [f for f in findings if f["package"] == "golang.org/x/net"]
        assert len(net_findings) == 1
        assert net_findings[0]["ghsa_id"] == "GHSA-3j8f-5j4v-9j9c"

    def test_openssl_cargo_vulnerable(self, scanner, tmp_path):
        """openssl <0.10.55 → Finding (Cargo.toml)."""
        cargo = tmp_path / "Cargo.toml"
        cargo.write_text(
            "[dependencies]\n"
            'openssl = "0.10.54"\n'
        )
        findings = scanner.scan(tmp_path)
        openssl_findings = [f for f in findings if f["package"] == "openssl"]
        assert len(openssl_findings) == 1
        assert openssl_findings[0]["ecosystem"] == "cargo"

    def test_mixed_manifests(self, scanner, tmp_path):
        """Mehrere Manifeste in einem Projekt."""
        # package.json mit npm deps
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({
            "dependencies": {"lodash": "^4.17.20"},
        }))
        # requirements.txt mit pypi deps
        req = tmp_path / "requirements.txt"
        req.write_text("django==4.2.9\n")
        # go.mod mit go deps
        gomod = tmp_path / "go.mod"
        gomod.write_text(
            "module test\n\nrequire (\n"
            "\tgolang.org/x/net v0.16.0\n"
            ")\n"
        )

        findings = scanner.scan(tmp_path)
        assert len(findings) == 3

        packages = {f["package"] for f in findings}
        assert "lodash" in packages
        assert "django" in packages
        assert "golang.org/x/net" in packages


# ======================================================================
# Keine falschen Positive
# ======================================================================


class TestNoFalsePositives:
    """Scanner soll keine falschen Positive liefern."""

    def test_no_manifest_found(self, scanner, tmp_path):
        """Keine Manifest-Datei → kein Finding."""
        findings = scanner.scan(tmp_path)
        assert findings == []

    def test_safe_versions_only(self, scanner, tmp_path):
        """Alle Versionen sicher → kein Finding."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({
            "dependencies": {
                "lodash": "^4.17.21",
                "express": "^4.18.1",
                "axios": "^1.6.0",
            },
        }))
        findings = scanner.scan(tmp_path)
        assert findings == []

    def test_unknown_package_is_safe(self, scanner, tmp_path):
        """Unbekanntes Package → kein Finding."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({
            "dependencies": {"my-obscure-pkg": "^1.0.0"},
        }))
        findings = scanner.scan(tmp_path)
        assert findings == []

    def test_empty_dependencies(self, scanner, tmp_path):
        """Leere dependencies → kein Finding."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({
            "dependencies": {},
            "devDependencies": {},
        }))
        findings = scanner.scan(tmp_path)
        assert findings == []


# ======================================================================
# add_vulnerability
# ======================================================================


class TestAddVulnerability:
    """Erweiterung der VULNERABILITIES-Liste."""

    def test_add_single(self, scanner):
        """Hinzufügen einer einzelnen Vulnerability."""
        count_before = len(DependencyVersionScanner.VULNERABILITIES)
        scanner.add_vulnerability(VersionVulnerability(
            package="test-pkg", ecosystem="npm",
            vulnerable_versions=["<1.0.0"], patched_versions=[">=1.0.0"],
            severity="high", title="Test Vulnerability",
            cwe="CWE-999", ghsa_id="GHSA-test-test-test",
        ))
        assert len(DependencyVersionScanner.VULNERABILITIES) == count_before + 1

    def test_add_and_detect(self, scanner, tmp_path):
        """Hinzufügen + Erkennung."""
        scanner.add_vulnerability(VersionVulnerability(
            package="my-pkg", ecosystem="npm",
            vulnerable_versions=["<2.0.0"], patched_versions=[">=2.0.0"],
            severity="high", title="My Custom Vuln",
            cwe="CWE-999", ghsa_id="GHSA-custom-custom-custom",
        ))
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({
            "dependencies": {"my-pkg": "1.0.0"},
        }))
        findings = scanner.scan(tmp_path)
        assert len(findings) == 1
        assert findings[0]["package"] == "my-pkg"
        assert findings[0]["title"] == "My Custom Vuln"


# ======================================================================
# VULNERABILITIES-Liste Validierung
# ======================================================================


class TestVulnerabilitiesList:
    """Validiert die Vollständigkeit der VULNERABILITIES-Liste."""

    def test_count(self):
        """Mindestens 50 Einträge."""
        assert len(DependencyVersionScanner.VULNERABILITIES) >= 50

    def test_all_have_package(self):
        """Jeder Eintrag hat package."""
        for v in DependencyVersionScanner.VULNERABILITIES:
            assert v.package, f"Eintrag fehlt package: {v}"

    def test_all_have_severity(self):
        """Jeder Eintrag hat severity."""
        valid = {"critical", "high", "medium", "low"}
        for v in DependencyVersionScanner.VULNERABILITIES:
            assert v.severity in valid, f"Ungültige severity für {v.package}: {v.severity}"

    def test_all_have_cwe(self):
        """Jeder Eintrag hat cwe."""
        for v in DependencyVersionScanner.VULNERABILITIES:
            assert v.cwe, f"Eintrag fehlt cwe: {v.package}"
            assert v.cwe.startswith("CWE-"), f"cwe format falsch für {v.package}: {v.cwe}"

    def test_all_have_ecosystem(self):
        """Jeder Eintrag hat gültiges ecosystem."""
        valid = {"npm", "pypi", "go", "cargo"}
        for v in DependencyVersionScanner.VULNERABILITIES:
            assert v.ecosystem in valid, f"Ungültiges ecosystem für {v.package}: {v.ecosystem}"

    def test_all_have_ghsa_id(self):
        """Jeder Eintrag hat ghsa_id."""
        for v in DependencyVersionScanner.VULNERABILITIES:
            assert v.ghsa_id, f"Eintrag fehlt ghsa_id: {v.package}"
            assert v.ghsa_id.startswith("GHSA-"), f"ghsa_id format falsch für {v.package}: {v.ghsa_id}"

    def test_all_have_vulnerable_versions(self):
        """Jeder Eintrag hat vulnerable_versions."""
        for v in DependencyVersionScanner.VULNERABILITIES:
            assert len(v.vulnerable_versions) > 0, f"Keine vulnerable_versions für {v.package}"

    def test_all_have_patched_versions(self):
        """Jeder Eintrag hat patched_versions."""
        for v in DependencyVersionScanner.VULNERABILITIES:
            assert len(v.patched_versions) > 0, f"Keine patched_versions für {v.package}"

    def test_unique_packages_per_ecosystem(self):
        """Keine Duplikate (package, ecosystem)."""
        seen = set()
        for v in DependencyVersionScanner.VULNERABILITIES:
            key = (v.package, v.ecosystem)
            assert key not in seen, f"Duplikat: {key}"
            seen.add(key)

    def test_ecosystem_distribution(self):
        """Alle 4 Ökosysteme sind vertreten."""
        ecosystems = {v.ecosystem for v in DependencyVersionScanner.VULNERABILITIES}
        assert "npm" in ecosystems
        assert "pypi" in ecosystems
        assert "go" in ecosystems
        assert "cargo" in ecosystems


# ======================================================================
# scan_as_frameworks
# ======================================================================


class TestScanAsFrameworks:
    """Integration mit DetectedFramework."""

    def test_returns_framework_objects(self, scanner, tmp_path):
        """scan_as_frameworks gibt DetectedFramework-Objekte zurück."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({
            "dependencies": {"lodash": "^4.17.20"},
        }))
        frameworks = scanner.scan_as_frameworks(tmp_path)
        assert len(frameworks) == 1
        fw = frameworks[0]
        assert fw.name == "Prototype Pollution in lodash"
        assert fw.category == "vulnerability"
        assert fw.confidence == "high"
        assert fw.version == "4.17.20"
        assert len(fw.evidence) == 1
        ev = fw.evidence[0]
        assert ev.pattern == "GHSA-4jxc-9g6f-8m6c"
        assert ev.confidence == "high"

    def test_empty_scan_no_frameworks(self, scanner, tmp_path):
        """Keine Vulnerabilities → keine Frameworks."""
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({
            "dependencies": {"lodash": "^4.17.21"},
        }))
        frameworks = scanner.scan_as_frameworks(tmp_path)
        assert frameworks == []


# ======================================================================
# Clean SemVer Helper
# ======================================================================


class TestCleanSemver:
    """SemVer-Bereinigung."""

    def test_caret_prefix(self):
        assert DependencyVersionScanner._clean_semver("^4.17.21") == "4.17.21"

    def test_tilde_prefix(self):
        assert DependencyVersionScanner._clean_semver("~4.17.21") == "4.17.21"

    def test_greater_equal_prefix(self):
        assert DependencyVersionScanner._clean_semver(">=4.17.21") == "4.17.21"

    def test_wildcard(self):
        assert DependencyVersionScanner._clean_semver("1.*") == "1.0"

    def test_or_syntax(self):
        """|| Syntax -> erste Alternative."""
        assert DependencyVersionScanner._clean_semver("^4.0.0 || ^5.0.0") == "4.0.0"

    def test_none_for_empty(self):
        assert DependencyVersionScanner._clean_semver("") is None
        assert DependencyVersionScanner._clean_semver("   ") is None

    def test_exact(self):
        assert DependencyVersionScanner._clean_semver("1.2.3") == "1.2.3"

    def test_three_part(self):
        assert DependencyVersionScanner._clean_semver("0.0.1") == "0.0.1"


# ======================================================================
# Clean Go Version Helper
# ======================================================================


class TestCleanGoVersion:
    """Go-Version-Bereinigung."""

    def test_v_prefix(self):
        assert DependencyVersionScanner._clean_go_version("v0.17.0") == "0.17.0"

    def test_incompatible(self):
        assert DependencyVersionScanner._clean_go_version("v1.0.0+incompatible") == "1.0.0"

    def test_pseudo_version(self):
        assert DependencyVersionScanner._clean_go_version(
            "v0.0.0-20230101000000-abcdef123456",
        ) == "0.0.0"

    def test_no_v_prefix(self):
        assert DependencyVersionScanner._clean_go_version("0.17.0") == "0.17.0"
