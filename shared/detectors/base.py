"""Framework Detection Engine — Automatische Tech-Stack-Erkennung.

Erkennt den gesamten Technologie-Stack eines Projekts durch Analyse von
package.json, go.mod, Cargo.toml, requirements.txt, Config-Dateien,
Ordnerstruktur und CI/CD-Konfiguration. Inspiriert von specfy/stack-analyser.

Usage:
    detector = FrameworkDetector("/path/to/project")
    result = detector.detect()
    logger.info("Detected frameworks: %s", result.frameworks)
    logger.info("Detection confidence: %s", result.confidence)
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("scout.framework_detector")

# ---------------------------------------------------------------------------
# Module-level caches (für Performance)
# ---------------------------------------------------------------------------

# Cache für kompilierte Glob-Regexe — vermeidet wiederholte re.compile() Aufrufe
_GLOB_REGEX_CACHE: Dict[str, re.Pattern] = {}

# Cache für YAML->TechDetector Instanzen — vermeidet wiederholte type()-Aufrufe
_YAML_DETECTOR_INSTANCE_CACHE: Dict[str, object] = {}

# ---------------------------------------------------------------------------
# Default-Verzeichnis für YAML-Detection-Rules (relativ zum Plugin-Root)
# ---------------------------------------------------------------------------
DEFAULT_YAML_RULES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "rules",
)

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
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "project_root": self.project_root,
            "frameworks": {
                cat: [fw.to_dict() for fw in fw_list]
                for cat, fw_list in self.frameworks.items()
            },
            "overall_confidence": self.overall_confidence,
            "errors": self.errors,
            "metadata": self.metadata,
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
# File Index — Single-Scan Index für alle Dateien im Projekt
# ---------------------------------------------------------------------------


class _FileIndex:
    """Einmaliger Projekt-File-Index. Alle Dateien einmal scannen,
    dann nur noch im Index suchen — ersetzt tausende rglob()-Aufrufe."""

    def __init__(self, root: Path, ignored: Optional[set] = None):
        self._root = root
        self._ignored: set = ignored or {
            "node_modules", ".git", "__pycache__", ".venv", "venv",
            ".next", "dist", "build", ".medusa", ".cache", "target",
        }
        # rel_path → Path
        self._files: Dict[str, Path] = {}
        # filename → [rel_paths]
        self._by_name: Dict[str, List[str]] = {}
        # extension → [rel_paths]  (z.B. ".py" → ["a.py", "src/b.py"])
        self._by_ext: Dict[str, List[str]] = {}
        self._build()

    def _build(self) -> None:
        """Scannt das Projekt rekursiv und baut den Index auf."""
        for root_str, dirs, files in os.walk(str(self._root)):
            # Ignorierte Verzeichnisse aus dem Walk entfernen (Performance!)
            dirs[:] = [d for d in dirs if d not in self._ignored]

            root = Path(root_str)
            for fname in files:
                fpath = root / fname
                try:
                    rel = str(fpath.relative_to(self._root))
                except ValueError:
                    continue
                self._files[rel] = fpath
                self._by_name.setdefault(fname, []).append(rel)
                ext = fpath.suffix.lower()
                self._by_ext.setdefault(ext, []).append(rel)

    def find(self, glob_pattern: str) -> List[Tuple[str, Path]]:
        """Findet Dateien passend zum Glob-Pattern im Index.

        Nutzt Fast-Paths für die häufigsten Pattern-Typen,
        fällt auf Regex-Match über alle Dateien zurück.
        """
        # Fast Path 1: Exakter Dateiname (kein Wildcard) → O(1) by_name lookup
        if "*" not in glob_pattern and "?" not in glob_pattern:
            name = Path(glob_pattern).name
            results: List[Tuple[str, Path]] = []
            for rel in self._by_name.get(name, []):
                # Exakter Match oder Pfad-Endung (z.B. "config/app.ts")
                if glob_pattern == rel or rel.endswith("/" + glob_pattern):
                    results.append((rel, self._files[rel]))
            return results

        # Fast Path 2: Nur Extension wie "*.py" → O(k) by_ext lookup
        if glob_pattern.startswith("*.") and "/" not in glob_pattern:
            ext = glob_pattern[1:]  # ".py"
            results = []
            for rel in self._by_ext.get(ext, []):
                results.append((rel, self._files[rel]))
            return results

        # Fast Path 3: Rekursive Extension wie "**/*.py", "**/*.tsx"
        if glob_pattern.startswith("**/*"):
            rest = glob_pattern[4:]
            if rest.startswith("."):
                ext = rest
                results = []
                for rel in self._by_ext.get(ext, []):
                    results.append((rel, self._files[rel]))
                return results

        # Slow Path: Regex-Match über alle Dateien
        regex = _compile_glob(glob_pattern)
        results = []
        for rel, fpath in self._files.items():
            if regex.match(rel):
                results.append((rel, fpath))
        return results


def _compile_glob(glob_pat: str) -> re.Pattern:
    """Wandelt Globs in Regex um (mit Cache).

    Unterstützt:
      - **/ für rekursive Suche
      - * für einzelne Segmente
      - ? für single chars
    """
    cached = _GLOB_REGEX_CACHE.get(glob_pat)
    if cached is not None:
        return cached

    # **/ durch rekursiven Pfad-Matcher ersetzen
    parts = glob_pat.split("**/")
    if len(parts) > 1:
        regex_parts = []
        for part in parts:
            if not part:
                continue
            escaped = re.escape(part)
            escaped = escaped.replace(r"\*", "[^/]*").replace(r"\?", ".")
            regex_parts.append(escaped)
        prefix = "(.*/)?" if glob_pat.startswith("**/") else ""
        suffix = "/?".join(regex_parts)
        regex_str = "^" + prefix + suffix + "$"
    else:
        parts = glob_pat.split("*")
        regex_str = "^" + re.escape(parts[0]) if parts else "^"
        for p in parts[1:]:
            regex_str += "[^/]*" + re.escape(p)
        regex_str += "$"

    compiled = re.compile(regex_str)
    _GLOB_REGEX_CACHE[glob_pat] = compiled
    return compiled


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

    # Globaler File-Index (wird von FrameworkDetector.detect() gesetzt)
    _global_file_index: Optional[_FileIndex] = None

    @classmethod
    def _set_file_index(cls, idx: Optional[_FileIndex]) -> None:
        """Setzt den globalen File-Index für alle Detector-Instanzen."""
        cls._global_file_index = idx

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
        """Findet Dateien die zu einem Glob passen — schnell und ohne node_modules.

        Nutzt den globalen File-Index wenn verfügbar (viel schneller als rglob).
        """
        # Fast Path: File-Index verwenden wenn gesetzt (→ kein rglob!)
        if self._global_file_index is not None:
            return self._global_file_index.find(file_glob)

        # Fallback: Original rglob-Logik (für detect_fast ohne Index)
        results: List[Tuple[str, Path]] = []
        pattern_re = self._glob_to_regex(file_glob)

        # Für feste Dateinamen (kein wildcard): direkter exist-Check
        if "*" not in file_glob:
            fpath = root / file_glob
            if fpath.exists() and fpath.is_file():
                results.append((file_glob, fpath))
            return results

        # Für Pattern mit Pfad-Tiefe: rglob mit depth-Limit
        parts = file_glob.split("/")
        leaf_part = parts[-1] if parts else file_glob

        if leaf_part.startswith("*"):
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
            depth = rel.count(os.sep)
            if depth > scan_depth:
                continue
            if pattern_re.match(rel):
                results.append((rel, fpath))

        return results

    @staticmethod
    def _glob_to_regex(glob_pat: str) -> re.Pattern:
        """Wandelt einfache File-Globs in Regex um (mit Cache).

        Delegiert an die modulare _compile_glob() Funktion, die
        Ergebnisse in _GLOB_REGEX_CACHE cached.
        """
        return _compile_glob(glob_pat)

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
