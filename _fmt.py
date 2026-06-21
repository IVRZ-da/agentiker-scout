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


def fmt_warn(message: str, data: dict | None = None) -> str:
    """Warning response with yellow status."""
    result = {"status": "warning", "message": message}
    if data:
        result["data"] = data
    return json.dumps(result, ensure_ascii=False, default=str)
