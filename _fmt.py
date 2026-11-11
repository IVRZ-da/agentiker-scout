"""Shared rich-based output formatting for scout plugin.

Mirrors the _fmt.py pattern from all 3 source plugins (analysis, bughunt, deep-research).
Single source of truth — replaces 3 duplicates.
"""

from __future__ import annotations

import json
from typing import Any


def fmt_ok(data: dict[str, Any] | str, message: str | None = None) -> str:
    """Success response with green status."""
    if isinstance(data, str):
        return json.dumps({"status": "ok", "message": data}, ensure_ascii=False)
    result: dict[str, Any] = {"status": "ok"}
    if message:
        result["message"] = message
    if isinstance(data, dict):
        result.update(data)
    return json.dumps(result, ensure_ascii=False, default=str)

def fmt_err(message: str, details: dict[str, Any] | None = None) -> str:
    """Error response with red status."""
    result: dict[str, Any] = {"status": "error", "message": message}
    if details:
        result["details"] = details
    return json.dumps(result, ensure_ascii=False, default=str)

def fmt_warn(message: str, details: dict[str, Any] | None = None) -> str:
    """Warning response with yellow status."""
    result: dict[str, Any] = {"status": "warning", "message": message}
    if details:
        result["details"] = details
    return json.dumps(result, ensure_ascii=False, default=str)

def fmt_info(message: str, data: dict[str, Any] | None = None) -> str:
    """Informational response."""
    result: dict[str, Any] = {"status": "info", "message": message}
    if data:
        result["data"] = data
    return json.dumps(result, ensure_ascii=False, default=str)

def fmt_table(headers: list[str], rows: list[list[str]], title: str | None = None) -> str:
    """Format as table (simple pipe-delimited for LLM consumption)."""
    parts: list[str] = []
    if title:
        parts.append(title)
    parts.append(" | ".join(headers))
    parts.append(" | ".join("-" * len(h) for h in headers))
    for row in rows:
        parts.append(" | ".join(row))
    return "\n".join(parts)

def fmt_code(code: str, language: str = "", **kwargs) -> str:
    """Format as code block. Ignores extra kwargs for backward compatibility."""
    lang = f"{language}" if language else ""
    return f"```{lang}\n{code}\n```"

def fmt_markdown(text: str) -> str:
    """Ensure text is valid markdown."""
    return text.strip()

def fmt_json(data: Any) -> str:
    """Pretty-print JSON data."""
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def fmt_research_status(data: dict, title: str | None = None) -> str:
    """Format research status with optional title."""
    result = {"status": "ok"}
    if title:
        result["title"] = title
    if isinstance(data, dict):
        result.update(data)
    return json.dumps(result, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# response_format: concise | detailed
# ---------------------------------------------------------------------------
#
# Anthropic misst ~1/3 der Tokens bei "concise" ohne Entscheidungsverlust. Die
# Verdichtung passiert zentral (siehe plugin._wrap_response_format), damit
# jeder Handler sie umsonst bekommt und kein Tool eine eigene Variante baut.

CONCISE_LIST_LIMIT = 5
CONCISE_STRING_LIMIT = 240

#: Skalare Schluessel, die auch in "concise" erhalten bleiben (Aggregate).
_KEEP_ALWAYS = frozenset({
    "status", "message", "count", "total", "error", "id", "session_id",
    "research_id", "finding_id", "name", "title", "severity", "duration_ms",
})


def condense(value: Any, *, list_limit: int = CONCISE_LIST_LIMIT,
             string_limit: int = CONCISE_STRING_LIMIT) -> Any:
    """Verdichtet eine verschachtelte Struktur fuer ``concise``.

    Listen werden gekuerzt (Rest als ``..._truncated`` vermerkt), lange Strings
    abgeschnitten. Skalare bleiben unveraendert — Aggregate wie ``count``
    muessen stimmen, sonst luegt die Ausgabe.
    """
    if isinstance(value, str):
        if len(value) <= string_limit:
            return value
        return value[: string_limit - 1] + "\u2026"
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(item, list) and len(item) > list_limit:
                out[key] = [condense(v, list_limit=list_limit, string_limit=string_limit)
                            for v in item[:list_limit]]
                out[f"{key}_truncated"] = len(item) - list_limit
            else:
                out[key] = condense(item, list_limit=list_limit, string_limit=string_limit)
        return out
    if isinstance(value, list):
        return [condense(v, list_limit=list_limit, string_limit=string_limit)
                for v in value[:list_limit]]
    return value


def condense_json(payload: str, **kwargs: Any) -> str:
    """Wendet :func:`condense` auf einen JSON-String an.

    Nicht-JSON-Ausgaben (Tabellen, Markdown) werden unveraendert
    zurueckgegeben — dort gibt es keine Felder zu verdichten.
    """
    if not isinstance(payload, str):
        return payload
    stripped = payload.strip()
    if not stripped.startswith(("{", "[")):
        return payload
    try:
        data = json.loads(stripped)
    except (json.JSONDecodeError, TypeError):
        return payload
    return json.dumps(condense(data, **kwargs), ensure_ascii=False, default=str)


def wants_concise(args: dict | None) -> bool:
    """True, wenn der Aufrufer ``response_format="concise"`` gesetzt hat."""
    if not isinstance(args, dict):
        return False
    return str(args.get("response_format", "detailed")).lower() == "concise"
