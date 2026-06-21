"""
Tests für die Tools des scout.research Plugins.

Testet: research_delete, research_cleanup, research_export,
research_compare, research_synthesize, research_schedule
sowie neue Features in research_status (show_orphans) und
research_save (native Arrays).
"""

import json
import pytest

from conftest import make_research_tools


@pytest.fixture
def rt(tmp_path):
    return make_research_tools(tmp_path)


# ---------------------------------------------------------------------------
# research_delete
# ---------------------------------------------------------------------------

class TestResearchDelete:
    def test_delete_plan_only(self, rt):
        """Löschen einer geplanten (noch nicht gespeicherten) Recherche."""
        start = json.loads(rt.research_start({"query": "Test Delete"}))
        rid = start["research_id"]
        assert (rt.PLANS_DIR / f"{rid}.json").exists()

        result = json.loads(rt.research_delete({"research_id": rid}))
        assert result["status"] != "error"
        assert result["deleted_plan"] is True
        assert result["deleted_result"] is False
        assert not (rt.PLANS_DIR / f"{rid}.json").exists()

    def test_delete_completed(self, rt):
        """Löschen einer abgeschlossenen Recherche."""
        start = json.loads(rt.research_start({"query": "Test Query"}))
        rid = start["research_id"]
        rt.research_save({"research_id": rid, "summary": "Done", "status": "completed"})

        assert (rt.RESULTS_DIR / f"{rid}.json").exists()
        result = json.loads(rt.research_delete({"research_id": rid}))
        assert result["deleted_plan"] is False
        assert result["deleted_result"] is True

    def test_delete_nonexistent(self, rt):
        """Löschen einer nicht-existenten ID."""
        result = json.loads(rt.research_delete({"research_id": "nonexistent"}))
        assert result["status"] == "error"

    def test_delete_empty_id(self, rt):
        """Löschen ohne ID."""
        result = json.loads(rt.research_delete({"research_id": ""}))
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# research_cleanup
# ---------------------------------------------------------------------------

