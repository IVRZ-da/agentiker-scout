"""shared/paths.py — eine Wahrheit fuer alle Nutzdaten-Pfade des Plugins.

Warum
-----
Nutzdaten (Sessions, Recherche-Ergebnisse, Custom-Patterns) gehoerten bisher
in das Plugin-Verzeichnis (``bughunt/data/``, ``research/data/``). Folgen:

* ein Plugin-Update ueberschreibt oder verwirrt Nutzdaten,
* Backups muessen Code und Daten auseinanderhalten,
* Tests schrieben in die echten Datenverzeichnisse (ueber 1000 Leichen).

Deshalb liegt alles Nutzdaten-Zeug jetzt in ``~/.hermes/data/scout`` — neben den
Daten der anderen Plugins, nicht im Code-Repo.

Ueberschreiben
--------------
``SCOUT_DATA_DIR`` setzen, um ein anderes Wurzelverzeichnis zu nutzen. Tests
und ``scripts/run_evals.py`` tun genau das, damit sie nichts Echtes anfassen.

Versionierte Ausnahme
---------------------
``bughunt/data/patterns_data.json`` (die 69 Built-in-Patterns) ist *Code*, kein
Nutzdatenverzeichnis. Sie bleibt im Plugin und wird hier bewusst nicht angefasst.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger("scout.paths")

PLUGIN_DIR = Path(__file__).resolve().parent.parent

#: Umgebungsvariable, die das Wurzelverzeichnis fuer Nutzdaten ueberschreibt.
ENV_DATA_DIR = "SCOUT_DATA_DIR"


def resolve_data_root() -> Path:
    """Wurzelverzeichnis fuer alle Nutzdaten (Env > XDG-Default)."""
    raw = os.environ.get(ENV_DATA_DIR, "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / ".hermes" / "data" / "scout").resolve()


# Beim Import aufgeloest, damit Import-Zeit-Konstanten in den Domain-Modulen
# funktionieren. Wer zur Laufzeit umschalten will, setzt die Env-Variable vor
# dem Import (so machen es conftest.py und scripts/run_evals.py) oder ruft
# reload_paths().
DATA_ROOT: Path = resolve_data_root()

# Bug-Hunt
BUGHUNT_DIR: Path = DATA_ROOT / "bughunt"
SESSIONS_DIR: Path = BUGHUNT_DIR / "sessions"
PATTERNS_DIR: Path = BUGHUNT_DIR / "patterns"
CUSTOM_PATTERNS_FILE: Path = PATTERNS_DIR / "custom_patterns.json"

# Research
RESEARCH_DIR: Path = DATA_ROOT / "research"
PLANS_DIR: Path = RESEARCH_DIR / "plans"
RESULTS_DIR: Path = RESEARCH_DIR / "results"
RESEARCH_TRACKER_FILE: Path = RESEARCH_DIR / "_tracker.json"

# Analysis
ANALYSIS_DIR: Path = DATA_ROOT / "analysis"


def _all_dirs() -> tuple[Path, ...]:
    """Aktuelle Verzeichnisliste — bewusst berechnet, nicht als Modul-Konstante.

    Eine Konstante wuerde die Pfade beim Import einfrieren; nach
    ``reload_paths()`` haette ``ensure_dirs()`` dann die alten Verzeichnisse
    angelegt und die neuen gefehlt.
    """
    return (
        BUGHUNT_DIR,
        SESSIONS_DIR,
        PATTERNS_DIR,
        RESEARCH_DIR,
        PLANS_DIR,
        RESULTS_DIR,
        ANALYSIS_DIR,
    )


def ensure_dirs() -> list[Path]:
    """Legt alle Nutzdatenverzeichnisse an. Gibt die angelegten Pfade zurueck."""
    created: list[Path] = []
    for path in _all_dirs():
        try:
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)
        except OSError as exc:  # pragma: no cover - nur bei kaputten Rechten
            logger.warning("scout: konnte %s nicht anlegen: %s", path, exc)
    return created


def describe() -> dict[str, str]:
    """Aktuelle Pfadbelegung — fuer Diagnose und ``--show-paths``."""
    return {
        "data_root": str(DATA_ROOT),
        "sessions": str(SESSIONS_DIR),
        "custom_patterns": str(CUSTOM_PATTERNS_FILE),
        "research_plans": str(PLANS_DIR),
        "research_results": str(RESULTS_DIR),
        "analysis": str(ANALYSIS_DIR),
        "plugin_dir": str(PLUGIN_DIR),
    }


#: Attributname -> Pfad. Basis fuer reload_paths() und fuer das Nachziehen von
#: Modulen, die die Konstanten per ``from x import y`` kopiert haben.
PATH_ATTRS = (
    "DATA_ROOT",
    "BUGHUNT_DIR",
    "SESSIONS_DIR",
    "PATTERNS_DIR",
    "CUSTOM_PATTERNS_FILE",
    "RESEARCH_DIR",
    "PLANS_DIR",
    "RESULTS_DIR",
    "RESEARCH_TRACKER_FILE",
    "ANALYSIS_DIR",
)


def reload_paths() -> dict[str, Path]:
    """Alles neu aus der Env-Variable aufloesen (Wurzel + abgeleitete Pfade).

    Wird von Tests und ``scripts/run_evals.py`` genutzt, wenn die Umschaltung
    erst nach dem Import erfolgt. Module, die die Konstanten kopiert haben,
    muessen ihre Attribute danach selbst nachziehen — deshalb gibt es
    ``PATH_ATTRS`` als Namensliste.
    """
    global DATA_ROOT, BUGHUNT_DIR, SESSIONS_DIR, PATTERNS_DIR, CUSTOM_PATTERNS_FILE
    global RESEARCH_DIR, PLANS_DIR, RESULTS_DIR, RESEARCH_TRACKER_FILE, ANALYSIS_DIR

    DATA_ROOT = resolve_data_root()
    BUGHUNT_DIR = DATA_ROOT / "bughunt"
    SESSIONS_DIR = BUGHUNT_DIR / "sessions"
    PATTERNS_DIR = BUGHUNT_DIR / "patterns"
    CUSTOM_PATTERNS_FILE = PATTERNS_DIR / "custom_patterns.json"
    RESEARCH_DIR = DATA_ROOT / "research"
    PLANS_DIR = RESEARCH_DIR / "plans"
    RESULTS_DIR = RESEARCH_DIR / "results"
    RESEARCH_TRACKER_FILE = RESEARCH_DIR / "_tracker.json"
    ANALYSIS_DIR = DATA_ROOT / "analysis"

    return {name: globals()[name] for name in PATH_ATTRS}
