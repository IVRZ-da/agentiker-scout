from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from .base import DetectedFramework, FrameworkEvidence
from .dependency_data import (
    _GO_PREFIXES,
    _KNOWN_PREFIXES,
    _TOP_CARGO,
    _TOP_GO,
    _TOP_NPM,
    _TOP_PYPI,
    _lookup_category,
)


class GenericDependencyDetector:
    """Extrahiert Framework-Informationen aus Package-Manager Dateien.

    Parst automatisch dependencies/devDependencies aus package.json,
    require aus go.mod, dependencies aus Cargo.toml, etc.
    """

    def detect(self, root: Path) -> List[DetectedFramework]:
        """Führt die generische Dependency-Erkennung durch.

        Args:
            root: Projekt-Root-Verzeichnis

        Returns:
            Liste von DetectedFramework-Objekten für alle gefundenen Dependencies
        """
        results: List[DetectedFramework] = []

        # Nur existierende Dateien prüfen (kein rglob)
        pkg_json = root / "package.json"
        go_mod = root / "go.mod"
        req_txt = root / "requirements.txt"
        cargo_toml = root / "Cargo.toml"

        if pkg_json.exists():
            results.extend(self._parse_package_json(pkg_json))

        if go_mod.exists():
            results.extend(self._parse_go_mod(go_mod))

        if req_txt.exists():
            results.extend(self._parse_requirements_txt(req_txt))

        if cargo_toml.exists():
            results.extend(self._parse_cargo_toml(cargo_toml))

        return results

    def _parse_package_json(self, path: Path) -> List[DetectedFramework]:
        """Parst package.json und erzeugt DetectedFramework-Einträge."""
        results: List[DetectedFramework] = []
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except (json.JSONDecodeError, Exception):
            return results

        all_deps: Dict[str, str] = {}
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            deps = data.get(key, {})
            if isinstance(deps, dict):
                all_deps.update(deps)

        for name, version_spec in all_deps.items():
            category = _lookup_category(name, _TOP_NPM, _KNOWN_PREFIXES)
            if category:
                confidence = "high" if name in _TOP_NPM else "medium"
            else:
                category = "other"
                confidence = "low"

            fw = DetectedFramework(
                name=name,
                category=category,
                confidence=confidence,
                version=self._clean_version(version_spec),
                evidence=[
                    FrameworkEvidence(
                        source="package.json",
                        pattern=name,
                        confidence=confidence if category != "other" else "low",
                        version=self._clean_version(version_spec),
                    )
                ],
            )
            results.append(fw)

        return results

    def _parse_requirements_txt(self, path: Path) -> List[DetectedFramework]:
        """Parst requirements.txt und erzeugt DetectedFramework-Einträge."""
        results: List[DetectedFramework] = []
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return results

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # Extract package name (handle ==, >=, <=, ~=, !=)
            match = re.match(r"^([a-zA-Z0-9_][a-zA-Z0-9_.-]*?)\s*[<>=!~]+\s*", line)
            if match:
                name = match.group(1).lower()
                version_spec = line[match.end():].strip()
            else:
                name = line.lower()
                version_spec = ""

            category = _lookup_category(name, _TOP_PYPI, _KNOWN_PREFIXES)
            if category:
                confidence = "high" if name in _TOP_PYPI else "medium"
            else:
                category = "other"
                confidence = "low"

            fw = DetectedFramework(
                name=name,
                category=category,
                confidence=confidence,
                version=self._clean_version(version_spec),
                evidence=[
                    FrameworkEvidence(
                        source="requirements.txt",
                        pattern=name,
                        confidence=confidence if category != "other" else "low",
                        version=self._clean_version(version_spec),
                    )
                ],
            )
            results.append(fw)

        return results

    def _parse_go_mod(self, path: Path) -> List[DetectedFramework]:
        """Parst go.mod und erzeugt DetectedFramework-Einträge."""
        results: List[DetectedFramework] = []
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return results

        in_require = False
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("require ("):
                in_require = True
                continue
            if in_require and line == ")":
                in_require = False
                continue
            if in_require:
                # Format: package/path version
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    version_spec = parts[1]
                else:
                    continue
            elif line.startswith("require "):
                # Single-line require: require package/path version
                rest = line[len("require "):].strip()
                parts = rest.split()
                if len(parts) >= 2:
                    name = parts[0]
                    version_spec = parts[1]
                else:
                    continue
            else:
                continue

            category = _lookup_category(name, _TOP_GO, _GO_PREFIXES)
            if category:
                confidence = "high" if name in _TOP_GO else "medium"
            else:
                category = "other"
                confidence = "low"

            fw = DetectedFramework(
                name=name,
                category=category,
                confidence=confidence,
                version=self._clean_version(version_spec),
                evidence=[
                    FrameworkEvidence(
                        source="go.mod",
                        pattern=name,
                        confidence=confidence if category != "other" else "low",
                        version=self._clean_version(version_spec),
                    )
                ],
            )
            results.append(fw)

        return results

    def _parse_cargo_toml(self, path: Path) -> List[DetectedFramework]:
        """Parst Cargo.toml und erzeugt DetectedFramework-Einträge."""
        results: List[DetectedFramework] = []
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return results

        in_dependencies = False
        in_dev_dependencies = False
        in_build_dependencies = False
        for line in content.splitlines():
            stripped = line.strip()

            # Section headers
            if stripped.startswith("[dependencies"):
                in_dependencies = True
                in_dev_dependencies = False
                in_build_dependencies = False
                continue
            if stripped.startswith("[dev-dependencies"):
                in_dependencies = False
                in_dev_dependencies = True
                in_build_dependencies = False
                continue
            if stripped.startswith("[build-dependencies"):
                in_dependencies = False
                in_dev_dependencies = False
                in_build_dependencies = True
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                in_dependencies = False
                in_dev_dependencies = False
                in_build_dependencies = False
                continue

            if not stripped or stripped.startswith("#"):
                continue

            if in_dependencies or in_dev_dependencies or in_build_dependencies:
                # Parse: name = "version" or name = { version = "...", ... }
                dep_match = re.match(r'^([a-zA-Z0-9_-]+)\s*=\s*"(.*?)"', stripped)
                if dep_match:
                    name = dep_match.group(1)
                    version_spec = dep_match.group(2)
                else:
                    # Complex form: name = { version = "...", ... }
                    dep_match = re.match(
                        r'^([a-zA-Z0-9_-]+)\s*=\s*\{', stripped
                    )
                    if dep_match:
                        name = dep_match.group(1)
                        # Try to extract version
                        ver_match = re.search(
                            r'version\s*=\s*"(.*?)"', line
                        )
                        version_spec = ver_match.group(1) if ver_match else ""
                    else:
                        continue

                category = _lookup_category(name, _TOP_CARGO, {})
                if category:
                    confidence = "high" if name in _TOP_CARGO else "medium"
                else:
                    category = "other"
                    confidence = "low"

                fw = DetectedFramework(
                    name=name,
                    category=category,
                    confidence=confidence,
                    version=self._clean_version(version_spec),
                    evidence=[
                        FrameworkEvidence(
                            source="Cargo.toml",
                            pattern=name,
                            confidence=confidence if category != "other" else "low",
                            version=self._clean_version(version_spec),
                        )
                    ],
                )
                results.append(fw)

        return results

    @staticmethod
    def _clean_version(version_spec: str) -> Optional[str]:
        """Bereinigt einen Version-String (entfernt ^ ~ >= etc.)."""
        if not version_spec:
            return None
        # Remove common prefixes
        cleaned = re.sub(r'^[\^~>=<!]+\s*', '', version_spec.strip())
        # Take first version-like token
        ver_match = re.search(r'\d+\.\d+\.\d+', cleaned)
        if ver_match:
            return ver_match.group(0)
        ver_match = re.search(r'\d+\.\d+', cleaned)
        if ver_match:
            return ver_match.group(0)
        return cleaned[:20] if cleaned else None
