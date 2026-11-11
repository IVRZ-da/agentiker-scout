"""Coverage-Ergaenzung fuer analysis/tools/base.py.

Deckt die Pfade ab, die von den bestehenden Tests nicht beruehrt werden:
  - _shutdown_executors (Executor-Leak bei Plugin-Reload)
  - _run_shared_pattern_scans (Pattern-Filter, Match-Truncation, Zaehler)
  - _persist_analysis (Honcho nicht verfuegbar)
  - _try_create_plan_follow_plan / _try_create_bughunt_finding (lose Kopplung)

Alle code-intel-/Honcho-Aufrufe sind gemockt — es findet kein echter Dispatch
und kein echter grep statt.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from scout.analysis.tools import base as base_mod
from scout.analysis.tools.base import (
    _persist_analysis,
    _run_shared_pattern_scans,
    _shutdown_executors,
    _try_create_bughunt_finding,
    _try_create_plan_follow_plan,
)


def _entry(handler):
    """Registry-Entry-Stub mit genau dem Attribut, das base.py nutzt."""
    entry = MagicMock()
    entry.handler = handler
    return entry


# ── _shutdown_executors ──────────────────────────────────────────────


class TestShutdownExecutors:
    def test_shuts_down_both_pools(self) -> None:
        """Beide Modul-Pools werden mit cancel_futures beendet."""
        timeout_pool = MagicMock()
        parallel_pool = MagicMock()

        with (
            patch.object(base_mod, "_timeout_executor", timeout_pool),
            patch.object(base_mod, "_parallel_executor", parallel_pool),
        ):
            _shutdown_executors()

        timeout_pool.shutdown.assert_called_once_with(wait=False, cancel_futures=True)
        parallel_pool.shutdown.assert_called_once_with(wait=False, cancel_futures=True)

    def test_shutdown_is_idempotent(self) -> None:
        """Zweifacher Shutdown darf nicht werfen (atexit + Reload)."""
        timeout_pool = MagicMock()
        parallel_pool = MagicMock()

        with (
            patch.object(base_mod, "_timeout_executor", timeout_pool),
            patch.object(base_mod, "_parallel_executor", parallel_pool),
        ):
            _shutdown_executors()
            _shutdown_executors()

        assert timeout_pool.shutdown.call_count == 2
        assert parallel_pool.shutdown.call_count == 2


# ── _run_shared_pattern_scans ────────────────────────────────────────


def _patterns() -> list[dict]:
    return [
        {
            "pattern_id": "p_str_kind",
            "name": "String-Kind",
            "severity": "P1",
            "category": "security",
            "analysis_kinds": "security",  # Einzelstring, kein List
            "scan_query": "eval(",
            "fix_description": "kein eval",
        },
        {
            "pattern_id": "p_many_hits",
            "name": "Viele Treffer",
            "severity": "P2",
            "category": "security",
            "analysis_kinds": ["security"],
            "scan_query": "md5(",
        },
        {
            "pattern_id": "p_other",
            "name": "Andere Kategorie",
            "analysis_kinds": ["code-quality"],
            "scan_query": "print(",
        },
        {
            "pattern_id": "",
            "name": "Ohne pattern_id",
            "analysis_kinds": ["security"],
            "scan_query": "os.system(",
        },
    ]


class TestRunSharedPatternScans:
    def test_filters_by_kind_and_truncates_hits(self) -> None:
        """kinds-Filter greift, Treffer werden auf 20 pro Pattern begrenzt."""
        hits = {
            "p_str_kind": [{"file": "a.py", "line": 1, "match": "eval(x)"}],
            "p_many_hits": [
                {"file": "b.py", "line": i, "match": "md5(x)"} for i in range(1, 26)
            ],
        }

        with (
            patch(
                "scout.shared.patterns.get_patterns_for_analysis",
                return_value=_patterns(),
            ),
            patch("scout.shared.grep_batch.grep_batch", return_value=hits) as batch,
            patch("scout.shared.patterns.increment_match_count") as incr,
        ):
            result = _run_shared_pattern_scans("/tmp/project", kinds=["security"])

        # p_other faellt durch den Filter, p ohne pattern_id kommt nicht in den Batch
        assert result["patterns_scanned"] == 3
        # 1 Treffer (p_str_kind) + 20 (p_many_hits, truncated aus 25)
        assert len(result["pattern_matches"]) == 21
        assert incr.call_count == 2

        scanned = batch.call_args[0][0]
        assert {p["pattern_id"] for p in scanned} == {"p_str_kind", "p_many_hits"}

        first = result["pattern_matches"][0]
        assert first["pattern_id"] == "p_str_kind"
        assert first["pattern_name"] == "String-Kind"
        assert first["severity"] == "P1"
        assert first["category"] == "security"
        assert first["file"] == "a.py"
        assert first["line"] == 1
        assert first["evidence"] == "eval(x)"
        assert first["fix_description"] == "kein eval"

    def test_without_kind_filter_scans_all(self) -> None:
        """Ohne kinds wird nicht gefiltert — auch code-quality Patterns laufen."""
        hits = {"p_other": [{"file": "c.py", "line": 7, "match": "print(x)"}]}

        with (
            patch(
                "scout.shared.patterns.get_patterns_for_analysis",
                return_value=_patterns(),
            ),
            patch("scout.shared.grep_batch.grep_batch", return_value=hits),
            patch("scout.shared.patterns.increment_match_count"),
        ):
            result = _run_shared_pattern_scans("/tmp/project")

        assert result["patterns_scanned"] == 4
        assert len(result["pattern_matches"]) == 1
        assert result["pattern_matches"][0]["severity"] == "P2"  # Default
        assert result["pattern_matches"][0]["category"] == ""

    def test_increment_failure_does_not_break_scan(self) -> None:
        """Ein kaputter Match-Zaehler darf den Scan nicht kippen."""
        hits = {"p_str_kind": [{"file": "a.py", "line": 1, "match": "eval(x)"}]}

        with (
            patch(
                "scout.shared.patterns.get_patterns_for_analysis",
                return_value=_patterns(),
            ),
            patch("scout.shared.grep_batch.grep_batch", return_value=hits),
            patch(
                "scout.shared.patterns.increment_match_count",
                side_effect=RuntimeError("counter locked"),
            ),
            patch.object(base_mod.logger, "debug") as log,
        ):
            result = _run_shared_pattern_scans("/tmp/project", kinds=["security"])

        assert len(result["pattern_matches"]) == 1
        assert log.called

    def test_no_scannable_patterns_skips_batch(self) -> None:
        """Patterns ohne scan_query/pattern_id loesen keinen grep-Batch aus."""
        with (
            patch(
                "scout.shared.patterns.get_patterns_for_analysis",
                return_value=[{"name": "nur-metadaten", "scan_query": ""}],
            ),
            patch("scout.shared.grep_batch.grep_batch") as batch,
        ):
            result = _run_shared_pattern_scans("/tmp/project")

        batch.assert_not_called()
        assert result == {"pattern_matches": [], "patterns_scanned": 1}

    def test_language_filter_is_forwarded(self) -> None:
        with (
            patch(
                "scout.shared.patterns.get_patterns_for_analysis",
                return_value=[],
            ) as get_patterns,
            patch("scout.shared.grep_batch.grep_batch") as batch,
        ):
            _run_shared_pattern_scans("/tmp/project", scan_language="python")

        get_patterns.assert_called_once_with(scan_language="python")
        batch.assert_not_called()


# ── _persist_analysis ────────────────────────────────────────────────


class TestPersistAnalysis:
    def test_honcho_dispatch_error_is_swallowed(self) -> None:
        """Ohne Honcho wird nur geloggt — kein Raise."""
        with (
            patch(
                "scout.shared.registry.registry.dispatch",
                side_effect=RuntimeError("honcho down"),
            ),
            patch.object(base_mod.logger, "info") as log,
        ):
            _persist_analysis(
                "inspect",
                {"tool": "analysis_inspect", "path": "/tmp/x"},
                {"path": "/tmp/x", "depth": 2},
            )

        assert log.called

    def test_success_dispatches_conclusion(self) -> None:
        with patch("scout.shared.registry.registry.dispatch") as dispatch:
            _persist_analysis(
                "deadcode",
                {"tool": "analysis_deadcode"},
                {"path": "/tmp/y", "total_unused": 3},
            )

        name, payload = dispatch.call_args[0]
        assert name == "honcho_conclude"
        assert payload["peer"] == "analysis"
        assert payload["conclusion"].startswith("analysis:deadcode:")
        assert "unused=3" in payload["conclusion"]


# ── _try_create_plan_follow_plan ─────────────────────────────────────


class TestTryCreatePlanFollowPlan:
    def test_returns_none_without_plugin(self) -> None:
        with patch("scout.shared.registry.registry.get_entry", return_value=None):
            assert _try_create_plan_follow_plan("analysis_inspect", "/tmp") is None

    def test_json_string_result_is_parsed(self) -> None:
        entry = _entry(lambda args: json.dumps({"status": "created", "plan_id": "pf_1"}))
        with patch("scout.shared.registry.registry.get_entry", return_value=entry):
            result = _try_create_plan_follow_plan("analysis_inspect", "/tmp")

        assert result == {"status": "created", "plan_id": "pf_1"}

    def test_plain_string_result_falls_back_to_flag(self) -> None:
        entry = _entry(lambda args: "Plan angelegt")
        with patch("scout.shared.registry.registry.get_entry", return_value=entry):
            result = _try_create_plan_follow_plan("analysis_deadcode", "/tmp")

        assert result == {"plan_created": True}

    def test_dict_result_is_passed_through(self) -> None:
        entry = _entry(lambda args: {"plan_id": "pf_2"})
        with patch("scout.shared.registry.registry.get_entry", return_value=entry):
            assert _try_create_plan_follow_plan("analysis_deadcode", "/tmp") == {
                "plan_id": "pf_2"
            }

    def test_handler_receives_goal_and_template(self) -> None:
        captured: dict = {}

        def handler(args):
            captured.update(args)
            return {"ok": True}

        with patch(
            "scout.shared.registry.registry.get_entry", return_value=_entry(handler)
        ):
            _try_create_plan_follow_plan("analysis_architecture", "/tmp/proj")

        assert captured["template"] == "analysis"
        assert "/tmp/proj" in captured["goal"]
        assert "analysis_architecture" in captured["goal"]

    def test_handler_exception_returns_none(self) -> None:
        def broken(args):
            raise RuntimeError("plan_follow kaputt")

        with (
            patch(
                "scout.shared.registry.registry.get_entry",
                return_value=_entry(broken),
            ),
            patch.object(base_mod.logger, "debug") as log,
        ):
            assert _try_create_plan_follow_plan("analysis_inspect", "/tmp") is None
        assert log.called

    def test_get_entry_exception_returns_none(self) -> None:
        with patch(
            "scout.shared.registry.registry.get_entry",
            side_effect=RuntimeError("registry kaputt"),
        ):
            assert _try_create_plan_follow_plan("analysis_inspect", "/tmp") is None


# ── _try_create_bughunt_finding ──────────────────────────────────────


class TestTryCreateBughuntFinding:
    def test_returns_none_without_plugin(self) -> None:
        with patch("scout.shared.registry.registry.get_entry", return_value=None):
            assert _try_create_bughunt_finding("high", "Zyklen", {"path": "/tmp"}) is None

    def test_json_string_result_is_parsed(self) -> None:
        entry = _entry(lambda args: json.dumps({"status": "created", "id": "bh_1"}))
        with patch("scout.shared.registry.registry.get_entry", return_value=entry):
            result = _try_create_bughunt_finding("high", "Zyklen", {"path": "/tmp"})
        assert result == {"status": "created", "id": "bh_1"}

    def test_plain_string_result_falls_back_to_flag(self) -> None:
        entry = _entry(lambda args: "ok")
        with patch("scout.shared.registry.registry.get_entry", return_value=entry):
            result = _try_create_bughunt_finding("medium", "Dead Code", {"path": "/tmp"})
        assert result == {"finding_created": True}

    def test_dict_result_is_passed_through(self) -> None:
        entry = _entry(lambda args: {"id": "bh_2"})
        with patch("scout.shared.registry.registry.get_entry", return_value=entry):
            assert _try_create_bughunt_finding("low", "x", {"path": "/tmp"}) == {
                "id": "bh_2"
            }

    def test_details_are_mapped_into_payload(self) -> None:
        captured: dict = {}

        def handler(args):
            captured.update(args)
            return {"ok": True}

        details = {
            "path": "/tmp",
            "session_id": "s1",
            "file": "a.py",
            "line": 42,
            "description": "d",
            "evidence": "e",
        }
        with patch(
            "scout.shared.registry.registry.get_entry", return_value=_entry(handler)
        ):
            _try_create_bughunt_finding("high", "Titel", details)

        assert captured["severity"] == "high"
        assert captured["title"] == "Titel"
        assert captured["session_id"] == "s1"
        assert captured["file"] == "a.py"
        assert captured["line"] == 42
        assert captured["description"] == "d"
        assert captured["evidence"] == "e"

    def test_missing_detail_keys_default(self) -> None:
        captured: dict = {}

        def handler(args):
            captured.update(args)
            return None

        with patch(
            "scout.shared.registry.registry.get_entry", return_value=_entry(handler)
        ):
            assert _try_create_bughunt_finding("low", "T", {"path": "/tmp"}) is None

        assert captured["session_id"] == ""
        assert captured["line"] == 0

    def test_handler_exception_returns_none(self) -> None:
        def broken(args):
            raise RuntimeError("bughunt kaputt")

        with (
            patch(
                "scout.shared.registry.registry.get_entry",
                return_value=_entry(broken),
            ),
            patch.object(base_mod.logger, "debug") as log,
        ):
            assert _try_create_bughunt_finding("medium", "T", {"path": "/tmp"}) is None
        assert log.called

    def test_get_entry_exception_returns_none(self) -> None:
        with patch(
            "scout.shared.registry.registry.get_entry",
            side_effect=ImportError("kein bughunt"),
        ):
            assert _try_create_bughunt_finding("medium", "T", {"path": "/tmp"}) is None


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        ({"path": "/tmp/a"}, "path=/tmp/a"),
        ({"path": "/tmp/a", "symbol": "foo"}, "symbol=foo"),
        ({"depth": 3}, "depth=3"),
        ({"tools_called": 4}, "tools=4"),
        ({"finding_count": 2}, "findings=2"),
        ({"total_unused": 9}, "unused=9"),
    ],
)
def test_build_summary_line_fields(metadata: dict, expected: str) -> None:
    """Jedes Metadaten-Feld landet in der Persist-Zeile."""
    assert expected in base_mod._build_summary_line({}, metadata)


def test_build_summary_line_skips_empty_symbol() -> None:
    line = base_mod._build_summary_line({}, {"path": "/tmp", "symbol": ""})
    assert line == "path=/tmp"


def test_negative_timeout_env_is_read_from_env() -> None:
    """ANALYSIS_TOOL_TIMEOUT wird beim Modul-Import gelesen."""
    assert isinstance(base_mod._DEFAULT_TOOL_TIMEOUT, int)
