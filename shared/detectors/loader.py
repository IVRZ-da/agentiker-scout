from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional

from shared.yaml_rule_loader import YamlRuleLoader

from .base import (
    _YAML_DETECTOR_INSTANCE_CACHE,
    DEFAULT_YAML_RULES_DIR,
    DetectedFramework,
    FrameworkEvidence,
    FrameworkProfile,
    _FileIndex,
    _TechDetector,
)
from .catalog import ALL_DETECTORS
from .dependency_data import _DOCKER_IMAGE_MAP, _DOTENV_PREFIXES
from .generic import GenericDependencyDetector

logger = logging.getLogger("scout.framework_detector")


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
        yaml_rules_dir: Optional[str] = None,
        use_yaml_rules: bool = True,
    ):
        self.project_root = Path(project_root).resolve()
        if not self.project_root.is_dir():
            raise ValueError(f"Project root nicht gefunden: {project_root}")

        # Python-Detectors
        py_detectors = custom_detectors if custom_detectors is not None else list(ALL_DETECTORS)

        # YAML-Rules laden und in Detectors konvertieren
        # Nutze get_instance() für Singleton — vermeidet mehrfaches Laden
        self._yaml_loader = YamlRuleLoader.get_instance()
        self._yaml_rules_dir: Optional[str] = None
        if use_yaml_rules:
            rules_dir = yaml_rules_dir or DEFAULT_YAML_RULES_DIR
            if os.path.isdir(rules_dir):
                self._yaml_rules_dir = rules_dir
                yaml_detectors = self._load_yaml_detectors(rules_dir)
                # YAML-Detectors überschreiben Python-Detectors mit gleichem Namen
                self._detectors = self._merge_detectors(yaml_detectors, py_detectors)
            else:
                logger.warning(
                    "YAML-Rules-Verzeichnis nicht gefunden: %s — nur Python-Detectors",
                    rules_dir,
                )
                self._detectors = py_detectors
        else:
            self._detectors = py_detectors

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

        # File-Index einmalig bauen — ersetzt tausende rglob()-Aufrufe
        file_index = _FileIndex(self.project_root)
        _TechDetector._set_file_index(file_index)

        try:
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
        finally:
            # File-Index immer zurücksetzen
            _TechDetector._set_file_index(None)

        # GenericDependencyDetector: alle Dependencies aus package.json/go.mod/... parsen
        # und als DetectedFramework-Einträge hinzufügen (ohne Duplikate)
        existing_names: set = set()
        for fw_list in self._profile.frameworks.values():
            for fw in fw_list:
                existing_names.add(fw.name)

        generic_detector = GenericDependencyDetector()
        generic_results = generic_detector.detect(self.project_root)
        for result in generic_results:
            if result.name not in existing_names:
                cat = result.category
                # categories-Filter respektieren
                if categories and cat not in categories:
                    continue
                if cat not in self._profile.frameworks:
                    self._profile.frameworks[cat] = []
                self._profile.frameworks[cat].append(result)
                existing_names.add(result.name)

        # Dotenv-Scanning (.env.example / .env)
        dotenv_results = self._detect_dotenv(self.project_root)
        for result in dotenv_results:
            if result.name not in existing_names:
                cat = result.category
                if categories and cat not in categories:
                    continue
                if cat not in self._profile.frameworks:
                    self._profile.frameworks[cat] = []
                self._profile.frameworks[cat].append(result)
                existing_names.add(result.name)

        # Docker-Scanning (docker-compose.yml / Dockerfile / compose.yaml)
        docker_results = self._scan_docker_files(self.project_root)
        for result in docker_results:
            if result.name not in existing_names:
                cat = result.category
                if categories and cat not in categories:
                    continue
                if cat not in self._profile.frameworks:
                    self._profile.frameworks[cat] = []
                self._profile.frameworks[cat].append(result)
                existing_names.add(result.name)

        self._compute_confidence()
        return self._profile

    def detect_fast(self) -> FrameworkProfile:
        """Schnelle Erkennung — lädt NUR YAML-Rules (kein Python-Code).

        Überspringt aufwändige rekursive Scans. Gut für schnelle Orientierung.
        Wenn keine YAML-Rules verfügbar sind, fallen alle Detectors durch.
        """
        self._profile = FrameworkProfile(project_root=str(self.project_root))

        # Nur YAML-Rules verwenden (YAML-Detectors stehen vorne in self._detectors)
        # Aber wir müssen wissen wo die Trennlinie ist — nutze yaml_rules_dir als Marker
        if self._yaml_rules_dir:
            yaml_detectors = self._load_yaml_detectors(self._yaml_rules_dir)
            fast_pool = yaml_detectors
        else:
            # Fallback: nur Detectors mit high-confidence Markern
            fast_pool = [d for d in self._detectors if any(
                m[2] == "high" for m in d.markers
            )]

        for detector in fast_pool:
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

    def _load_yaml_detectors(self, rules_dir: str) -> List[_TechDetector]:
        """Lädt YAML-Rules und konvertiert sie in _TechDetector-Objekte (gecached).

        Args:
            rules_dir: Pfad zum YAML-Rules-Verzeichnis

        Returns:
            Liste von _TechDetector-Instanzen (leer bei Fehlern)
        """
        detectors: List[_TechDetector] = []
        try:
            rules = self._yaml_loader.load_all(rules_dir)
            for rule in rules:
                # Cache-Check: bereits konvertierte Detector-Instanz?
                if rule.name in _YAML_DETECTOR_INSTANCE_CACHE:
                    detectors.append(_YAML_DETECTOR_INSTANCE_CACHE[rule.name])  # type: ignore[arg-type]
                    continue
                try:
                    detector = self._yaml_loader.to_detector(rule)
                    _YAML_DETECTOR_INSTANCE_CACHE[rule.name] = detector
                    detectors.append(detector)  # type: ignore[arg-type]
                except Exception as e:
                    logger.debug(
                        "YAML-Rule '%s' konnte nicht konvertiert werden: %s",
                        rule.name, e,
                    )
        except Exception as e:
            logger.warning(
                "YAML-Rules konnten nicht geladen werden: %s", e
            )
        return detectors

    @staticmethod
    def _merge_detectors(
        yaml_detectors: List[_TechDetector],
        py_detectors: List[_TechDetector],
    ) -> List[_TechDetector]:
        """Merged YAML- und Python-Detectors.

        YAML-Detectors überschreiben Python-Detectors mit demselben ``name``.
        Alle Python-Detectors, die kein YAML-Pendant haben, bleiben erhalten.
        Reihenfolge: YAML-Detectors zuerst, dann die restlichen Python-Detectors.

        Returns:
            Kombinierte und deduplizierte Detector-Liste
        """
        yaml_names = {d.name for d in yaml_detectors}
        rest = [d for d in py_detectors if d.name not in yaml_names]
        return yaml_detectors + rest

    @staticmethod
    def _detect_dotenv(root: Path) -> List[DetectedFramework]:
        """Scannt .env.example und .env nach bekannten Variablen-Prefixen.

        Parst KEY=VALUE Paare und matched bekannte Prefixe gegen
        die _DOTENV_PREFIXES-Map.

        Args:
            root: Projekt-Root-Verzeichnis

        Returns:
            Liste von DetectedFramework-Objekten
        """
        results: List[DetectedFramework] = []
        seen: set = set()

        for env_file in (".env.example", ".env"):
            fpath = root / env_file
            if not fpath.exists():
                continue
            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue

                key = line.split("=", 1)[0].strip()
                if not key:
                    continue

                # Check known prefixes (longest prefix wins)
                matched = None
                matched_prefix = ""
                for prefix, (category, name) in _DOTENV_PREFIXES.items():
                    if key.startswith(prefix) and len(prefix) > len(matched_prefix):
                        matched = (category, name)
                        matched_prefix = prefix

                if matched is not None and matched[1] not in seen:
                    category, name = matched
                    seen.add(name)
                    fw = DetectedFramework(
                        name=name,
                        category=category,
                        confidence="medium",
                        evidence=[
                            FrameworkEvidence(
                                source=env_file,
                                pattern=key,
                                confidence="medium",
                            )
                        ],
                    )
                    results.append(fw)

        return results

    @staticmethod
    def _scan_docker_files(root: Path) -> List[DetectedFramework]:
        """Scannt Dockerfiles und docker-compose.yml nach bekannten Images.

        Parst docker-compose.yml/compose.yaml ``services`` auf ``image:``
        Einträge und Dockerfile ``FROM`` Statements.

        Args:
            root: Projekt-Root-Verzeichnis

        Returns:
            Liste von DetectedFramework-Objekten
        """
        results: List[DetectedFramework] = []
        seen: set = set()

        # 1. docker-compose.yml / compose.yaml — parse `image:` entries
        for compose_file in ("docker-compose.yml", "docker-compose.yaml", "compose.yaml"):
            fpath = root / compose_file
            if not fpath.exists():
                continue
            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for line in content.splitlines():
                stripped = line.strip()
                if not stripped.startswith("image:"):
                    continue
                img = stripped[len("image:"):].strip().strip('"').strip("'")
                if not img:
                    continue
                # Extract base image name (before tag)
                base = img.split(":")[0] if ":" in img else img
                base_lower = base.split("/")[-1].lower() if "/" in base else base.lower()

                if base_lower in _DOCKER_IMAGE_MAP and base_lower not in seen:
                    category, name = _DOCKER_IMAGE_MAP[base_lower]
                    seen.add(base_lower)
                    version = img.split(":")[1] if ":" in img else None
                    fw = DetectedFramework(
                        name=name,
                        category=category,
                        confidence="high",
                        version=version,
                        evidence=[
                            FrameworkEvidence(
                                source=compose_file,
                                pattern=f"image: {img}",
                                confidence="high",
                                version=version,
                            )
                        ],
                    )
                    results.append(fw)

        # 2. Dockerfile — parse FROM statements
        for df_name in ("Dockerfile",):
            df_path = root / df_name
            if not df_path.exists():
                continue
            try:
                content = df_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for line in content.splitlines():
                stripped = line.strip()
                upper = stripped.upper()
                if not upper.startswith("FROM "):
                    continue
                img = stripped[len("FROM "):].strip()
                # Strip AS alias
                as_idx = upper.find(" AS ")
                if as_idx != -1:
                    img = img[:as_idx].strip()
                if not img:
                    continue
                base = img.split(":")[0] if ":" in img else img
                base_lower = base.split("/")[-1].lower() if "/" in base else base.lower()

                if base_lower in _DOCKER_IMAGE_MAP and base_lower not in seen:
                    category, name = _DOCKER_IMAGE_MAP[base_lower]
                    seen.add(base_lower)
                    version = img.split(":")[1] if ":" in img else None
                    fw = DetectedFramework(
                        name=name,
                        category=category,
                        confidence="high",
                        version=version,
                        evidence=[
                            FrameworkEvidence(
                                source=df_name,
                                pattern=f"FROM {img}",
                                confidence="high",
                                version=version,
                            )
                        ],
                    )
                    results.append(fw)

        return results
