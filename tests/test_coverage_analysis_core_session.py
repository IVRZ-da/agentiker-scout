"""Findings-Aggregation und Session-Persistenz in ``analysis_core``.

Zwei Hook-Pfade, die bisher nie liefen:

* ``_aggregate_findings`` für ``code_cycle_detector`` — Zyklen landen als
  Zähler plus Detail-Liste (max. 5) in der Session;
* ``persist_analysis_session`` — Guard für inaktive Sessions und Session ohne
  Tool-Calls (wird verworfen statt an Honcho geschickt).

Die globale ``_analysis_session`` wird nach jedem Test zurückgesetzt.
"""

from __future__ import annotations

import json

import pytest

from scout.analysis import analysis_core as core


@pytest.fixture(autouse=True)
def clean_session():
    core._analysis_session.reset()
    yield
    core._analysis_session.reset()


class TestAggregateCycles:
    def test_cycles_are_counted_and_details_capped(self):
        core._analysis_session.start("architecture", "Zyklus-Analyse")

        cycles = [{"chain": f"mod{i} -> mod{i + 1}"} for i in range(7)]
        core._aggregate_findings(
            "code_cycle_detector", {"path": "/projekt"}, json.dumps({"cycles": cycles})
        )

        assert core._analysis_session.findings["cycles"] == 7
        assert len(core._analysis_session.findings["cycle_details"]) == 5

    def test_no_cycles_leaves_findings_untouched(self):
        core._analysis_session.start("architecture", "Zyklus-Analyse")

        core._aggregate_findings("code_cycle_detector", {}, {"cycles": []})

        assert "cycles" not in core._analysis_session.findings


class TestPersistSession:
    def test_inactive_session_is_ignored(self):
        """Ohne aktive Session passiert nichts — kein Dispatch, kein Reset."""
        core._analysis_session.reset()

        core.persist_analysis_session()

        assert core._analysis_session.active is False
        assert core._analysis_session.tools_used == []

    def test_session_without_tool_calls_is_discarded(self):
        core._analysis_session.start("code", "nur gestartet, nichts benutzt")

        core.persist_analysis_session()

        assert core._analysis_session.active is False
        assert core._analysis_session.intent == ""
        assert core._analysis_session.tools_used == []
