"""Ein grep fuer viele Patterns.

Der Scan-Runner startete bisher pro Pattern einen eigenen ``grep``-Prozess ueber
das gesamte Projekt — bei 32 grep-Patterns also 32 vollstaendige Dateibaum-
Durchlaeufe. Diese Datei gruppiert Patterns nach ihrem ``--include``-Glob, baut
eine Alternation und laesst grep **einmal pro Gruppe** laufen; die Zuordnung
Treffer→Pattern passiert danach in Python.

Damit gibt es genau eine grep-Implementierung, die sowohl BugHunt als auch die
Analysis-Pattern nutzen.
"""
from __future__ import annotations

import logging
import re
import subprocess

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60
#: Ab dieser Laenge wird die Alternation aufgeteilt (ARG_MAX und Lesbarkeit).
MAX_PATTERN_CHARS = 6000


def build_include_flags(file_glob: str) -> tuple[str, ...]:
    """Uebersetzt ``**/*.{ts,tsx}`` in grep-``--include``-Flags."""
    if not file_glob:
        return ()

    pattern = file_glob.replace("**/", "")
    if "{" in pattern and "}" in pattern:
        prefix, rest = pattern.split("{", 1)
        extensions = rest.split("}", 1)[0].split(",")
        flags: list[str] = []
        for ext in extensions:
            ext = ext.strip()
            if ext:
                flags.extend(["--include", f"{prefix}{ext}"])
        return tuple(flags)

    return ("--include", pattern)


_GREP_LINE = re.compile(r"^(?P<file>.+?):(?P<line>\d+):(?P<content>.*)$")


def _parse_grep_line(line: str) -> dict | None:
    """``pfad:zeile:inhalt`` → dict.

    Regex statt ``split(":")``: Pfade duerfen Doppelpunkte enthalten, und der
    Inhalt auch — nur die erste ``:zahl:``-Folge trennt.
    """
    match = _GREP_LINE.match(line)
    if match is None:
        return None
    return {
        "file": match.group("file"),
        "line": int(match.group("line")),
        "match": match.group("content").strip()[:300],
    }


def _chunks(patterns: list[dict], limit: int = MAX_PATTERN_CHARS) -> list[list[dict]]:
    """Teilt Patterns so auf, dass die Alternation handhabbar bleibt."""
    groups: list[list[dict]] = []
    current: list[dict] = []
    size = 0
    for pattern in patterns:
        length = len(pattern["scan_query"]) + 5
        if current and size + length > limit:
            groups.append(current)
            current, size = [], 0
        current.append(pattern)
        size += length
    if current:
        groups.append(current)
    return groups


def _run_grep(cmd: list[str], timeout: int) -> list[str] | None:
    """Fuehrt grep aus. ``None`` bedeutet: grep hat den Ausdruck abgelehnt."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        logger.warning("grep batch timeout nach %ds", timeout)
        return []
    except FileNotFoundError:
        logger.warning("grep nicht gefunden")
        return []
    except OSError as exc:
        logger.warning("grep batch fehlgeschlagen: %s", exc)
        return []

    if proc.returncode == 2:
        # Syntaxfehler in mindestens einem Pattern — der Aufrufer muss einzeln
        # nachfassen, sonst verlieren die anderen Patterns ihre Treffer.
        logger.debug("grep Syntaxfehler: %s", (proc.stderr or "")[:200])
        return None
    if proc.returncode not in (0, 1):  # 1 = keine Treffer, kein Fehler
        logger.warning("grep exit %d: %s", proc.returncode, (proc.stderr or "")[:200])
        return []
    return proc.stdout.splitlines()


def grep_batch(
    patterns: list[dict],
    project_root: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, list[dict]]:
    """Fuehrt alle grep-Patterns in moeglichst wenigen Subprozessen aus.

    Args:
        patterns: Dicts mit ``pattern_id`` und ``scan_query``, optional
            ``scan_file_glob``.
        project_root: Projektwurzel.
        timeout: Zeitlimit pro grep-Aufruf.

    Returns:
        ``{pattern_id: [{file, line, match}, ...]}`` — Patterns ohne Treffer
        fehlen im Ergebnis nicht zwangslaeufig, sie haben dann eine leere Liste.
    """
    results: dict[str, list[dict]] = {}
    usable: list[dict] = []
    compiled: dict[str, re.Pattern] = {}

    for pattern in patterns:
        pattern_id = pattern.get("pattern_id") or pattern.get("id") or ""
        query = pattern.get("scan_query") or ""
        if not pattern_id or not query:
            continue
        try:
            compiled[pattern_id] = re.compile(query)
        except re.error as exc:
            # Patterns sind grep-Regexe (BRE/ERE), nicht Python-Regexe: "eval(" ist
            # dort gueltig, hier nicht. Statt das Pattern zu verlieren, ordnen wir
            # Treffer ueber den Literal-Text zu.
            logger.debug("Pattern %s: kein Python-Regex (%s) — Literal-Fallback",
                         pattern_id, exc)
            compiled[pattern_id] = re.compile(re.escape(query))
        results.setdefault(pattern_id, [])
        usable.append({**pattern, "pattern_id": pattern_id})

    if not usable:
        return results

    # Gruppen: gleiche --include-Flags teilen sich einen grep-Lauf
    by_glob: dict[tuple[str, ...], list[dict]] = {}
    for pattern in usable:
        flags = build_include_flags(pattern.get("scan_file_glob", ""))
        by_glob.setdefault(flags, []).append(pattern)

    for flags, group in by_glob.items():
        for chunk in _chunks(group):
            # Bewusst kein "-E": die Patterns sind BRE (grep ohne -E geschrieben),
            # dort ist "eval(" ein Literal. Mit -E waere es ein Syntaxfehler und
            # wuerde den ganzen Batch kippen. Mehrere -e erhalten die Semantik
            # jedes einzelnen Patterns und brauchen trotzdem nur einen Prozess.
            cmd = ["grep", "-rnI", *flags]
            for pattern in chunk:
                cmd.extend(["-e", pattern["scan_query"]])
            cmd.append(project_root)
            logger.debug("grep batch: %d Patterns", len(chunk))

            lines = _run_grep(cmd, timeout)
            if lines is None:
                # Ein Pattern im Chunk ist fuer grep ungueltig: einzeln nachfassen,
                # damit die uebrigen nicht leer ausgehen.
                for pattern in chunk:
                    single = ["grep", "-rnI", *flags, "-e", pattern["scan_query"], project_root]
                    single_lines = _run_grep(single, timeout) or []
                    logger.debug("grep Einzellauf %s: %d Zeilen",
                                 pattern["pattern_id"], len(single_lines))
                    _assign(single_lines, [pattern], compiled, results)
                continue

            _assign(lines, chunk, compiled, results)

    return results


def _assign(
    lines: list[str],
    chunk: list[dict],
    compiled: dict[str, re.Pattern],
    results: dict[str, list[dict]],
) -> None:
    """Ordnet grep-Ausgabezeilen den Patterns zu, die darauf passen."""
    for line in lines:
        parsed = _parse_grep_line(line)
        if parsed is None:
            continue
        for pattern in chunk:
            matcher = compiled[pattern["pattern_id"]]
            if matcher.search(parsed["match"]) or matcher.search(line):
                results[pattern["pattern_id"]].append(parsed)
