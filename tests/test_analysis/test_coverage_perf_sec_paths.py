"""Coverage-Ergaenzung fuer analysis/tools/perf_sec.py.

Deckt Hotspot-Erkennung, Shared-Pattern-/Security-Scan-Integration und die
Kennzahlen-Extraktion von analysis_ask ab. Alle Tool-Aufrufe sind gemockt.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scout.analysis.tools import perf_sec as perf_sec_mod
from scout.analysis.tools.perf_sec import (
    analysis_ask_tool,
    analysis_performance_tool,
    analysis_security_tool,
)

MOD = "scout.analysis.tools.perf_sec"


def _fake_call_tool(mapping: dict, raise_for: set[str] | tuple[str, ...] = ()):
    def fake(name, timeout=0, **kwargs):
        if name in raise_for:
            raise RuntimeError(f"{name} nicht verfuegbar")
        return mapping.get(name, {})

    return fake


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "mod.py").write_text("def foo():\n    return 1\n")
    return tmp_path


# ── analysis_performance ─────────────────────────────────────────────


class TestPerformanceHotspots:
    def test_resolve_error_after_validation(self, project: Path) -> None:
        with patch(f"{MOD}._validate_and_resolve_path", return_value=("kaputt", "")):
            data = json.loads(analysis_performance_tool({"path": str(project)}))

        assert data["status"] == "error"
        assert "kaputt" in data["error"]

    def test_high_rank_is_reported_as_hotspot(self, project: Path) -> None:
        sections = {
            "complexity": {"rank": "D", "complexity": 4},
            "hot_paths": {"hot_paths": [{"file": "a.py", "callers": 9}]},
        }
        with patch(f"{MOD}._parallel_dispatch", return_value=sections):
            data = json.loads(analysis_performance_tool({"path": str(project)}))

        assert data["findings"]["hot_path_count"] == 1
        assert data["findings"]["hotspots"] == ["Hotspot: complexity=4 (rank=D)"]

    def test_high_score_without_rank_is_hotspot(self, project: Path) -> None:
        sections = {
            "complexity": {"rank": "A", "complexity": 22},
            "hot_paths": {"hot_paths": [{"file": "a.py"}]},
        }
        with patch(f"{MOD}._parallel_dispatch", return_value=sections):
            data = json.loads(analysis_performance_tool({"path": str(project)}))

        assert data["findings"]["hotspots"] == ["Hotspot: complexity=22 (rank=A)"]

    def test_moderate_metrics_are_not_hotspots(self, project: Path) -> None:
        sections = {
            "complexity": {"rank": "B", "complexity": 7},
            "hot_paths": {"paths": []},
        }
        with patch(f"{MOD}._parallel_dispatch", return_value=sections):
            data = json.loads(analysis_performance_tool({"path": str(project)}))

        # keine hot_paths => kein findings-Block
        assert "findings" not in data

    def test_complexity_as_non_dict_cannot_crash(self, project: Path) -> None:
        sections = {"complexity": "kein dict", "hot_paths": "auch kein dict"}
        with patch(f"{MOD}._parallel_dispatch", return_value=sections):
            data = json.loads(analysis_performance_tool({"path": str(project)}))

        assert data["status"] == "ok"
        assert data["summary"]["sections_completed"] == 2

    def test_paths_fallback_key(self, project: Path) -> None:
        sections = {"hot_paths": {"paths": [{"file": "a"}, {"file": "b"}]}}
        with patch(f"{MOD}._parallel_dispatch", return_value=sections):
            data = json.loads(analysis_performance_tool({"path": str(project)}))

        assert data["findings"]["hot_path_count"] == 2

    def test_dispatch_exception_is_captured(self, project: Path) -> None:
        with patch(
            f"{MOD}._parallel_dispatch", side_effect=RuntimeError("dispatch kaputt")
        ):
            data = json.loads(analysis_performance_tool({"path": str(project)}))

        assert data["status"] == "ok"
        assert data["summary"]["error"] == "dispatch kaputt"

    def test_inlay_hints_only_for_files(self, tmp_path: Path) -> None:
        calls: list[list[str]] = []

        def fake_dispatch(call_list, timeout=120):
            calls.append([c["key"] for c in call_list])
            return {c["key"]: {} for c in call_list}

        file_path = tmp_path / "a.py"
        file_path.write_text("x = 1\n")

        with patch(f"{MOD}._parallel_dispatch", side_effect=fake_dispatch):
            json.loads(analysis_performance_tool({"path": str(file_path)}))
            json.loads(analysis_performance_tool({"path": str(tmp_path)}))

        assert "inlay_hints" in calls[0]
        assert "inlay_hints" not in calls[1]

    def test_invalid_path_returns_error(self) -> None:
        data = json.loads(analysis_performance_tool({"path": "../etc/passwd"}))
        assert data["status"] == "error"


# ── analysis_security ────────────────────────────────────────────────


class TestSecurityScanIntegration:
    def test_resolve_error_after_validation(self, project: Path) -> None:
        with patch(f"{MOD}._validate_and_resolve_path", return_value=("kaputt", "")):
            data = json.loads(analysis_security_tool({"path": str(project)}))

        assert data["status"] == "error"
        assert "kaputt" in data["error"]

    def test_orphaned_errors_dict_and_count(self, project: Path) -> None:
        fake = _fake_call_tool(
            {"code_search_by_error": {"errors": [{"file": "a.py"}, {"file": "b.py"}]}}
        )
        with (
            patch(f"{MOD}._call_tool", side_effect=fake),
            patch(
                "scout.shared.registry.registry.dispatch", return_value=None
            ),
        ):
            data = json.loads(
                analysis_security_tool({"path": str(project), "kinds": ["errors"]})
            )

        assert data["summary"]["errors_scanned"] == 2
        assert len(data["findings"]["orphaned_errors"]) == 2

    def test_orphaned_errors_non_dict_result(self, project: Path) -> None:
        """Nicht-dict Antwort wird unveraendert uebernommen."""
        with (
            patch(f"{MOD}._call_tool", side_effect=_fake_call_tool(
                {"code_search_by_error": [{"file": "a.py"}]}
            )),
            patch("scout.shared.registry.registry.dispatch", return_value=None),
            patch(
                "scout.analysis.tools.base._run_shared_pattern_scans",
                return_value={},
            ),
        ):
            data = json.loads(
                analysis_security_tool({"path": str(project), "kinds": ["errors"]})
            )

        assert data["findings"]["orphaned_errors"] == [{"file": "a.py"}]
        assert data["summary"]["errors_scanned"] == 0

    def test_security_patterns_from_json_string(self, project: Path) -> None:
        payload = json.dumps([{"id": "v1"}, {"id": "v2"}])

        def dispatch(name, args=None, **kwargs):
            if name == "code_search_by_error" and args.get("error") == "Vulnerability":
                return payload
            return None

        with (
            patch(f"{MOD}._call_tool", side_effect=_fake_call_tool({})),
            patch("scout.shared.registry.registry.dispatch", side_effect=dispatch),
            patch(
                "scout.analysis.tools.base._run_shared_pattern_scans",
                return_value={},
            ),
        ):
            data = json.loads(
                analysis_security_tool(
                    {"path": str(project), "kinds": ["vulnerabilities"]}
                )
            )

        assert data["findings"]["security_patterns"] == [{"id": "v1"}, {"id": "v2"}]
        assert data["summary"]["vulnerabilities_found"] == 2

    def test_security_pattern_scan_failure_is_swallowed(self, project: Path) -> None:
        with (
            patch(f"{MOD}._call_tool", side_effect=_fake_call_tool({})),
            patch(
                "scout.shared.registry.registry.dispatch",
                side_effect=RuntimeError("kein error-scan"),
            ),
            patch(
                "scout.analysis.tools.base._run_shared_pattern_scans",
                return_value={},
            ),
        ):
            data = json.loads(
                analysis_security_tool(
                    {"path": str(project), "kinds": ["vulnerabilities"]}
                )
            )

        assert data["status"] == "ok"
        assert "security_patterns" not in data["findings"]

    def test_shared_patterns_are_merged(self, project: Path) -> None:
        shared = {
            "pattern_matches": [{"pattern_id": "p1", "file": "a.py"}],
            "patterns_scanned": 7,
        }
        with (
            patch(f"{MOD}._call_tool", side_effect=_fake_call_tool({})),
            patch("scout.shared.registry.registry.dispatch", return_value=None),
            patch(
                "scout.analysis.tools.base._run_shared_pattern_scans",
                return_value=shared,
            ) as scan,
        ):
            data = json.loads(
                analysis_security_tool({"path": str(project), "kinds": ["errors"]})
            )

        assert data["findings"]["shared_patterns"] == shared["pattern_matches"]
        assert data["summary"]["shared_patterns_count"] == 1
        assert data["summary"]["patterns_scanned"] == 7
        assert scan.call_args.kwargs["kinds"] == ["security"]

    def test_shared_pattern_scan_failure_is_swallowed(self, project: Path) -> None:
        with (
            patch(f"{MOD}._call_tool", side_effect=_fake_call_tool({})),
            patch("scout.shared.registry.registry.dispatch", return_value=None),
            patch(
                "scout.analysis.tools.base._run_shared_pattern_scans",
                side_effect=RuntimeError("scan kaputt"),
            ),
        ):
            data = json.loads(
                analysis_security_tool({"path": str(project), "kinds": ["errors"]})
            )

        assert data["status"] == "ok"
        assert "shared_patterns" not in data["findings"]

    def test_security_scan_findings_from_json_string(self, project: Path) -> None:
        fake = _fake_call_tool(
            {"code_security_scan": json.dumps({"findings": [{"rule": "x"}]})}
        )
        with (
            patch(f"{MOD}._call_tool", side_effect=fake),
            patch("scout.shared.registry.registry.dispatch", return_value=None),
            patch(
                "scout.analysis.tools.base._run_shared_pattern_scans",
                return_value={},
            ),
        ):
            data = json.loads(
                analysis_security_tool(
                    {"path": str(project), "kinds": ["vulnerabilities"]}
                )
            )

        assert data["findings"]["vulnerability_scan"] == [{"rule": "x"}]
        assert data["summary"]["vulnerability_scan_count"] == 1
        assert data["summary"]["vulnerabilities_found"] == 1

    def test_security_scan_without_findings_is_skipped(self, project: Path) -> None:
        fake = _fake_call_tool({"code_security_scan": {"findings": []}})
        with (
            patch(f"{MOD}._call_tool", side_effect=fake),
            patch("scout.shared.registry.registry.dispatch", return_value=None),
            patch(
                "scout.analysis.tools.base._run_shared_pattern_scans",
                return_value={},
            ),
        ):
            data = json.loads(
                analysis_security_tool(
                    {"path": str(project), "kinds": ["vulnerabilities"]}
                )
            )

        assert "vulnerability_scan" not in data["findings"]

    def test_security_scan_failure_is_swallowed(self, project: Path) -> None:
        with (
            patch(
                f"{MOD}._call_tool",
                side_effect=_fake_call_tool({}, raise_for={"code_security_scan"}),
            ),
            patch("scout.shared.registry.registry.dispatch", return_value=None),
            patch(
                "scout.analysis.tools.base._run_shared_pattern_scans",
                return_value={},
            ),
        ):
            data = json.loads(
                analysis_security_tool(
                    {"path": str(project), "kinds": ["vulnerabilities"]}
                )
            )

        assert data["status"] == "ok"
        assert "vulnerability_scan" not in data["findings"]

    def test_unexpected_result_type_sets_summary_error(self, project: Path) -> None:
        """Nicht-groessenfaehiges Tool-Ergebnis -> Fehler wird protokolliert."""
        with (
            patch(f"{MOD}._call_tool", side_effect=_fake_call_tool(
                {"code_search_by_error": 5}
            )),
            patch("scout.shared.registry.registry.dispatch", return_value=None),
            patch(
                "scout.analysis.tools.base._run_shared_pattern_scans",
                return_value={},
            ),
        ):
            data = json.loads(
                analysis_security_tool({"path": str(project), "kinds": ["errors"]})
            )

        assert data["status"] == "ok"
        assert "has no len()" in data["summary"]["error"]

    def test_invalid_path_returns_error(self) -> None:
        data = json.loads(analysis_security_tool({"path": "../escape"}))
        assert data["status"] == "error"


# ── analysis_ask ─────────────────────────────────────────────────────


def _ask(args: dict) -> dict:
    return json.loads(analysis_ask_tool(args))


class TestAskMetrics:
    def test_question_required(self) -> None:
        data = _ask({"question": "   "})
        assert data["status"] == "error"

    def test_symbols_dict_is_counted(self, project: Path) -> None:
        ctx = {"symbols": {"symbols": [{"name": "a"}, {"name": "b"}]}}
        with (
            patch(f"{MOD}._parallel_dispatch", return_value=ctx),
            patch("scout.shared.registry.registry.dispatch", return_value=None),
        ):
            data = _ask({"question": "Was macht das?", "path": str(project)})

        assert data["metrics"]["symbol_count"] == 2
        assert data["metrics"]["has_honcho"] is False
        assert "Kein Honcho-Kontext" in data["summary"]

    def test_symbols_data_fallback_and_list(self, project: Path) -> None:
        with (
            patch(
                f"{MOD}._parallel_dispatch",
                return_value={"symbols": {"data": [{"name": "a"}]}},
            ),
            patch("scout.shared.registry.registry.dispatch", return_value=None),
        ):
            assert _ask({"question": "q", "path": str(project)})["metrics"][
                "symbol_count"
            ] == 1

        with (
            patch(f"{MOD}._parallel_dispatch", return_value={"symbols": [1, 2, 3]}),
            patch("scout.shared.registry.registry.dispatch", return_value=None),
        ):
            assert _ask({"question": "q", "path": str(project)})["metrics"][
                "symbol_count"
            ] == 3

    def test_diagnostic_counts_are_extracted(self, project: Path) -> None:
        ctx = {
            "symbols": {"symbols": []},
            "diagnostics": {"errors": 2, "diagnostic_count": 7},
        }
        with (
            patch(f"{MOD}._parallel_dispatch", return_value=ctx),
            patch("scout.shared.registry.registry.dispatch", return_value=None),
        ):
            data = _ask({"question": "q", "path": str(project)})

        assert data["metrics"]["diag_errors"] == 2
        assert data["metrics"]["diag_warnings"] == 5
        assert "⚠5 ✗2" in data["summary"]

    def test_context_collection_failure_is_logged(self, project: Path) -> None:
        with (
            patch(
                f"{MOD}._parallel_dispatch", side_effect=RuntimeError("ctx kaputt")
            ),
            patch("scout.shared.registry.registry.dispatch", return_value=None),
            patch.object(perf_sec_mod.logger, "warning") as log,
        ):
            data = _ask({"question": "q", "path": str(project)})

        assert data["metrics"]["symbol_count"] == 0
        assert log.called

    def test_honcho_hint_is_appended(self) -> None:
        with patch(
            "scout.shared.registry.registry.dispatch",
            return_value="Sehr langer Honcho-Kontext ueber das Projekt",
        ):
            data = _ask({"question": "q"})

        assert data["metrics"]["has_honcho"] is True
        assert "Honcho-Kontext vorhanden" in data["summary"]
        assert "→ Sehr langer" in data["summary"]

    def test_short_honcho_result_gives_no_hint(self) -> None:
        with patch("scout.shared.registry.registry.dispatch", return_value="kurz"):
            data = _ask({"question": "q"})

        assert data["metrics"]["has_honcho"] is True
        assert "→" not in data["summary"]

    def test_honcho_failure_is_swallowed(self) -> None:
        with patch(
            "scout.shared.registry.registry.dispatch",
            side_effect=RuntimeError("honcho down"),
        ):
            data = _ask({"question": "q"})

        assert data["status"] == "ok"
        assert data["metrics"]["has_honcho"] is False

    def test_invalid_path_skips_context_collection(self) -> None:
        with (
            patch(f"{MOD}._parallel_dispatch") as dispatch,
            patch("scout.shared.registry.registry.dispatch", return_value=None),
        ):
            data = _ask({"question": "q", "path": "../escape"})

        dispatch.assert_not_called()
        assert data["metrics"]["symbol_count"] == 0

    def test_long_question_is_truncated(self) -> None:
        question = "x" * 400
        with patch("scout.shared.registry.registry.dispatch", return_value=None):
            data = _ask({"question": question})

        assert len(data["question"]) == 200
        assert len(data["summary"].splitlines()[0]) <= 126
