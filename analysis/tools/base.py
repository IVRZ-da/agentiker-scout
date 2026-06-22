"""tools/base.py — Basis-Helper für Analyse-Tools."""
from __future__ import annotations

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("analysis")



_TRAVERSAL_PATTERN = re.compile(
    r"(?:^|/|\\)\.{2,}(?:/|\\)|"
    r"(?:%2e%2e|%252e%252e|\\\\.\\.)", re.IGNORECASE
)

# Ungültige Zeichen in Pfaden
_INVALID_PATH_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _validate_path(path: str) -> Optional[str]:
    """Validiert einen Pfad-Parameter auf Sicherheitsrisiken.

    Prüft:
      - Path-Traversal (../, ..\\, URL-kodiert)
      - Null-Bytes und Steuerzeichen
      - Symlink-Escapes (via realpath Vergleich)
      - Länge (>4096 Zeichen)

    Returns:
        None wenn gültig, Fehler-String wenn ungültig.
    """
    if not path or not isinstance(path, str):
        return "Path is empty or not a string"

    if len(path) > 4096:
        return f"Path too long ({len(path)} chars, max 4096)"

    # Null-Bytes und Steuerzeichen
    if _INVALID_PATH_CHARS.search(path):
        return "Path contains control characters or null bytes"

    # Path-Traversal
    if _TRAVERSAL_PATTERN.search(path):
        return f"Path traversal detected in: {path[:100]}"

    # Absolute Pfade müssen existieren
    if os.path.isabs(path):
        try:
            resolved = os.path.realpath(path)
            # Sicherstellen dass resolved nicht auf unerwartete Ziele zeigt
            if not resolved.startswith("/"):
                return f"Path resolves to non-absolute location: {resolved}"
            # Symlink-Check: Prüfen ob realpath stark vom original abweicht
            orig_normalized = os.path.normpath(path)
            if resolved != orig_normalized and not orig_normalized.startswith(
                ("/proc/", "/sys/", "/dev/")
            ):
                logger.debug(
                    "path resolves differently: %s → %s", orig_normalized, resolved
                )
        except (OSError, ValueError) as e:
            return f"Path resolution error: {e}"

    return None


def _validate_and_resolve_path(path: str) -> Tuple[Optional[str], str]:
    """Validiert und resolved einen Pfad.

    Returns:
        Tuple aus (error_message, resolved_absolute_path).
        Bei Erfolg: (None, resolved_absolute_path).
        Bei Fehler: (error_string, resolved_path) — resolved_path ist nur
        für type-safety als str deklariert, bei Fehler nicht nutzen.
    """
    error = _validate_path(path)
    if error:
        return error, path  # path als Fallback, wird bei error ignoriert

    # Zu absolutem Pfad auflösen
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)

    resolved = os.path.realpath(path)
    return None, resolved


# ---------------------------------------------------------------------------
# Helper: code-intel Tool-Aufrufe
# ---------------------------------------------------------------------------

# Max Timeout pro Tool-Call (Sekunden). Kann via env var überschrieben werden.
_DEFAULT_TOOL_TIMEOUT = int(os.environ.get("ANALYSIS_TOOL_TIMEOUT", "120"))

# Thread-Pool für Timeout-fähige Tool-Dispatches (ein Thread)
_timeout_executor = ThreadPoolExecutor(max_workers=1)

# Thread-Pool für parallele Tool-Dispatches (mehrere Threads)
_parallel_executor = ThreadPoolExecutor(max_workers=4)


def _call_tool(name: str, timeout: int = _DEFAULT_TOOL_TIMEOUT, **kwargs: Any) -> Any:
    """Ruft ein Tool aus dem globalen Registry auf.

    Nutzt tools.registry für den Dispatch — das funktioniert sowohl
    mit Built-in- als auch mit Plugin-Tools (code_intel, etc.).

    Args:
        name: Tool-Name (z.B. "code_symbols")
        timeout: Timeout in Sekunden (Default: 120, via env ANALYSIS_TOOL_TIMEOUT)
        **kwargs: Tool-Argumente

    Returns:
        Tool-Ergebnis (dict/list/str) oder {"error": ...} bei Fehler/Timeout.
    """
    try:
        from tools.registry import registry

        # Dispatch in Thread mit Timeout
        future = _timeout_executor.submit(registry.dispatch, name, kwargs)
        try:
            result = future.result(timeout=timeout)
        except FuturesTimeout:
            logger.warning("tool call %s timed out after %ds", name, timeout)
            return {"error": f"timeout after {timeout}s", "tool": name}

        if isinstance(result, str):
            try:
                return json.loads(result)
            except (json.JSONDecodeError, TypeError):
                return result
        return result
    except Exception as e:
        logger.warning("tool call %s failed: %s", name, e)
        return {"error": str(e), "tool": name}