class TestResearchCleanup:
    def test_cleanup_orphan_plans(self, rt):
        """Cleanup löscht alte Orphan-Plans."""
        # Alten Plan anlegen
        old_id = "oldplan123"
        old_plan = {
            "id": old_id, "query": "Old", "depth": 1,
            "max_sources": 5, "status": "planned",
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        (rt.PLANS_DIR / f"{old_id}.json").write_text(json.dumps(old_plan))

        result = json.loads(rt.research_cleanup({
            "action": "plans", "older_than_days": 1,
        }))
        assert result["deleted_plans"] >= 1
        assert not (rt.PLANS_DIR / f"{old_id}.json").exists()

    def test_cleanup_keeps_recent(self, rt):
        """Cleanup löscht keine aktuellen Orphan-Plans."""
        start = json.loads(rt.research_start({"query": "Fresh"}))
        rid = start["research_id"]

        result = json.loads(rt.research_cleanup({
            "action": "plans", "older_than_days": 30,
        }))
        # Der frische Plan sollte nicht gelöscht werden
        assert (rt.PLANS_DIR / f"{rid}.json").exists()

    def test_cleanup_invalid_action(self, rt):
        """Ungültige action."""
        result = json.loads(rt.research_cleanup({"action": "invalid"}))
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# research_export
# ---------------------------------------------------------------------------

class TestResearchExport:
    def test_export_markdown(self, rt):
        """Export als Markdown."""
        start = json.loads(rt.research_start({"query": "Green Tech Export Test"}))
        rid = start["research_id"]
        rt.research_save({
            "research_id": rid,
            "summary": "Zusammenfassung des Exports",
            "findings": [
                {"finding": "Finding 1", "sources": ["https://example.com/1"]},
            ],
            "sources": [
                {"url": "https://example.com/1", "title": "Quelle 1", "relevance": 0.9},
            ],
            "status": "completed",
        })

        result = json.loads(rt.research_export({
            "research_id": rid, "format": "markdown",
        }))
        assert result["status"] != "error"
        assert "Green Tech Export Test" in result["content"]
        assert "Finding 1" in result["content"]
        assert "Quelle 1" in result["content"]
        assert result["format"] == "markdown"

    def test_export_text(self, rt):
        """Export als Text."""
        start = json.loads(rt.research_start({"query": "Text Export"}))
        rid = start["research_id"]
        rt.research_save({
            "research_id": rid, "summary": "Text-Export", "status": "completed",
        })

        result = json.loads(rt.research_export({
            "research_id": rid, "format": "text",
        }))
        assert result["format"] == "text"
        assert "RESEARCH:" in result["content"]

    def test_export_nonexistent(self, rt):
        """Export einer nicht-existenten ID."""
        result = json.loads(rt.research_export({"research_id": "noexist"}))
        assert result["status"] == "error"

    def test_export_plan_only(self, rt):
        """Export einer geplanten Recherche (ohne Save)."""
        start = json.loads(rt.research_start({"query": "Plan Only Export"}))
        rid = start["research_id"]

        result = json.loads(rt.research_export({"research_id": rid}))
        assert result["status"] != "error"
        assert "Plan Only Export" in result["content"]


# ---------------------------------------------------------------------------
# research_compare
# ---------------------------------------------------------------------------

class TestResearchCompare:
    def test_compare_two(self, rt):
        """Vergleich von 2 Recherchen."""
        ids = []
        for q in ["Renewable Energy", "Climate Science"]:
            start = json.loads(rt.research_start({"query": q}))
            ids.append(start["research_id"])
            rt.research_save({
                "research_id": start["research_id"],
                "summary": f"Ergebnisse zu {q}",
                "findings": [{"finding": f"Finding {q}", "sources": []}],
                "sources": [],
                "status": "completed",
            })

        result = json.loads(rt.research_compare({"research_ids": ids}))
        assert result["total_items"] == 2
        assert len(result["items"]) == 2

    def test_compare_too_few(self, rt):
        """Vergleich mit < 2 IDs."""
        result = json.loads(rt.research_compare({"research_ids": ["onlyone"]}))
        assert result["status"] == "error"

    def test_compare_too_many(self, rt):
        """Vergleich mit > 3 IDs."""
        result = json.loads(rt.research_compare({
            "research_ids": ["a", "b", "c", "d"],
        }))
        assert result["status"] == "error"

    def test_compare_nonexistent(self, rt):
        """Vergleich mit nicht-existenten IDs."""
        result = json.loads(rt.research_compare({
            "research_ids": ["real1", "noexist"],
        }))
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# research_synthesize
# ---------------------------------------------------------------------------

class TestResearchSynthesize:
    def test_synthesize_empty(self, rt):
        """Synthese ohne lokale Ergebnisse."""
        result = json.loads(rt.research_synthesize({
            "query": "Nichts da",
            "reasoning_level": "low",
        }))
        assert result["local_result_count"] == 0
        assert "honcho_reasoning" in result["instruction"]

    def test_synthesize_with_local(self, rt):
        """Synthese mit lokalen Ergebnissen."""
        start = json.loads(rt.research_start({"query": "Renewable Energy"}))
        rid = start["research_id"]
        rt.research_save({
            "research_id": rid, "summary": "Renewable Energy policy in DE",
            "status": "completed",
        })

        result = json.loads(rt.research_synthesize({
            "query": "Renewable Energy",
            "reasoning_level": "medium",
        }))
        assert result["local_result_count"] >= 1

    def test_synthesize_missing_query(self, rt):
        """Synthese ohne Query."""
        result = json.loads(rt.research_synthesize({"query": ""}))
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# research_schedule
# ---------------------------------------------------------------------------

class TestResearchSchedule:
    def test_schedule_daily(self, rt):
        """Tägliche Planung."""
        result = json.loads(rt.research_schedule({
            "query": "Green Tech Market 2026",
            "interval": "daily",
            "max_sources": 5,
        }))
        assert result["interval"] == "daily"
        assert result["cron_schedule"] == "0 6 * * *"
        assert "cronjob" in result["instruction"]

    def test_schedule_weekly(self, rt):
        """Wöchentliche Planung."""
        result = json.loads(rt.research_schedule({
            "query": "Climate Science",
            "interval": "weekly",
        }))
        assert result["interval"] == "weekly"
        assert result["cron_schedule"] == "0 6 * * 1"

    def test_schedule_invalid_interval(self, rt):
        """Ungültiges Intervall."""
        result = json.loads(rt.research_schedule({
            "query": "Test", "interval": "yearly",
        }))
        assert result["status"] == "error"

    def test_schedule_missing_query(self, rt):
        """Planung ohne Query."""
        result = json.loads(rt.research_schedule({"query": ""}))
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# research_status mit show_orphans
# ---------------------------------------------------------------------------

class TestResearchStatusOrphans:
    def test_show_orphans(self, rt):
        """show_orphans zeigt hängengebliebene Plans."""
        # Einige Plans anlegen ohne Save
        for i in range(3):
            p = {"id": f"orphan{i}", "query": f"Orphan {i}", "depth": 1,
                 "max_sources": 5, "status": "planned",
                 "created_at": "2026-01-01T00:00:00+00:00"}
            (rt.PLANS_DIR / f"orphan{i}.json").write_text(json.dumps(p))

        # Auch einen mit Save (sollte nicht als Orphan zählen)
        start = json.loads(rt.research_start({"query": "Valid"}))
        rt.research_save({"research_id": start["research_id"],
                          "summary": "Valid", "status": "completed"})

        result = json.loads(rt.research_status({"research_id": "", "show_orphans": True}))
        assert result["orphans_count"] >= 3
        assert "research_cleanup" in result["message"]

    def test_show_orphans_only(self, rt):
        """show_orphans=true ohne research_id."""
        result = json.loads(rt.research_status({"research_id": "", "show_orphans": True}))
        # Darf nicht "error" sein
        assert result.get("status") != "error"
        assert "orphans_count" in result


# ---------------------------------------------------------------------------
# research_save mit nativen Arrays
# ---------------------------------------------------------------------------

class TestResearchSaveNativeArrays:
    def test_save_native_findings(self, rt):
        """findings als natives Array (kein JSON-String)."""
        start = json.loads(rt.research_start({"query": "Native Arrays"}))
        rid = start["research_id"]

        result = json.loads(rt.research_save({
            "research_id": rid,
            "summary": "Test mit nativen Arrays",
            "findings": [
                {"finding": "Erstes Finding", "sources": ["https://example.com"]},
                {"finding": "Zweites Finding", "sources": []},
            ],
            "sources": [
                {"url": "https://example.com", "title": "Beispiel", "relevance": 0.95},
            ],
            "status": "completed",
        }))
        assert result["findings_count"] == 2
        assert result["sources_count"] == 1

        # Prüfe persisted data
        saved = json.loads((rt.RESULTS_DIR / f"{rid}.json").read_text())
        assert len(saved["findings"]) == 2
        assert saved["findings"][0]["finding"] == "Erstes Finding"
        assert len(saved["sources"]) == 1
        assert saved["sources"][0]["url"] == "https://example.com"

    def test_save_native_empty_arrays(self, rt):
        """findings/sources als leere Arrays."""
        start = json.loads(rt.research_start({"query": "Empty Arrays"}))
        rid = start["research_id"]

        result = json.loads(rt.research_save({
            "research_id": rid, "summary": "Leer", "status": "completed",
            "findings": [], "sources": [],
        }))
        assert result["findings_count"] == 0
        assert result["sources_count"] == 0

    def test_save_backward_compat_json_string(self, rt):
        """Abwärtskompatibel: JSON-String wird noch akzeptiert."""
        start = json.loads(rt.research_start({"query": "Compat"}))
        rid = start["research_id"]

        result = json.loads(rt.research_save({
            "research_id": rid,
            "summary": "Backward compat",
            "findings": json.dumps([{"finding": "Compat", "sources": []}]),
            "sources": json.dumps([{"url": "https://example.com", "title": "X"}]),
            "status": "completed",
        }))
        assert result["findings_count"] == 1
        assert result["sources_count"] == 1

    def test_save_malformed_findings_native(self, rt):
        """Kaputte findings (kein JSON, kein Array)."""
        start = json.loads(rt.research_start({"query": "Malformed"}))
        result = json.loads(rt.research_save({
            "research_id": start["research_id"],
            "summary": "Test",
            "findings": "kein JSON",  # String, aber kein JSON
            "status": "completed",
        }))
        # Darf nicht crashen
        assert result["findings_count"] >= 0


# ---------------------------------------------------------------------------
# plan_follow Integration (lose Kopplung via Registry)
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="testet plan_follow Integration — Mock-Konflikt")
class TestResearchStartPlanFollow:

    def test_without_plan_follow(self, rt):
        """research_start funktioniert auch ohne plan_follow Plugin."""
        result = json.loads(rt.research_start({"query": "Ohne Plan-Follow"}))
        assert result["status"] != "error"
        # plan_follow sollte None sein (nicht geladen im Test-Mock)
        assert result.get("plan_follow") is None

    def test_with_plan_follow_mock(self, rt):
        """research_start erzeugt Plan wenn plan_follow verfügbar ist."""
        from tools import registry as tools_registry

        # plan_follow Handler simulieren
        def mock_plan_create(args):
            return json.dumps({
                "status": "created",
                "plan_id": "pf_testplan",
                "current_task": {
                    "task_id": "rs1",
                    "name": "Web-Recherche durchführen",
                    "status": "in_progress",
                },
            })

        tools_registry.set_plan_follow_mock(mock_plan_create)

        try:
            result = json.loads(rt.research_start({"query": "Mit Plan-Follow"}))
            pf = result.get("plan_follow")
            assert pf is not None, "plan_follow sollte ein Dict sein"
            assert pf.get("status") == "created"
            assert pf.get("plan_id") == "pf_testplan"
        finally:
            tools_registry.set_plan_follow_mock(None)

    def test_plan_follow_error_graceful(self, rt):
        """Fehler im plan_follow Handler crashen research_start nicht."""
        from tools import registry as tools_registry

        def broken_handler(args):
            raise RuntimeError("Simulierter Fehler")

        tools_registry.set_plan_follow_mock(broken_handler)

        try:
            result = json.loads(rt.research_start({"query": "Fehlerfall"}))
            assert result["status"] != "error"
            pf = result.get("plan_follow")
            assert pf is not None
            assert "error" in pf
        finally:
            tools_registry.set_plan_follow_mock(None)


