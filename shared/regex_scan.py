"""Python-Regex-Scans fuer Patterns, die grep nicht abbilden kann.

Warum es das gibt: ``grep`` laeuft in BRE und ohne ``(?x)``; viele Security-Muster
brauchen aber Freiraum (Kommentare, verschachtelte Alternativen, ``\\s*``-Ketzer).
Ein Muster wie "Secret-Zuweisung, aber kein Variablenverweis" ist als BRE nicht
mehr lesbar und als Python-Regex ein Zweizeiler.

Deshalb ein eigener ``scan_type: "regex"``: dieselben Patterns wie ``grep``,
gleiche Ergebnisform ``{pattern_id: [{file, line, match}]}``, gleiche
Verzeichnisausschluesse (``scan_paths``) — nur ausgewertet in Python.

Grenzen sind Pflicht, sonst haengt ein Scan an einem 200-MB-Bundle: pro Datei
wird nur bis ``MAX_FILE_BYTES`` gelesen, Binaerdateien werden uebersprungen, und
pro Pattern gibt es eine Obergrenze an Treffern.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from scout.shared.scan_paths import file_patterns, iter_source_files

logger = logging.getLogger(__name__)

#: Groessere Dateien sind generiert oder Daten — nicht scannen.
MAX_FILE_BYTES = 1_000_000
#: Obergrenze pro Pattern, damit ein einzelnes Rauschmuster den Report nicht flutet.
MAX_MATCHES_PER_PATTERN = 200
#: Laenge des Evidence-Texts pro Treffer.
MAX_MATCH_CHARS = 300

#: ``scan_flags``-Buchstaben → re-Flags. ``m`` ist immer an.
_FLAG_MAP = {
    "i": re.IGNORECASE,
    "m": re.MULTILINE,
    "s": re.DOTALL,
    "x": re.VERBOSE,
}


def compile_flags(scan_flags: str | None) -> int:
    """Uebersetzt ``scan_flags`` (z. B. ``"im"``) in ``re``-Flags."""
    flags = re.MULTILINE
    for letter in scan_flags or "":
        flags |= _FLAG_MAP.get(letter.lower(), 0)
    return flags


def _read_text(path: Path) -> str | None:
    """Datei als Text lesen; ``None`` bei Binaerinhalt, zu gross oder IO-Fehler."""
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        raw = path.read_bytes()
    except OSError as exc:
        logger.debug("regex_scan: %s nicht lesbar (%s)", path, exc)
        return None
    if b"\x00" in raw[:8192]:
        return None
    return raw.decode("utf-8", errors="replace")


def regex_batch(
    patterns: list[dict],
    project_root: str,
    max_matches: int = MAX_MATCHES_PER_PATTERN,
) -> dict[str, list[dict]]:
    """Fuehrt alle ``scan_type=regex``-Patterns in einem Dateibaum-Durchlauf aus.

    Args:
        patterns: Dicts mit ``pattern_id``, ``scan_query`` (Python-Regex),
            optional ``scan_file_glob`` und ``scan_flags``.
        project_root: Projektwurzel.
        max_matches: Obergrenze an Treffern pro Pattern.

    Returns:
        ``{pattern_id: [{file, line, match}, ...]}`` — Patterns ohne Treffer
        stehen mit leerer Liste drin.
    """
    results: dict[str, list[dict]] = {}
    usable: list[tuple[dict, re.Pattern]] = []

    for pattern in patterns:
        pattern_id = pattern.get("pattern_id") or pattern.get("id") or ""
        query = (pattern.get("scan_query") or "").strip()
        if not pattern_id or not query:
            continue
        try:
            matcher = re.compile(query, compile_flags(pattern.get("scan_flags")))
        except re.error as exc:
            # Ein kaputtes Muster darf die anderen nicht mitreissen.
            logger.warning("regex_scan: Pattern %s ungueltig (%s)", pattern_id, exc)
            results.setdefault(pattern_id, [])
            continue
        results.setdefault(pattern_id, [])
        usable.append(({**pattern, "pattern_id": pattern_id}, matcher))

    if not usable:
        return results

    # Ein Walk fuer alle Patterns; Datei-Globs unterscheiden sich, also pro Datei
    # gegen die Glob-Liste des jeweiligen Patterns pruefen.
    globs = {item[0]["pattern_id"]: _glob_matcher(item[0].get("scan_file_glob", "")) for item in usable}

    for path in iter_source_files(project_root):
        text = _read_text(path)
        if text is None:
            continue
        for pattern, matcher in usable:
            pattern_id = pattern["pattern_id"]
            if len(results[pattern_id]) >= max_matches:
                continue
            glob_check = globs[pattern_id]
            if glob_check is not None and not glob_check(path.name):
                continue
            for match in matcher.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                evidence = " ".join(match.group(0).split())[:MAX_MATCH_CHARS]
                results[pattern_id].append({
                    "file": str(path),
                    "line": line,
                    "match": evidence,
                })
                if len(results[pattern_id]) >= max_matches:
                    logger.info("regex_scan: %s bei %d Treffern abgeschnitten",
                                pattern_id, max_matches)
                    break

    return results


def _glob_matcher(file_glob: str):
    """Dateinamens-Filter aus einem Glob; ``None`` = alle Dateien."""
    from fnmatch import fnmatch

    patterns = file_patterns(file_glob)
    if not patterns:
        return None
    return lambda name: any(fnmatch(name, pattern) for pattern in patterns)