# ---------------------------------------------------------------------------
# Shared Pattern Integration (P3)
# ---------------------------------------------------------------------------

def _run_shared_pattern_scans(
    path: str,
    kinds: Optional[List[str]] = None,
    scan_language: str = "",
) -> Dict[str, Any]:
    """Führt Shared Patterns (auto_analysis=True) gegen einen Pfad aus.

    Lädt Patterns aus ~/.hermes/patterns/shared_patterns.json und führt
    grep für jedes Pattern mit scan_type="grep" aus.

    Args:
        path: Absoluter Pfad zum Projekt-Root
        kinds: Filter auf analysis_kinds (z.B. ["security"], ["code-quality"])
        scan_language: Optionaler Sprach-Filter

    Returns:
        Dict mit "pattern_matches" (Liste) und "patterns_scanned" (count)
    """
    from scout.shared.patterns import get_patterns_for_analysis

    patterns = get_patterns_for_analysis(scan_language=scan_language)

    # Filter auf analysis_kinds
    if kinds:
        filtered = []
        for p in patterns:
            pk = p.get("analysis_kinds", [])
            if isinstance(pk, str):
                pk = [pk]
            if any(k in pk for k in kinds):
                filtered.append(p)
        patterns = filtered

    matches = []
    for p in patterns:
        scan_query = p.get("scan_query", "")
        scan_file_glob = p.get("scan_file_glob", "")
        if not scan_query:
            continue

        try:
            import subprocess
            # grep bauen
            grep_cmd = ["grep", "-rn"]
            if scan_file_glob:
                grep_cmd.extend(["--include", scan_file_glob])
            grep_cmd.append(scan_query)
            grep_cmd.append(path)

            result = subprocess.run(
                grep_cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split("\n")[:20]:
                    parts = line.split(":", 2)
                    if len(parts) >= 2:
                        matches.append({
                            "pattern_id": p.get("pattern_id", "?"),
                            "pattern_name": p.get("name", "?"),
                            "severity": p.get("severity", "P2"),
                            "category": p.get("category", ""),
                            "file": parts[0],
                            "line": parts[1],
                            "evidence": parts[2] if len(parts) > 2 else "",
                            "fix_description": p.get("fix_description", ""),
                        })
                # Auto-Enrichment: match_count incrementieren (P5)
                try:
                    from scout.shared.patterns import increment_match_count
                    increment_match_count(p["pattern_id"])
                except Exception as e:
                    logger.debug("increment_match_count failed for %s: %s", p.get("pattern_id", "?"), e)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.debug("shared pattern scan skipped for %s: %s",
                         p.get("pattern_id"), e)

    return {
        "pattern_matches": matches,
        "patterns_scanned": len(patterns),
    }


def _parallel_dispatch(
    calls: List[Dict[str, Any]],
    timeout: int = _DEFAULT_TOOL_TIMEOUT,
) -> Dict[str, Any]:
    """Führt mehrere unabhängige Tool-Calls parallel aus.

    Args:
        calls: Liste von Dicts mit {"key": result_key, "name": tool_name, "kwargs": {...}}
        timeout: Timeout pro Call (Default: 120s)

    Returns:
        Dict mit keys → Ergebnisse (inkl. "key_error" bei Fehlern).
    """
    try:
        from tools.registry import registry
    except ImportError:
        logger.warning("tools.registry nicht verfügbar — _parallel_dispatch fällt aus")
        return {}

    results: Dict[str, Any] = {}
    futures = {}

    for call in calls:
        key = call["key"]
        name = call["name"]
        kwargs = call.get("kwargs", {})
        future = _parallel_executor.submit(registry.dispatch, name, kwargs)
        futures[future] = (key, name)

    for future in futures:
        key, name = futures[future]
        try:
            result = future.result(timeout=timeout)
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except (json.JSONDecodeError, TypeError) as e:
                    logger.debug("parallel dispatch json parse skipped: %s", e)
            results[key] = result
        except FuturesTimeout:
            results[f"{key}_error"] = f"timeout after {timeout}s"
            logger.warning("parallel tool call %s timed out after %ds", name, timeout)
        except Exception as e:
            results[f"{key}_error"] = str(e)
            logger.warning("parallel tool call %s failed: %s", name, e)

    return results


# ---------------------------------------------------------------------------
# Schema-Definitionen
# ---------------------------------------------------------------------------

_symbol_line_cache: Dict[str, int] = {}


def _clear_symbol_line_cache() -> None:
    """Leert den Symbol-Line-Cache. Wird vor jeder neuen Analyse aufgerufen."""
    _symbol_line_cache.clear()


def _find_symbol_line(path: str, symbol: str) -> int:
    """Findet die Zeilennummer eines Symbols in einer Datei.

    Nutzt internen Cache (dict) um wiederholte code_symbols Calls bei
    mehreren Analyse-Layern zu vermeiden.
    """
    cache_key = f"{path}:{symbol}"
    cached = _symbol_line_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        symbols = _call_tool("code_symbols", path=path, pattern=symbol)
        result = 1
        if isinstance(symbols, list):
            for s in symbols:
                if s.get("name") == symbol:
                    result = s.get("line", 1)
                    break
        elif isinstance(symbols, dict):
            for s in symbols.get("symbols", []):
                if s.get("name") == symbol:
                    result = s.get("line", 1)
                    break
        _symbol_line_cache[cache_key] = result
        return result
    except Exception as e:
        logger.debug("_find_symbol_line failed for %s: %s", symbol, e)
        return 1


def _summarize_symbols(symbols: Any) -> List[Dict[str, Any]]:
    """Extrahiert eine kompakte Symbol-Liste."""
    if isinstance(symbols, list):
        return [
            {"name": s.get("name", "?"), "kind": s.get("kind", ""), "line": s.get("line", 0)}
            for s in symbols[:50]
        ]
    if isinstance(symbols, dict):
        return [
            {"name": s.get("name", "?"), "kind": s.get("kind", ""), "line": s.get("line", 0)}
            for s in symbols.get("symbols", [])[:50]
        ]
    return []


def _summarize_diagnostics(diag: Any) -> Dict[str, int]:
    """Extrahiert Diagnostic-Zusammenfassung."""
    if isinstance(diag, dict):
        return {
            "errors": diag.get("errors", 0),
            "warnings": diag.get("warnings", 0) or diag.get("diagnostic_count", 0) - diag.get("errors", 0),
            "total": diag.get("diagnostic_count", 0) or diag.get("errors", 0),
        }
    return {"total": 0}


def _persist_analysis(intent: str, report: Dict[str, Any], metadata: Dict[str, Any]) -> None:
    """Persistiert Analyse-Ergebnisse in Honcho."""
    try:
        from hermes_cli.plugins import invoke_hook
        invoke_hook(
            "post_llm_call",
            action="honcho_conclude",
            conclusion=(
                f"analysis:{intent}:"
                f"{datetime.now().strftime('%Y-%m-%d')}: "
                f"{_build_summary_line(report, metadata)[:200]}"
            ),
            metadata={
                "tools_called": report.get("summary", {}).get("tools_called", 0),
                "path": metadata.get("path", ""),
                "symbol": metadata.get("symbol"),
                "findings": report.get("findings", {}),
                "intent": intent,
            },
        )
    except Exception:
        logger.info(
            "analysis %s: %s | %s",
            intent,
            _build_summary_line(report, metadata),
            metadata,
        )


def _build_summary_line(report: Dict[str, Any], metadata: Dict[str, Any]) -> str:
    """Baut eine einzeilige Zusammenfassung."""
    parts = []
    if "path" in metadata:
        parts.append(f"path={metadata['path']}")
    if "symbol" in metadata and metadata["symbol"]:
        parts.append(f"symbol={metadata['symbol']}")
    if "depth" in metadata:
        parts.append(f"depth={metadata['depth']}")
    if "tools_called" in metadata:
        parts.append(f"tools={metadata['tools_called']}")
    if "total_unused" in metadata:
        parts.append(f"unused={metadata['total_unused']}")
    if "finding_count" in metadata:
        parts.append(f"findings={metadata['finding_count']}")
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# analysis_diff Tool
# ---------------------------------------------------------------------------
