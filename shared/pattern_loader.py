r"""Bug-Pattern Loader — Schwester-Loader zu YamlRuleLoader.

Lädt Bug-Patterns aus YAML-Dateien (data/patterns/), validiert sie
und stellt sie als BugPattern-Objekte bereit.

YAML-Format:
    ```yaml
    - id: OWASP-01
      cwe: CWE-20
      category: security
      severity: critical
      languages: [typescript, javascript, python, go]
      title: Fehlende Input-Validierung
      scan_query: 'express\.(post|put|patch)\(.*req\.body'
      fix_description: "req.body vor Verwendung mit Zod/Yup validieren"
      confidence: high
    ```

Usage:
    loader = PatternLoader.get_instance()
    all_patterns = loader.load_all()
    security = loader.get_by_category("security")
    py_patterns = loader.get_by_language("python")
    pat = loader.get_by_id("OWASP-01")
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("scout.pattern_loader")

# ---------------------------------------------------------------------------
# Valid values
# ---------------------------------------------------------------------------

VALID_SEVERITIES = frozenset({"critical", "high", "medium", "low", "info"})
VALID_CONFIDENCES = frozenset({"high", "medium", "low"})

# Bekannte Sprachen für Validierungs-Warnungen.
# Unbekannte Sprachen werden trotzdem geladen (nur Warnung).
KNOWN_LANGUAGES = frozenset({
    "python", "javascript", "typescript", "go", "rust", "java", "kotlin",
    "swift", "ruby", "php", "csharp", "cpp", "c", "scala", "sql",
    "bash", "shell", "dockerfile", "yaml", "json", "html", "css",
    "terraform", "hcl", "lua", "r", "dart", "elixir", "haskell",
    "clojure", "solidity", "vue", "svelte", "jsx", "tsx",
})

CWE_PATTERN = re.compile(r"^CWE-\d+$")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class BugPattern:
    """Ein einzelnes Bug-Pattern.

    Attributes:
        id: Eindeutige Pattern-ID (z.B. ``OWASP-01``, ``TS-001``)
        cwe: CWE-Nummer im Format ``CWE-XXXX``
        category: Kategorie (z.B. ``security``, ``code-quality``)
        severity: Schweregrad (critical | high | medium | low | info)
        languages: Liste der betroffenen Sprachen
        title: Kurzbeschreibung
        scan_query: Such-Query für den Scanner
        fix_description: Beschreibung der empfohlenen Korrektur
        confidence: Konfidenz (high | medium | low)
    """
    id: str
    cwe: str
    category: str
    severity: str
    languages: List[str]
    title: str
    scan_query: str
    fix_description: str
    confidence: str

    def __post_init__(self) -> None:
        errors: List[str] = []

        if not self.id:
            errors.append("id fehlt")
        if not self.scan_query:
            errors.append("scan_query fehlt")
        if self.severity not in VALID_SEVERITIES:
            errors.append(
                f"Ungültiges severity '{self.severity}'. "
                f"Erlaubt: {', '.join(sorted(VALID_SEVERITIES))}"
            )
        if self.confidence not in VALID_CONFIDENCES:
            errors.append(
                f"Ungültiges confidence '{self.confidence}'. "
                f"Erlaubt: {', '.join(sorted(VALID_CONFIDENCES))}"
            )
        if self.cwe and not CWE_PATTERN.match(self.cwe):
            errors.append(
                f"Ungültiges CWE-Format '{self.cwe}'. Erwartet: CWE-XXXX"
            )

        if errors:
            raise ValueError(
                f"BugPattern '{self.id or '?'}': {'; '.join(errors)}"
            )


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class PatternLoader:
    """Lädt, validiert und cached Bug-Patterns aus YAML-Dateien.

    Fehlertolerant — einzelne kaputte YAML-Dateien oder invalide Einträge
    brechen nicht den gesamten Ladevorgang. Nutzt Singleton (get_instance()).
    """

    _instance: Optional['PatternLoader'] = None

    def __init__(self, patterns_dir: str = "data/patterns") -> None:
        self.patterns_dir = patterns_dir
        self._patterns: List[BugPattern] = []
        self._by_category: Dict[str, List[BugPattern]] = {}
        self._by_language: Dict[str, List[BugPattern]] = {}
        self._by_id: Dict[str, BugPattern] = {}
        self._loaded = False

    # ── Singleton ────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> 'PatternLoader':
        """Gibt die Singleton-Instanz zurück. Erzeugt sie bei Bedarf."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Public API ───────────────────────────────────────────────────

    def load_all(self) -> List[BugPattern]:
        """Lädt alle Bug-Patterns aus dem patterns_dir (rekursiv).

        Ist Thread-safe nach dem ersten Laden. Verwendet einen _loaded-Flag
        für schnelle Cached-Abfragen.

        Returns:
            Liste aller validen BugPattern-Objekte
        """
        if self._loaded:
            return list(self._patterns)

        self._patterns = []
        self._by_category = {}
        self._by_language = {}
        self._by_id = {}
        seen_ids: Dict[str, str] = {}  # id -> file (für Duplikat-Warnung)

        patterns_path = Path(self.patterns_dir).resolve()

        if not patterns_path.is_dir():
            logger.warning("Patterns-Verzeichnis nicht gefunden: %s", self.patterns_dir)
            self._loaded = True
            return []

        yaml_files = sorted(patterns_path.rglob("*.yaml")) + sorted(patterns_path.rglob("*.yml"))

        for yaml_path in yaml_files:
            try:
                file_patterns = self._load_file(yaml_path, seen_ids)
                self._patterns.extend(file_patterns)
            except Exception as e:
                logger.warning(
                    "Fehler beim Laden von %s: %s — übersprungen",
                    yaml_path.name, e,
                )

        # Deduplizieren: bei doppelten IDs behalten wir den letzten Eintrag
        seen_pos: Dict[str, int] = {}
        for i, pat in enumerate(self._patterns):
            seen_pos[pat.id] = i  # letztes Vorkommen gewinnt
        keep = set(seen_pos.values())
        self._patterns = [p for i, p in enumerate(self._patterns) if i in keep]

        # Indizes bauen
        for pat in self._patterns:
            self._by_category.setdefault(pat.category, []).append(pat)
            self._by_id[pat.id] = pat
            for lang in pat.languages:
                self._by_language.setdefault(lang, []).append(pat)

        self._loaded = True
        return list(self._patterns)

    def get_by_category(self, category: str) -> List[BugPattern]:
        """Alle Patterns einer bestimmten Kategorie.

        Args:
            category: Kategorie-Name (z.B. ``security``, ``code-quality``)

        Returns:
            Liste der BugPatterns dieser Kategorie (leer wenn keine)
        """
        self.load_all()
        return list(self._by_category.get(category, []))

    def get_by_language(self, lang: str) -> List[BugPattern]:
        """Alle Patterns für eine bestimmte Sprache.

        Args:
            lang: Sprache (z.B. ``python``, ``typescript``)

        Returns:
            Liste der BugPatterns für diese Sprache (leer wenn keine)
        """
        self.load_all()
        return list(self._by_language.get(lang, []))

    def get_by_id(self, pid: str) -> Optional[BugPattern]:
        """Ein Pattern anhand seiner ID.

        Args:
            pid: Pattern-ID (z.B. ``OWASP-01``)

        Returns:
            BugPattern oder None, wenn nicht gefunden
        """
        self.load_all()
        return self._by_id.get(pid)

    def filter(
        self,
        categories: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        severities: Optional[List[str]] = None,
        min_confidence: str = "low",
    ) -> List[BugPattern]:
        """Patterns nach mehreren Kriterien filtern.

        Alle Kriterien sind optional. Werden mehrere angegeben,
        müssen alle zutreffen (AND-Verknüpfung).

        Args:
            categories: Nur Patterns dieser Kategorien (None = alle)
            languages: Nur Patterns für diese Sprachen (None = alle)
            severities: Nur Patterns mit diesem Severity (None = alle)
            min_confidence: Mindest-Konfidenz (``low``, ``medium``, ``high``)

        Returns:
            Gefilterte Liste der BugPatterns
        """
        self.load_all()
        confidence_rank = {"low": 0, "medium": 1, "high": 2}
        min_rank = confidence_rank.get(min_confidence, 0)

        results: List[BugPattern] = []
        for pat in self._patterns:
            if categories and pat.category not in categories:
                continue
            if languages and not any(l in languages for l in pat.languages):  # noqa: E741
                continue
            if severities and pat.severity not in severities:
                continue
            if confidence_rank.get(pat.confidence, 0) < min_rank:
                continue
            results.append(pat)
        return results

    # ── Internals ────────────────────────────────────────────────────

    def _load_file(
        self,
        yaml_path: Path,
        seen_ids: Dict[str, str],
    ) -> List[BugPattern]:
        """Lädt und validiert Patterns aus einer einzelnen YAML-Datei."""
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)

        if not raw:
            return []

        if not isinstance(raw, list):
            raise ValueError(
                f"YAML-Formatfehler: erwartete Liste von Patterns, "
                f"bekam {type(raw).__name__}"
            )

        patterns: List[BugPattern] = []
        for i, entry in enumerate(raw):
            if not isinstance(entry, dict):
                logger.warning(
                    "Eintrag %d in %s ist kein Dict — übersprungen",
                    i, yaml_path.name,
                )
                continue
            try:
                pattern = self._parse_entry(entry, yaml_path, seen_ids)
                if pattern is not None:
                    patterns.append(pattern)
            except (ValueError, KeyError) as e:
                logger.warning(
                    "Eintrag %d in %s: %s — übersprungen",
                    i, yaml_path.name, e,
                )
        return patterns

    def _parse_entry(
        self,
        entry: dict,
        yaml_path: Path,
        seen_ids: Dict[str, str],
    ) -> Optional[BugPattern]:
        """Parst einen einzelnen Pattern-Eintrag aus dem YAML-Dict.

        Returns:
            BugPattern oder None bei Überspringen (z.B. fehlende Pflichtfelder)
        """
        pid = entry.get("id", "")
        scan_query = entry.get("scan_query", "")

        # Pflichtfelder prüfen
        if not pid:
            logger.warning(
                "Eintrag in %s: fehlende id — übersprungen", yaml_path.name,
            )
            return None
        if not scan_query:
            logger.warning(
                "Pattern '%s' in %s: scan_query ist leer — übersprungen",
                pid, yaml_path.name,
            )
            return None

        # Duplikat-Prüfung
        if pid in seen_ids:
            logger.warning(
                "Duplikat-ID '%s' in %s (schon gesehen in %s) — "
                "letzter Eintrag gewinnt",
                pid, yaml_path.name, seen_ids[pid],
            )
        seen_ids[pid] = yaml_path.name

        cwe = str(entry.get("cwe", ""))
        category = str(entry.get("category", "default"))
        severity = str(entry.get("severity", "medium"))
        title = str(entry.get("title", ""))
        fix_description = str(entry.get("fix_description", ""))
        confidence = str(entry.get("confidence", "medium"))

        raw_languages = entry.get("languages", [])
        if not isinstance(raw_languages, list):
            raw_languages = [str(raw_languages)]
        languages: List[str] = [str(l) for l in raw_languages]  # noqa: E741

        # Warnung bei unbekannter Sprache (trotzdem laden)
        for lang in languages:
            if lang not in KNOWN_LANGUAGES:
                logger.warning(
                    "Pattern '%s' in %s: unbekannte Sprache '%s' — wird trotzdem geladen",
                    pid, yaml_path.name, lang,
                )

        # CWE-Format prüfen (wenn gesetzt)
        if cwe and not CWE_PATTERN.match(cwe):
            logger.warning(
                "Pattern '%s' in %s: ungültiges CWE-Format '%s' — übersprungen",
                pid, yaml_path.name, cwe,
            )
            return None

        # Severity prüfen
        if severity not in VALID_SEVERITIES:
            logger.warning(
                "Pattern '%s' in %s: ungültiges severity '%s' — übersprungen",
                pid, yaml_path.name, severity,
            )
            return None

        # Confidence prüfen
        if confidence not in VALID_CONFIDENCES:
            logger.warning(
                "Pattern '%s' in %s: ungültiges confidence '%s' — übersprungen",
                pid, yaml_path.name, confidence,
            )
            return None

        return BugPattern(
            id=pid,
            cwe=cwe,
            category=category,
            severity=severity,
            languages=languages,
            title=title,
            scan_query=scan_query,
            fix_description=fix_description,
            confidence=confidence,
        )

    def clear(self) -> None:
        """Leert den internen Cache. Nächstes load_all() lädt neu."""
        self._patterns = []
        self._by_category = {}
        self._by_language = {}
        self._by_id = {}
        self._loaded = False

    @staticmethod
    def reset_singleton() -> None:
        """Setzt die Singleton-Instanz zurück (für Tests)."""
        PatternLoader._instance = None