# ---------------------------------------------------------------------------
# Path Traversal Security (P2 Fix)
# ---------------------------------------------------------------------------


class TestPathTraversal:
    """research_id darf keine Pfad-Trennzeichen enthalten."""

    def test_delete_path_traversal(self, rt):
        """research_delete blockt ../ in research_id."""
        result = json.loads(rt.research_delete({"research_id": "../../etc/passwd"}))
        assert result["status"] == "error"
        assert "Pfad" in result["error"] or "Trennzeichen" in result["error"]

    def test_save_path_traversal(self, rt):
        """research_save blockt ../ in research_id."""
        result = json.loads(rt.research_save({
            "research_id": "../etc/passwd",
            "summary": "test",
            "status": "completed",
        }))
        assert result["status"] == "error"
        assert "Pfad" in result["error"] or "Trennzeichen" in result["error"]

    def test_status_path_traversal(self, rt):
        """research_status blockt ../ in research_id."""
        result = json.loads(rt.research_status({"research_id": "../etc/passwd"}))
        assert result["status"] == "error"
        assert "Pfad" in result["error"] or "Trennzeichen" in result["error"]

    def test_export_path_traversal(self, rt):
        """research_export blockt ../ in research_id."""
        result = json.loads(rt.research_export({"research_id": "../../etc/passwd"}))
        assert result["status"] == "error"
        assert "Pfad" in result["error"] or "Trennzeichen" in result["error"]

    def test_compare_path_traversal(self, rt):
        """research_compare blockt ../ in research_ids."""
        result = json.loads(rt.research_compare({
            "research_ids": ["valid1", "../../etc/passwd"],
        }))
        assert result["status"] == "error"
        assert "Pfad" in result["error"] or "Trennzeichen" in result["error"]

    def test_valid_research_id_still_works(self, rt):
        """Normale research_ids funktionieren weiterhin."""
        start = json.loads(rt.research_start({"query": "Valid Test"}))
        rid = start["research_id"]
        assert len(rid) == 8
        assert "/" not in rid
