"""Tests für analysis_ask — Kürzung und Output-Format.

Prüft dass die Antworten kurz und prägnant sind (nicht der volle Data-Dump).
"""
from __future__ import annotations

import json

import pytest

from scout.analysis.tools.perf_sec import analysis_ask_tool


def _parse_result(raw: str) -> dict:
    """Hilfsfunktion: fmt_ok/fmt_err Output parsen."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"status": "error", "raw": raw}


class TestAnalysisAskCompact:
    """Testet dass analysis_ask kompakte Antworten liefert."""

    def test_output_contains_no_full_context(self):
        """🔴 KEIN 'context' mit voller Symbol-Liste mehr im Output."""
        result = analysis_ask_tool({
            "question": "Was macht diese Funktion?",
            "path": "/home/jo/.hermes/plugins/scout",
        })
        parsed = _parse_result(result)
        assert parsed.get("status") == "ok", f"Expected ok, got: {parsed.get('status')}"
        # Früher: result["context"] = {symbols: [...], diagnostics: [...]}
        assert "context" not in parsed, "context wurde nicht entfernt — Output ist zu lang!"
        assert "findings" not in parsed, "leeres findings array wurde nicht entfernt"

    def test_output_has_compact_metrics(self):
        """Output enthält kompakte Metriken statt voller Daten."""
        result = analysis_ask_tool({
            "question": "Was macht diese Funktion?",
            "path": "/home/jo/.hermes/plugins/scout",
        })
        parsed = _parse_result(result)
        assert "metrics" in parsed, "metrics fehlen im Output"
        metrics = parsed["metrics"]
        assert "symbol_count" in metrics
        assert "diag_errors" in metrics
        assert "diag_warnings" in metrics
        assert "has_honcho" in metrics

    def test_output_has_summary(self):
        """Output enthält eine lesbare Summary."""
        result = analysis_ask_tool({
            "question": "Was macht diese Funktion?",
            "path": "/home/jo/.hermes/plugins/scout",
        })
        parsed = _parse_result(result)
        assert "summary" in parsed, "summary fehlt"
        assert len(parsed["summary"]) > 10, "summary ist zu kurz"
        assert "📝" in parsed["summary"] or "Was macht" in parsed["summary"]

    def test_output_is_not_oversized(self):
        """Output ist kompakt (< 2000 Zeichen als String)."""
        result = analysis_ask_tool({
            "question": "Was macht diese Funktion?",
            "path": "/home/jo/.hermes/plugins/scout",
        })
        # fmt_ok gibt JSON-String zurück — Länge prüfen
        assert len(result) < 2000, (
            f"Output ist zu lang: {len(result)} Zeichen. "
            f"Vorher war das >10KB mit vollem Symbol/Diagnostic-Dump."
        )

    def test_without_path(self):
        """Ohne path: Kein Code-Kontext, aber Frage + Honcho."""
        result = analysis_ask_tool({"question": "Wer hat das Projekt gestartet?"})
        parsed = _parse_result(result)
        assert parsed.get("status") == "ok"
        assert "metrics" in parsed
        metrics = parsed["metrics"]
        assert metrics["symbol_count"] == 0
        assert metrics["diag_errors"] == 0
        assert metrics["diag_warnings"] == 0

    def test_empty_question_returns_error(self):
        """Leere Frage -> Fehler."""
        result = analysis_ask_tool({"question": ""})
        parsed = _parse_result(result)
        assert parsed.get("status") == "error"

    def test_missing_question_returns_error(self):
        """Fehlende Frage -> Fehler."""
        result = analysis_ask_tool({})
        parsed = _parse_result(result)
        assert parsed.get("status") == "error"

    def test_question_is_truncated_in_output(self):
        """Frage wird im Output auf 200 Zeichen gekürzt."""
        long_q = "x" * 500
        result = analysis_ask_tool({"question": long_q})
        parsed = _parse_result(result)
        assert len(parsed.get("question", "")) <= 200, "question wurde nicht gekürzt"

    def test_output_size_is_reasonable_with_all_params(self):
        """Mit allen Parametern: Output bleibt kompakt."""
        result = analysis_ask_tool({
            "question": "Analysiere die Code-Qualität dieser Datei und gib mir "
                        "eine detaillierte Übersicht über alle Probleme, "
                        "die gefunden wurden, sortiert nach Schweregrad.",
            "path": "/home/jo/.hermes/plugins/scout",
        })
        assert len(result) < 2000, (
            f"Output mit path ist zu lang: {len(result)} Zeichen"
        )

    @pytest.mark.parametrize("question", [
        "Kurze Frage",
        "Eine etwas längere Frage die mehr Details enthält und analysiert werden soll",
        "a",
        "12345",
    ])
    def test_various_question_lengths(self, question):
        """Verschiedene Frage-Längen sollten alle funktionieren."""
        result = analysis_ask_tool({"question": question})
        parsed = _parse_result(result)
        assert parsed.get("status") == "ok"
        assert len(result) < 2000, f"Output zu lang für Frage '{question[:20]}...'"
