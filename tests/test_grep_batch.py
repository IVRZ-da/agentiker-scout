"""Sammel-grep: viele Patterns, wenige Subprozesse.

Der Kern der Aenderung ist nicht nur Geschwindigkeit, sondern Korrektheit:
Patterns sind BRE, ein einziges ungueltiges ERE-Pattern darf den Batch nicht
kippen und kein Pattern darf stillschweigend verschwinden.
"""
from __future__ import annotations

import subprocess

import pytest

from scout.shared.grep_batch import build_include_flags, grep_batch


def test_build_include_flags_single():
    assert build_include_flags("*.ts") == ("--include", "*.ts")


def test_build_include_flags_multiple():
    assert build_include_flags("**/*.{ts,tsx}") == (
        "--include", "*.ts", "--include", "*.tsx",
    )


def test_build_include_flags_empty():
    assert build_include_flags("") == ()


def test_grep_batch_finds_each_pattern(tmp_path):
    (tmp_path / "a.py").write_text("api_key = 'x'\neval('1')\npass\n")
    (tmp_path / "b.ts").write_text("const secret = 'y';\n")

    patterns = [
        {"pattern_id": "S1", "scan_query": "api_key", "scan_file_glob": "*.py"},
        {"pattern_id": "S2", "scan_query": "eval(", "scan_file_glob": "*.py"},
        {"pattern_id": "S3", "scan_query": "secret", "scan_file_glob": "*.ts"},
    ]
    result = grep_batch(patterns, str(tmp_path))

    assert result["S1"][0]["file"].endswith("a.py")
    assert result["S1"][0]["line"] == 1
    # "eval(" ist BRE-gueltig, aber kein Python-Regex -> Literal-Fallback
    assert result["S2"][0]["line"] == 2
    assert result["S3"][0]["file"].endswith("b.ts")


def test_grep_batch_groups_by_include(tmp_path, monkeypatch):
    """Gleiche Globs teilen sich einen Prozess, verschiedene bekommen eigene."""
    (tmp_path / "a.py").write_text("alpha\n")
    (tmp_path / "b.ts").write_text("beta\n")

    calls: list[list[str]] = []
    real_run = subprocess.run

    def counting_run(cmd, *args, **kwargs):
        calls.append(list(cmd))
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr("scout.shared.grep_batch.subprocess.run", counting_run)

    patterns = [
        {"pattern_id": f"P{i}", "scan_query": "alpha", "scan_file_glob": "*.py"}
        for i in range(5)
    ] + [
        {"pattern_id": f"Q{i}", "scan_query": "beta", "scan_file_glob": "*.ts"}
        for i in range(5)
    ]
    grep_batch(patterns, str(tmp_path))

    # 10 Patterns, 2 Glob-Gruppen -> 2 Prozesse statt 10
    assert len(calls) == 2, calls


def test_grep_batch_empty_patterns_makes_no_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "scout.shared.grep_batch.subprocess.run",
        lambda *a, **k: calls.append(a) or pytest.fail("kein Aufruf erwartet"),
    )
    assert grep_batch([], "/tmp") == {}
    assert calls == []


def test_grep_batch_skips_pattern_without_query(tmp_path):
    result = grep_batch([{"pattern_id": "X"}], str(tmp_path))
    assert "X" not in result


def test_grep_batch_survives_missing_binary(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise FileNotFoundError("grep weg")

    monkeypatch.setattr("scout.shared.grep_batch.subprocess.run", boom)
    result = grep_batch([{"pattern_id": "S1", "scan_query": "x"}], str(tmp_path))
    assert result == {"S1": []}


def test_grep_batch_survives_timeout(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="grep", timeout=1)

    monkeypatch.setattr("scout.shared.grep_batch.subprocess.run", timeout)
    result = grep_batch([{"pattern_id": "S1", "scan_query": "x"}], str(tmp_path))
    assert result == {"S1": []}


def test_grep_batch_handles_colons_in_path(tmp_path):
    sub = tmp_path / "weird:name"
    sub.mkdir()
    (sub / "f.py").write_text("needle\n")

    result = grep_batch([{"pattern_id": "S1", "scan_query": "needle"}], str(tmp_path))
    assert result["S1"], "Treffer mit Doppelpunkt im Pfad ging verloren"
    assert result["S1"][0]["line"] == 1


def test_grep_batch_returns_empty_list_for_no_match(tmp_path):
    (tmp_path / "a.py").write_text("nichts\n")
    result = grep_batch([{"pattern_id": "S1", "scan_query": "zzz"}], str(tmp_path))
    assert result["S1"] == []


def test_invalid_bre_pattern_does_not_kill_the_chunk(tmp_path, monkeypatch):
    """Ein kaputtes BRE-Pattern darf die Treffer der anderen nicht verschlucken."""
    (tmp_path / "a.py").write_text("needle_one\nneedle_two\n")

    patterns = [
        {"pattern_id": "GUT1", "scan_query": "needle_one"},
        {"pattern_id": "KAPUTT", "scan_query": "a\\{2,"},   # ungueltig fuer grep
        {"pattern_id": "GUT2", "scan_query": "needle_two"},
    ]
    result = grep_batch(patterns, str(tmp_path))

    assert result["GUT1"], "guter Nachbar verlor seine Treffer"
    assert result["GUT2"], "guter Nachbar verlor seine Treffer"
    assert result["KAPUTT"] == []


def test_returncode_2_triggers_single_runs(tmp_path, monkeypatch):
    calls: list[list[str]] = []
    real_run = subprocess.run

    def counting(cmd, *args, **kwargs):
        calls.append(list(cmd))
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr("scout.shared.grep_batch.subprocess.run", counting)
    (tmp_path / "f.py").write_text("x\n")
    grep_batch([
        {"pattern_id": "A", "scan_query": "a\\{3,"},
        {"pattern_id": "B", "scan_query": "x"},
    ], str(tmp_path))

    # 1 Sammellauf (scheitert) + 2 Einzellaeufe
    assert len(calls) == 3, calls
