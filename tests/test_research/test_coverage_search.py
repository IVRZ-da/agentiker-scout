"""Coverage-Ergänzung für scout/research/tools/search.py.

Deckt die Zweige ab, die von den CRUD-/Tool-Tests nicht erreicht werden:
BM25-Randfälle, Index-Aufbau, Facetten-Filter (Tags als String, Datum),
Orphan-Plans, Status-Dauerformatierung und Altersverteilung in stats.

Alle Schreibvorgänge laufen über tmp_path — kein Zugriff auf echte Nutzdaten.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from scout.research.tools import base as base_mod
from scout.research.tools import search as search_mod

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def research_dirs(tmp_path, monkeypatch):
    """Lenkt PLANS_DIR/RESULTS_DIR von search.py und base.py auf tmp_path."""
    plans = tmp_path / "plans"
    results = tmp_path / "results"
    plans.mkdir()
    results.mkdir()

    for mod in (search_mod, base_mod):
        monkeypatch.setattr(mod, "PLANS_DIR", plans, raising=True)
        monkeypatch.setattr(mod, "RESULTS_DIR", results, raising=True)

    return plans, results


def _write_result(results_dir, rid: str, **fields) -> None:
    payload = {"id": rid, "query": f"Query {rid}", "status": "completed"}
    payload.update(fields)
    (results_dir / f"{rid}.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_plan(plans_dir, rid: str, **fields) -> None:
    payload = {"id": rid, "query": f"Query {rid}", "status": "planned"}
    payload.update(fields)
    (plans_dir / f"{rid}.json").write_text(json.dumps(payload), encoding="utf-8")


def _iso(days_ago: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


# ---------------------------------------------------------------------------
# Tokenizer / BM25
# ---------------------------------------------------------------------------


class TestBm25Helpers:
    def test_tokenize_drops_single_characters_keeps_umlauts(self):
        tokens = search_mod._tokenize("A Öl für Größe 42 x")
        assert "öl" in tokens
        assert "größe" in tokens
        assert "42" in tokens
        # Einzelzeichen werden verworfen
        assert "a" not in tokens
        assert "x" not in tokens

    def test_bm25_zero_for_empty_document(self):
        assert search_mod._bm25_score(["cbd"], "", 3, {"cbd": 1}, 4.0) == 0.0

    def test_bm25_zero_for_zero_average_length(self):
        # Dokument hat Terme, avgdl ist aber 0 (Index ohne Dokumente) → 0.0
        assert search_mod._bm25_score(["cbd"], "cbd cbd", 0, {}, 0.0) == 0.0

    def test_bm25_scores_matching_term_higher_than_missing(self):
        hit = search_mod._bm25_score(["cbd"], "cbd öl", 2, {"cbd": 1}, 2.0)
        miss = search_mod._bm25_score(["xyz"], "cbd öl", 2, {"xyz": 1}, 2.0)
        assert hit > 0
        assert miss == 0.0


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------


class TestBuildIndex:
    def test_missing_results_dir_returns_empty_index(self, research_dirs, monkeypatch, tmp_path):
        monkeypatch.setattr(search_mod, "RESULTS_DIR", tmp_path / "nope", raising=True)
        assert search_mod._build_index() == ([], {}, 0.0, 0)

    def test_skips_unreadable_documents_and_accepts_str_findings(self, research_dirs):
        _plans, results = research_dirs
        # Leere/kaputte Datei → übersprungen
        (results / "broken.json").write_text("", encoding="utf-8")
        _write_result(
            results,
            "full",
            summary="Zusammenfassung",
            findings=["String-Finding zu CBD", {"finding": "Dict-Finding"}],
            sources=[{"title": "Quelle A", "url": "https://example.test/a"}],
        )

        documents, df_map, avgdl, n = search_mod._build_index()

        assert n == 1
        assert documents[0]["stem"] == "full"
        assert "String-Finding zu CBD" in documents[0]["text"]
        assert "quelled" not in documents[0]["text"]
        assert df_map["cbd"] == 1
        assert avgdl > 0

    def test_empty_results_dir_yields_zero_documents(self, research_dirs):
        documents, df_map, avgdl, n = search_mod._build_index()
        assert (documents, df_map, avgdl, n) == ([], {}, 0.0, 0)


# ---------------------------------------------------------------------------
# research_search — Filter
# ---------------------------------------------------------------------------


class TestSearchFilters:
    def test_tags_as_string_are_normalized(self, research_dirs):
        _plans, results = research_dirs
        _write_result(results, "cbd1", tags=["cbd-oel"])
        _write_result(results, "other", tags=["steuern"])

        payload = json.loads(search_mod.research_search({"query": "", "tags": "CBD Oel"}))

        assert payload["total"] == 1
        assert payload["results"][0]["research_id"] == "cbd1"

    def test_date_from_and_to_bound_the_window(self, research_dirs):
        _plans, results = research_dirs
        _write_result(results, "old", saved_at="2020-01-01T00:00:00+00:00")
        _write_result(results, "mid", saved_at="2023-06-15T00:00:00+00:00")
        _write_result(results, "new", saved_at="2026-01-01T00:00:00+00:00")

        payload = json.loads(search_mod.research_search({
            "query": "",
            "date_from": "2023-01-01T00:00:00+00:00",
            "date_to": "2023-12-31T00:00:00+00:00",
        }))

        ids = [r["research_id"] for r in payload["results"]]
        assert ids == ["mid"]

    def test_unparseable_saved_at_is_kept(self, research_dirs):
        _plans, results = research_dirs
        _write_result(results, "weird", saved_at="kein-datum")

        payload = json.loads(search_mod.research_search({
            "query": "",
            "date_from": "2023-01-01T00:00:00+00:00",
        }))

        assert payload["total"] == 1
        assert payload["results"][0]["research_id"] == "weird"

    def test_status_filter_completed_only(self, research_dirs):
        _plans, results = research_dirs
        _write_result(results, "done", status="completed")
        _write_result(results, "failed", status="failed")

        payload = json.loads(search_mod.research_search({"query": "", "status": "COMPLETED"}))

        assert [r["research_id"] for r in payload["results"]] == ["done"]

    def test_limit_is_clamped_to_at_least_one(self, research_dirs):
        _plans, results = research_dirs
        for i in range(3):
            _write_result(results, f"r{i}")

        payload = json.loads(search_mod.research_search({"query": "Query", "limit": 0}))

        assert len(payload["results"]) == 1


# ---------------------------------------------------------------------------
# Orphan-Plans (gestartet, nie gespeichert)
# ---------------------------------------------------------------------------


class TestOrphanPlans:
    def test_no_query_returns_no_orphans(self, research_dirs):
        plans, _results = research_dirs
        _write_plan(plans, "orphan")
        assert search_mod._search_orphan_plans("", 0, {}, 0.0) == []

    def test_orphan_listed_when_result_missing(self, research_dirs):
        plans, _results = research_dirs
        _write_plan(plans, "orphan", query="CBD Legalisierung")

        found = search_mod._search_orphan_plans("cbd", 1, {"cbd": 1}, 2.0)

        assert [o["research_id"] for o in found] == ["orphan"]
        assert "noch nicht abgeschlossen" in found[0]["message"]

    def test_orphan_skipped_when_result_exists(self, research_dirs):
        plans, results = research_dirs
        _write_plan(plans, "done")
        _write_result(results, "done")

        assert search_mod._search_orphan_plans("query", 0, {}, 0.0) == []

    def test_corrupt_plan_file_is_skipped(self, research_dirs):
        plans, _results = research_dirs
        (plans / "broken.json").write_text("", encoding="utf-8")

        assert search_mod._search_orphan_plans("query", 0, {}, 0.0) == []

    def test_query_without_usable_terms_keeps_orphan(self, research_dirs):
        plans, _results = research_dirs
        _write_plan(plans, "orphan", query="CBD")

        # "a" ist nach Tokenisierung leer → kein Score, Plan bleibt sichtbar
        found = search_mod._search_orphan_plans("a", 0, {}, 0.0)

        assert [o["research_id"] for o in found] == ["orphan"]

    def test_orphans_surface_via_research_search(self, research_dirs):
        plans, results = research_dirs
        _write_result(results, "saved", query="CBD Öl Markt")
        _write_plan(plans, "pending", query="CBD Öl Preise")

        payload = json.loads(search_mod.research_search({"query": "CBD"}))

        assert payload["total"] == 1
        assert [o["research_id"] for o in payload["in_progress"]] == ["pending"]


# ---------------------------------------------------------------------------
# Honcho-Erkennung
# ---------------------------------------------------------------------------


def test_honcho_check_returns_false_on_registry_error(monkeypatch):
    from scout.shared.registry import registry

    def _boom(*_a, **_kw):
        raise RuntimeError("registry down")

    monkeypatch.setattr(registry, "get_entry", _boom, raising=True)

    assert search_mod._check_honcho_available() is False


# ---------------------------------------------------------------------------
# research_status
# ---------------------------------------------------------------------------


class TestResearchStatus:
    def test_missing_id_without_orphan_flag_is_an_error(self, research_dirs):
        payload = json.loads(search_mod.research_status({}))
        assert payload["status"] == "error"
        assert "research_id" in payload["error"]

    def test_invalid_id_is_rejected(self, research_dirs):
        payload = json.loads(search_mod.research_status({"research_id": "../etc/passwd"}))
        assert payload["status"] == "error"

    def test_unknown_id_reports_not_found(self, research_dirs):
        payload = json.loads(search_mod.research_status({"research_id": "gibtsnicht"}))
        assert payload["status"] == "not_found"

    def test_show_orphans_survives_broken_schedule_module(self, research_dirs, monkeypatch):
        plans, _results = research_dirs
        _write_plan(plans, "orphan1")

        from scout.research.tools import crud as crud_mod

        def _boom():
            raise RuntimeError("schedule kaputt")

        monkeypatch.setattr(crud_mod, "due_schedules", _boom, raising=True)

        payload = json.loads(search_mod.research_status({"show_orphans": True}))

        assert payload["status"] == "ok"
        assert payload["schedules_due"] == []
        assert payload["orphans_count"] == 1

    @pytest.mark.parametrize(
        ("created", "saved", "expected"),
        [
            ("2026-01-01T10:00:00+00:00", "2026-01-01T10:00:42+00:00", "42s"),
            ("2026-01-01T10:00:00+00:00", "2026-01-01T10:05:07+00:00", "5m 7s"),
            ("2026-01-01T10:00:00+00:00", "2026-01-01T12:30:00+00:00", "2h 30m"),
        ],
    )
    def test_duration_formatting(self, research_dirs, created, saved, expected):
        _plans, results = research_dirs
        _write_result(results, "timed", created_at=created, saved_at=saved)

        payload = json.loads(search_mod.research_status({"research_id": "timed"}))

        assert payload["duration"] == expected

    def test_invalid_timestamps_give_unknown_duration(self, research_dirs):
        _plans, results = research_dirs
        _write_result(results, "bad", created_at="gestern", saved_at="heute")

        payload = json.loads(search_mod.research_status({"research_id": "bad"}))

        assert payload["duration"] == "unbekannt"

    def test_plan_status_is_reported(self, research_dirs):
        plans, _results = research_dirs
        _write_plan(plans, "planned1", query="CBD", depth=3)

        payload = json.loads(search_mod.research_status({"research_id": "planned1"}))

        assert payload["status"] == "planned"
        assert payload["depth"] == 3


# ---------------------------------------------------------------------------
# research_stats
# ---------------------------------------------------------------------------


class TestResearchStats:
    def test_age_distribution_buckets_and_invalid_timestamps(self, research_dirs):
        _plans, results = research_dirs
        _write_result(results, "fresh", saved_at=_iso(0), tags=["cbd", "markt"])
        _write_result(results, "week", saved_at=_iso(3), tags=["cbd"])
        _write_result(results, "month", saved_at=_iso(10))
        _write_result(results, "ancient", saved_at=_iso(120))
        _write_result(results, "badstamp", saved_at="irgendwann")

        payload = json.loads(search_mod.research_stats({}))

        assert payload["total_researches"] == 5
        assert payload["age_distribution"]["< 1 Tag"] == 1
        assert payload["age_distribution"]["1-7 Tage"] == 1
        assert payload["age_distribution"]["7-30 Tage"] == 1
        assert payload["age_distribution"]["> 30 Tage"] == 1
        # Ungültiger Zeitstempel zählt in keinen Bucket
        assert sum(payload["age_distribution"].values()) == 4
        assert payload["top_tags"] == {"cbd": 2, "markt": 1}

    def test_stats_counts_orphans_and_status_distribution(self, research_dirs):
        plans, results = research_dirs
        _write_result(results, "done", status="completed", sources=[{"url": "u"}],
                      findings=[{"finding": "f"}])
        _write_plan(plans, "pending")

        payload = json.loads(search_mod.research_stats({}))

        assert payload["orphan_plans"] == 1
        assert payload["status_distribution"] == {"completed": 1}
        assert payload["total_sources"] == 1
        assert payload["total_findings"] == 1
        assert "1 Orphan-Plans" in payload["instruction"]
