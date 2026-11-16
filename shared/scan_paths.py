"""Wo gescannt wird — und wo nicht.

Ein Pattern-Scan ueber die Projektwurzel findet sonst zuerst die Kopien in
``node_modules`` und ``.venv``: beim Bug-Hunt in einem Node-Projekt kamen 41 von
41 Treffern aus ``node_modules/@types/node``. Fremdcode ist kein Fund, er ist
Rauschen — er verstopft den Report und verdraengt die echten Treffer.

Deshalb eine Liste, die beide Scanner benutzen: ``grep_batch`` (als
``--exclude-dir``) und ``regex_scan`` (beim Verzeichnis-Walk). Eine Quelle,
damit die beiden nicht auseinanderlaufen.

Ueberschreibbar per ``SCOUT_SCAN_EXCLUDES`` (kommagetrennt, wird *ergaenzt*),
falls ein Projekt bewusst in ``build/`` oder ``dist/`` sucht.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path

#: Verzeichnisse, die generierten oder fremden Code enthalten.
#: Bewusst konservativ: nur was nachweislich abgeleitet ist (Lockfile-Installation,
#: Build-Ausgabe, Cache) — kein ``docs/`` oder ``examples/``, dort stehen echte
#: Quellen.
EXCLUDE_DIRS: tuple[str, ...] = (
    # Abhaengigkeiten
    "node_modules",
    "bower_components",
    "vendor",
    "site-packages",
    ".venv",
    "venv",
    "env",
    # VCS und Werkzeug-Caches
    ".git",
    ".hg",
    ".svn",
    ".cache",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".tox",
    ".nox",
    ".gradle",
    ".m2",
    "__pycache__",
    # Build-Ausgaben
    "dist",
    "build",
    "out",
    "target",
    "coverage",
    "htmlcov",
    ".next",
    ".nuxt",
    ".svelte-kit",
    ".turbo",
    ".parcel-cache",
    ".terraform",
)

#: Dateien, die nie Quelltext sind.
EXCLUDE_FILE_GLOBS: tuple[str, ...] = (
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "uv.lock",
    "*.pyc",
)

_ENV_VAR = "SCOUT_SCAN_EXCLUDES"


def excluded_dirs() -> tuple[str, ...]:
    """``EXCLUDE_DIRS`` plus optional eigene Eintraege aus der Umgebung."""
    extra = os.environ.get(_ENV_VAR, "")
    custom = tuple(part.strip() for part in extra.split(",") if part.strip())
    return EXCLUDE_DIRS + custom


def build_exclude_flags() -> tuple[str, ...]:
    """``('--exclude-dir', 'node_modules', '--exclude-dir', 'dist', ...)`` fuer grep."""
    flags: list[str] = []
    for name in excluded_dirs():
        flags.extend(["--exclude-dir", name])
    for glob in EXCLUDE_FILE_GLOBS:
        flags.extend(["--exclude", glob])
    return tuple(flags)


def is_excluded_dir(name: str) -> bool:
    """True, wenn ein Verzeichnisname uebersprungen werden soll."""
    return name in excluded_dirs()


def is_excluded_file(name: str) -> bool:
    """True, wenn ein Dateiname (z. B. ``app.min.js``) uebersprungen werden soll."""
    return any(fnmatch.fnmatch(name, glob) for glob in EXCLUDE_FILE_GLOBS)


def iter_source_files(root: str | Path, file_glob: str = ""):
    """Alle Dateien unter ``root``, ohne Fremdcode und ohne Build-Ausgaben.

    ``file_glob`` ist ein Glob wie ``**/*.ts`` oder ``**/*.{ts,tsx}`` — es wird
    nur der Dateinamensteil ausgewertet, die Verzeichnisrekursion macht der Walk.
    """
    patterns = file_patterns(file_glob)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if not is_excluded_dir(name))
        for filename in sorted(filenames):
            if is_excluded_file(filename):
                continue
            if patterns and not any(fnmatch.fnmatch(filename, pattern) for pattern in patterns):
                continue
            yield Path(dirpath) / filename


def file_patterns(file_glob: str) -> tuple[str, ...]:
    """``**/*.{ts,tsx}`` → ``('*.ts', '*.tsx')``; leer → alle Dateien."""
    if not file_glob:
        return ()
    pattern = file_glob.replace("**/", "")
    if "{" in pattern and "}" in pattern:
        prefix, rest = pattern.split("{", 1)
        return tuple(
            f"{prefix}{ext.strip()}"
            for ext in rest.split("}", 1)[0].split(",")
            if ext.strip()
        )
    return (pattern,)
