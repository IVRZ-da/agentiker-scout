"""YAML-based Rule Engine for Framework Detection.

Lädt YAML-Regeln aus data/rules/, validiert sie und wandelt sie
in _TechDetector-kompatible Objekte um.

Usage:
    loader = YamlRuleLoader()
    rules = loader.load_all("/path/to/data/rules")
    for rule in rules:
        detector = loader.to_detector(rule)
        result = detector.detect(Path(project_root))
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger("scout.yaml_rule_loader")

# ---------------------------------------------------------------------------
# Valid categories
# ---------------------------------------------------------------------------
VALID_CATEGORIES = frozenset({
    "backend", "frontend", "ui_library", "database", "language",
    "testing", "infra", "ci", "package_manager",
})

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class YamlMarker:
    """Ein einzelner Marker in einer YAML-Regel.

    Attributes:
        file: Datei-Glob (z.B. ``package.json``, ``**/*.py``)
        search: Suchpattern (String oder Regex). Leer = reine Existenzprüfung.
        confidence: ``high`` | ``medium`` | ``low``
    """
    file: str
    search: str = ""
    confidence: str = "high"

    def __post_init__(self) -> None:
        if self.confidence not in ("high", "medium", "low"):
            raise ValueError(
                f"Ungültiges confidence '{self.confidence}' für {self.file}. "
                f"Erlaubt: high, medium, low"
            )


@dataclass
class YamlRule:
    """Eine einzelne YAML-Detection-Rule.

    Attributes:
        name: Technologie-Name (z.B. ``nextjs``, ``react``)
        category: Kategorie aus VALID_CATEGORIES
        markers: Liste von Datei-/Pattern-Markern
        version_hint: Optionaler Regex zur Version-Extraktion
    """
    name: str
    category: str
    markers: List[YamlMarker] = field(default_factory=list)
    version_hint: str = ""

    def __post_init__(self) -> None:
        errors: List[str] = []
        if not self.name:
            errors.append("name fehlt")
        if not self.category:
            errors.append("category fehlt")
        elif self.category not in VALID_CATEGORIES:
            errors.append(
                f"Ungültige category '{self.category}'. "
                f"Erlaubt: {', '.join(sorted(VALID_CATEGORIES))}"
            )
        if not self.markers:
            errors.append("markers-Liste ist leer oder fehlt")
        if errors:
            raise ValueError(f"Rule '{self.name or '?'}': {'; '.join(errors)}")

    def to_marker_tuples(self) -> List[Tuple[str, str, str]]:
        """Wandelt die Marker in das (file, search, confidence)-Tupel-Format um.

        Dieses Format wird von ``_TechDetector.detect()`` erwartet.
        """
        return [(m.file, m.search, m.confidence) for m in self.markers]


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class YamlRuleLoader:
    """Lädt, validiert und cached YAML-Detection-Rules aus einem Verzeichnis.

    Thread-safe (nach erstmaligem Laden). Fehlertolerant — einzelne kaputte
    YAML-Dateien brechen nicht den gesamten Ladevorgang.

    Nutzt Singleton-Pattern (get_instance()) für Performance.
    """

    _instance: Optional['YamlRuleLoader'] = None
    # Cache für to_detector() — vermeidet wiederholte type()-Aufrufe
    _detector_cache: Dict[str, object] = {}

    def __init__(self) -> None:
        # Cache: rules_dir -> {"by_category": {cat: [YamlRule, ...]}, "all": [YamlRule, ...]}
        self._cache: Dict[str, Dict] = {}

    @classmethod
    def get_instance(cls) -> 'YamlRuleLoader':
        """Gibt die Singleton-Instanz zurück. Erzeugt sie bei Bedarf."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Public API ──────────────────────────────────────────────────

    def load_all(
        self,
        rules_dir: str,
        force_reload: bool = False,
    ) -> List[YamlRule]:
        """Lädt ALLE YAML-Rules aus dem Verzeichnis (rekursiv).

        Args:
            rules_dir: Pfad zum Rule-Verzeichnis (z.B. ``data/rules/``)
            force_reload: Wenn True, Cache ignorieren und neu laden

        Returns:
            Liste aller validen YamlRules
        """
        cache_key = os.path.abspath(rules_dir)
        if not force_reload and cache_key in self._cache:
            return list(self._cache[cache_key]["all"])

        rules = self._load_directory(rules_dir)
        # Nach Kategorie sortieren
        by_cat: Dict[str, List[YamlRule]] = {}
        for rule in rules:
            by_cat.setdefault(rule.category, []).append(rule)

        self._cache[cache_key] = {"by_category": by_cat, "all": rules}
        return rules

    def load_by_category(
        self,
        rules_dir: str,
        category: str,
        force_reload: bool = False,
    ) -> List[YamlRule]:
        """Lädt alle Rules einer bestimmten Kategorie.

        Args:
            rules_dir: Pfad zum Rule-Verzeichnis
            category: Kategorie aus VALID_CATEGORIES
            force_reload: Cache umgehen

        Returns:
            Liste der YamlRules in dieser Kategorie (leer wenn keine)
        """
        # load_all cached, also rufen wir sie auf
        self.load_all(rules_dir, force_reload=force_reload)
        cache_key = os.path.abspath(rules_dir)
        return list(self._cache[cache_key]["by_category"].get(category, []))

    def to_detector(self, rule: YamlRule) -> object:
        """Erzeugt ein ``_TechDetector``-ähnliches Objekt aus einer YamlRule (gecached).

        Das zurückgegebene Objekt hat die Attribute ``name``, ``category``,
        ``markers`` und die Methode ``detect(root)``, die mit dem
        existierenden ``_TechDetector.detect()`` kompatibel ist.

        Results werden in ``_detector_cache`` gecached — bei wiederholtem
        Aufruf mit derselben Rule wird die bereits erzeugte Instanz
        zurückgegeben (vermeidet teure ``type()``-Aufrufe).

        Args:
            rule: Eine validierte YamlRule

        Returns:
            Ein Objekt mit ``_TechDetector``-Interface
        """
        if rule.name in self._detector_cache:
            return self._detector_cache[rule.name]

        from shared.framework_detector import _TechDetector

        markers = rule.to_marker_tuples()

        cls = type(
            f"_Yaml_{rule.name}",
            (_TechDetector,),
            {
                "name": rule.name,
                "category": rule.category,
                "markers": markers,
                "_version_regex": rule.version_hint,
            },
        )
        instance = cls()
        self._detector_cache[rule.name] = instance
        return instance

    # ── Internals ───────────────────────────────────────────────────

    def _load_directory(self, rules_dir: str) -> List[YamlRule]:
        """Lädt alle .yaml/.yml Dateien aus dem Verzeichnis rekursiv."""
        rules: List[YamlRule] = []
        rules_path = Path(rules_dir).resolve()

        if not rules_path.is_dir():
            logger.warning("Rules-Verzeichnis nicht gefunden: %s", rules_dir)
            return rules

        yaml_files = sorted(rules_path.rglob("*.yaml")) + sorted(rules_path.rglob("*.yml"))

        for yaml_path in yaml_files:
            try:
                file_rules = self._load_file(yaml_path)
                rules.extend(file_rules)
            except Exception as e:
                logger.warning(
                    "Fehler beim Laden von %s: %s — übersprungen",
                    yaml_path.name, e,
                )

        return rules

    def _load_file(self, yaml_path: Path) -> List[YamlRule]:
        """Lädt und validiert Rules aus einer einzelnen YAML-Datei."""
        with open(yaml_path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)

        if not raw:
            return []

        if not isinstance(raw, list):
            raise ValueError(
                f"YAML-Formatfehler: erwartete Liste von Rules, "
                f"bekam {type(raw).__name__}"
            )

        rules: List[YamlRule] = []
        for i, entry in enumerate(raw):
            if not isinstance(entry, dict):
                logger.warning(
                    "Eintrag %d in %s ist kein Dict — übersprungen",
                    i, yaml_path.name,
                )
                continue
            try:
                rule = self._parse_entry(entry)
                rules.append(rule)
            except (ValueError, KeyError) as e:
                logger.warning(
                    "Eintrag %d in %s: %s — übersprungen",
                    i, yaml_path.name, e,
                )
        return rules

    def _parse_entry(self, entry: dict) -> YamlRule:
        """Parst einen einzelnen Rule-Eintrag aus dem YAML-Dict."""
        name = entry.get("name", "")
        category = entry.get("category", "")

        raw_markers = entry.get("markers", [])
        markers: List[YamlMarker] = []
        for j, m in enumerate(raw_markers):
            if isinstance(m, dict):
                markers.append(YamlMarker(
                    file=m.get("file", ""),
                    search=m.get("search", ""),
                    confidence=m.get("confidence", "high"),
                ))
            elif isinstance(m, (list, tuple)):
                # Fallback: (file, search, confidence) als Liste
                if len(m) >= 2:
                    markers.append(YamlMarker(
                        file=m[0],
                        search=m[1] if len(m) > 1 else "",
                        confidence=m[2] if len(m) > 2 else "high",
                    ))
                else:
                    logger.warning(
                        "Marker #%d hat zu wenige Elemente — übersprungen", j
                    )
            else:
                logger.warning(
                    "Marker #%d ist weder dict noch list — übersprungen", j
                )

        return YamlRule(
            name=name,
            category=category,
            markers=markers,
            version_hint=str(entry.get("version_hint", "")),
        )

    def clear_cache(self) -> None:
        """Leert den internen Cache."""
        self._cache.clear()
