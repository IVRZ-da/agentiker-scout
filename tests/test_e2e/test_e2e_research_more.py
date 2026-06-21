"""E2E tests for scout research_* tools — auto, cleanup, compare, export,
export_all, merge, schedule, stats, synthesize, tag, update, verify.

Requires E2E_TEST=1 environment variable.
Alle Tools operieren auf transienten Research-Daten (keine Firecrawl-Calls).
"""

import json
import os
import sys
import uuid

import pytest

_plugin_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _plugin_root not in sys.path:
    sys.path.insert(0, os.path.dirname(_plugin_root))

pytestmark = pytest.mark.run_e2e


# ---------------------------------------------------------------------------
# Helfer: Research anlegen & speichern (für Tools die eine research_id brauchen)
# ---------------------------------------------------------------------------

def _create_research(tmp_path) -> tuple[str, str, str, str]:
    """Create + save a research, return (research_id, query, summary, rid2)."""
    from scout.research.tools.crud import research_start, research_save

    suffix = uuid.uuid4().hex[:6]
    query = f"E2E Test Auto {suffix}"
    start = json.loads(research_start({"query": query, "depth": 1}))
    assert start.get("status") != "error", f"research_start failed: {start}"
    rid = start.get("research_id") or start.get("data", {}).get("research_id", "")
    assert rid, f"No research_id in: {start}"

    summary = f"E2E test summary {suffix}"
    save = json.loads(research_save({
        "research_id": rid,
        "summary": summary,
        "findings": [
            {"finding": "Test finding A", "sources": ["https://a.test.com"]},
            {"finding": "Test finding B", "sources": ["https://b.test.com"]},
        ],
        "sources": [
            {"url": "https://a.test.com", "title": "Source A", "relevance": 0.9},
            {"url": "https://b.test.com", "title": "Source B", "relevance": 0.8},
        ],
        "status": "completed",
    }))
    assert save.get("status") != "error", f"research_save failed: {save}"
    return rid, query, summary, suffix


def _delete_research(rid: str) -> None:
    """Delete a research by id."""
    from scout.research.tools.crud import research_delete
    json.loads(research_delete({"research_id": rid}))


# ═══════════════════════════════════════════════════════════════════════════
# research_auto
# ═══════════════════════════════════════════════════════════════════════════

class TestResearchAutoE2E:
    """research_auto: Startet autonome Recherche (Anweisungen, kein Firecrawl)."""

    def test_auto_basic(self):
        from scout.research.tools.crud import research_auto
        r = json.loads(research_auto({"query": "E2E Test Auto Basic"}))
        assert r.get("status") != "error", f"research_auto failed: {r}"
        assert r.get("research_id"), f"No research_id in: {r}"
        assert r.get("auto_mode") is True

    def test_auto_missing_query(self):
        from scout.research.tools.crud import research_auto
        r = json.loads(research_auto({}))
        assert r.get("status") == "error"

    def test_auto_with_depth(self):
        from scout.research.tools.crud import research_auto
        r = json.loads(research_auto({"query": "E2E Test Auto Depth", "depth": 5, "max_sources": 3}))
        assert r.get("status") != "error"
        # cleanup plan
        from scout.research.tools.base import PLANS_DIR
        rid = r["research_id"]
        plan_path = PLANS_DIR / f"{rid}.json"
        if plan_path.exists():
            plan_path.unlink()

    def test_auto_cleanup_plan(self):
        """Clean up the plan file created by auto after test."""
        from scout.research.tools.base import PLANS_DIR
        for f in list(PLANS_DIR.glob("*.json")):
            data = json.loads(f.read_text()) if f.stat().st_size > 0 else {}
            query = data.get("query", "")
            if "E2E Test Auto" in query:
                f.unlink()


# ═══════════════════════════════════════════════════════════════════════════
# research_cleanup
# ═══════════════════════════════════════════════════════════════════════════

class TestResearchCleanupE2E:
    """research_cleanup: Bereinigt alte/verwaiste Research-Daten."""

    def test_cleanup_plans(self):
        from scout.research.tools.crud import research_cleanup
        r = json.loads(research_cleanup({"action": "plans", "older_than_days": 1}))
        assert r.get("status") != "error"
        assert "deleted_plans" in r

    def test_cleanup_invalid_action(self):
        from scout.research.tools.crud import research_cleanup
        r = json.loads(research_cleanup({"action": "invalid"}))
        assert r.get("status") == "error"


# ═══════════════════════════════════════════════════════════════════════════
# research_compare
# ═══════════════════════════════════════════════════════════════════════════

class TestResearchCompareE2E:
    """research_compare: Vergleicht 2-3 Research-IDs."""

    def test_compare_two(self, tmp_path):
        rid1, _, _, _ = _create_research(tmp_path)
        rid2, _, _, _ = _create_research(tmp_path)
        from scout.research.tools.export import research_compare
        r = json.loads(research_compare({"research_ids": [rid1, rid2]}))
        assert r.get("status") != "error", f"research_compare failed: {r}"
        assert r.get("total_items") == 2
        _delete_research(rid1)
        _delete_research(rid2)

    def test_compare_too_few_ids(self):
        from scout.research.tools.export import research_compare
        r = json.loads(research_compare({"research_ids": ["one"]}))
        assert r.get("status") == "error"


# ═══════════════════════════════════════════════════════════════════════════
# research_export
# ═══════════════════════════════════════════════════════════════════════════

class TestResearchExportE2E:
    """research_export: Exportiert Research als Markdown oder Text."""

    def test_export_markdown(self, tmp_path):
        rid, _, _, _ = _create_research(tmp_path)
        from scout.research.tools.export import research_export
        r = json.loads(research_export({"research_id": rid, "format": "markdown"}))
        assert r.get("status") != "error", f"research_export failed: {r}"
        assert r.get("format") == "markdown"
        _delete_research(rid)

    def test_export_text(self, tmp_path):
        rid, _, _, _ = _create_research(tmp_path)
        from scout.research.tools.export import research_export
        r = json.loads(research_export({"research_id": rid, "format": "text"}))
        assert r.get("status") != "error"
        assert r.get("format") == "text"
        _delete_research(rid)

    def test_export_missing_id(self):
        from scout.research.tools.export import research_export
        r = json.loads(research_export({"research_id": ""}))
        assert r.get("status") == "error"

    def test_export_invalid_format(self, tmp_path):
        rid, _, _, _ = _create_research(tmp_path)
        from scout.research.tools.export import research_export
        r = json.loads(research_export({"research_id": rid, "format": "pdf"}))
        assert r.get("status") == "error"
        _delete_research(rid)


# ═══════════════════════════════════════════════════════════════════════════
# research_export_all
# ═══════════════════════════════════════════════════════════════════════════

class TestResearchExportAllE2E:
    """research_export_all: Batch-Export aller Recherchen."""

    def test_export_all_json(self):
        from scout.research.tools.export import research_export_all
        r = json.loads(research_export_all({"format": "json"}))
        assert r.get("status") != "error"
        assert r.get("format") == "json"

    def test_export_all_markdown(self):
        from scout.research.tools.export import research_export_all
        r = json.loads(research_export_all({"format": "markdown"}))
        assert r.get("status") != "error"
        assert r.get("format") == "markdown"

    def test_export_all_csv(self):
        from scout.research.tools.export import research_export_all
        r = json.loads(research_export_all({"format": "csv"}))
        assert r.get("status") != "error"
        assert r.get("format") == "csv"

    def test_export_all_invalid_format(self):
        from scout.research.tools.export import research_export_all
        r = json.loads(research_export_all({"format": "xml"}))
        assert r.get("status") == "error"


# ═══════════════════════════════════════════════════════════════════════════
# research_merge
# ═══════════════════════════════════════════════════════════════════════════

class TestResearchMergeE2E:
    """research_merge: Fasst mehrere Recherchen zu einer zusammen."""

    def test_merge_two(self, tmp_path):
        rid1, q1, _, _ = _create_research(tmp_path)
        rid2, q2, _, _ = _create_research(tmp_path)
        from scout.research.tools.export import research_merge
        r = json.loads(research_merge({
            "research_ids": [rid1, rid2],
            "new_summary": "Merged E2E test",
        }))
        assert r.get("status") != "error", f"research_merge failed: {r}"
        assert r.get("findings_count", 0) >= 2
        new_id = r.get("research_id", "")
        assert new_id
        _delete_research(rid1)
        _delete_research(rid2)
        _delete_research(new_id)

    def test_merge_too_few_ids(self):
        from scout.research.tools.export import research_merge
        r = json.loads(research_merge({"research_ids": ["single"]}))
        assert r.get("status") == "error"

    def test_merge_too_many_ids(self):
        from scout.research.tools.export import research_merge
        r = json.loads(research_merge({"research_ids": ["a", "b", "c", "d", "e", "f"]}))
        assert r.get("status") == "error"


# ═══════════════════════════════════════════════════════════════════════════
# research_schedule
# ═══════════════════════════════════════════════════════════════════════════

class TestResearchScheduleE2E:
    """research_schedule: Plant periodische Recherchen."""

    def test_schedule_daily(self):
        from scout.research.tools.schedule import research_schedule
        r = json.loads(research_schedule({"query": "E2E Test Schedule", "interval": "daily"}))
        assert r.get("status") != "error", f"research_schedule failed: {r}"
        assert r.get("interval") == "daily"
        assert r.get("research_id")

    def test_schedule_weekly(self):
        from scout.research.tools.schedule import research_schedule
        r = json.loads(research_schedule({"query": "E2E Test Schedule", "interval": "weekly"}))
        assert r.get("status") != "error"
        assert r.get("interval") == "weekly"

    def test_schedule_missing_query(self):
        from scout.research.tools.schedule import research_schedule
        r = json.loads(research_schedule({}))
        assert r.get("status") == "error"

    def test_schedule_invalid_interval(self):
        from scout.research.tools.schedule import research_schedule
        r = json.loads(research_schedule({"query": "E2E Test", "interval": "yearly"}))
        assert r.get("status") == "error"


# ═══════════════════════════════════════════════════════════════════════════
# research_stats
# ═══════════════════════════════════════════════════════════════════════════

class TestResearchStatsE2E:
    """research_stats: Metriken und Statistiken."""

    def test_stats_basic(self):
        from scout.research.tools.search import research_stats
        r = json.loads(research_stats({}))
        assert r.get("status") != "error", f"research_stats failed: {r}"
        assert "total_researches" in r
        assert "status_distribution" in r


# ═══════════════════════════════════════════════════════════════════════════
# research_synthesize
# ═══════════════════════════════════════════════════════════════════════════

class TestResearchSynthesizeE2E:
    """research_synthesize: Synthetisiert Ergebnisse via Honcho/Lokal."""

    def test_synthesize_basic(self, tmp_path):
        # Create at least one research for local matching
        rid, _, _, _ = _create_research(tmp_path)
        from scout.research.tools.export import research_synthesize
        r = json.loads(research_synthesize({"query": "E2E Test Auto", "reasoning_level": "medium"}))
        assert r.get("status") != "error", f"research_synthesize failed: {r}"
        _delete_research(rid)

    def test_synthesize_missing_query(self):
        from scout.research.tools.export import research_synthesize
        r = json.loads(research_synthesize({}))
        assert r.get("status") == "error"

    def test_synthesize_invalid_level(self, tmp_path):
        _create_research(tmp_path)
        from scout.research.tools.export import research_synthesize
        r = json.loads(research_synthesize({"query": "E2E Test", "reasoning_level": "extreme"}))
        assert r.get("status") != "error"  # defaults to medium


# ═══════════════════════════════════════════════════════════════════════════
# research_tag
# ═══════════════════════════════════════════════════════════════════════════

class TestResearchTagE2E:
    """research_tag: Tag-Verwaltung für Recherchen."""

    def test_tag_add(self, tmp_path):
        rid, _, _, _ = _create_research(tmp_path)
        from scout.research.tools.crud import research_tag
        r = json.loads(research_tag({"research_id": rid, "tags": ["e2e", "test"], "action": "add"}))
        assert r.get("status") != "error", f"research_tag add failed: {r}"
        assert "e2e" in r.get("tags", [])
        _delete_research(rid)

    def test_tag_remove(self, tmp_path):
        rid, _, _, _ = _create_research(tmp_path)
        from scout.research.tools.crud import research_tag
        json.loads(research_tag({"research_id": rid, "tags": ["e2e", "test"], "action": "add"}))
        r = json.loads(research_tag({"research_id": rid, "tags": ["e2e"], "action": "remove"}))
        assert r.get("status") != "error"
        assert "e2e" not in r.get("tags", [])
        _delete_research(rid)

    def test_tag_set(self, tmp_path):
        rid, _, _, _ = _create_research(tmp_path)
        from scout.research.tools.crud import research_tag
        r = json.loads(research_tag({"research_id": rid, "tags": ["replaced"], "action": "set"}))
        assert r.get("status") != "error"
        assert r.get("tags") == ["replaced"]
        _delete_research(rid)

    def test_tag_clear(self, tmp_path):
        rid, _, _, _ = _create_research(tmp_path)
        from scout.research.tools.crud import research_tag
        json.loads(research_tag({"research_id": rid, "tags": ["e2e"], "action": "add"}))
        r = json.loads(research_tag({"research_id": rid, "tags": [], "action": "clear"}))
        assert r.get("status") != "error"
        assert r.get("tags") == []
        _delete_research(rid)

    def test_tag_missing_id(self):
        from scout.research.tools.crud import research_tag
        r = json.loads(research_tag({"research_id": ""}))
        assert r.get("status") == "error"

    def test_tag_invalid_action(self, tmp_path):
        rid, _, _, _ = _create_research(tmp_path)
        from scout.research.tools.crud import research_tag
        r = json.loads(research_tag({"research_id": rid, "action": "unknown"}))
        assert r.get("status") == "error"
        _delete_research(rid)


# ═══════════════════════════════════════════════════════════════════════════
# research_update
# ═══════════════════════════════════════════════════════════════════════════

class TestResearchUpdateE2E:
    """research_update: Aktualisiert bestehende Recherche."""

    def test_update_summary(self, tmp_path):
        rid, _, _, _ = _create_research(tmp_path)
        from scout.research.tools.crud import research_update
        r = json.loads(research_update({"research_id": rid, "summary": "Updated summary"}))
        assert r.get("status") != "error", f"research_update failed: {r}"
        _delete_research(rid)

    def test_update_append_findings(self, tmp_path):
        rid, _, _, _ = _create_research(tmp_path)
        from scout.research.tools.crud import research_update
        r = json.loads(research_update({
            "research_id": rid,
            "append_findings": [{"finding": "New finding", "sources": ["https://new.test.com"]}],
        }))
        assert r.get("status") != "error"
        _delete_research(rid)

    def test_update_append_sources(self, tmp_path):
        rid, _, _, _ = _create_research(tmp_path)
        from scout.research.tools.crud import research_update
        r = json.loads(research_update({
            "research_id": rid,
            "append_sources": [{"url": "https://new.test.com", "title": "New Source", "relevance": 0.7}],
        }))
        assert r.get("status") != "error"
        _delete_research(rid)

    def test_update_missing_id(self):
        from scout.research.tools.crud import research_update
        r = json.loads(research_update({"research_id": ""}))
        assert r.get("status") == "error"

    def test_update_no_changes(self, tmp_path):
        rid, _, _, _ = _create_research(tmp_path)
        from scout.research.tools.crud import research_update
        r = json.loads(research_update({"research_id": rid}))
        assert r.get("status") == "error"
        _delete_research(rid)


# ═══════════════════════════════════════════════════════════════════════════
# research_verify
# ═══════════════════════════════════════════════════════════════════════════

class TestResearchVerifyE2E:
    """research_verify: Prüft Quellen-URLs auf Erreichbarkeit."""

    def test_verify_no_sources(self, tmp_path):
        """Test with research that has sources — verify returns results even
        if URLs are not reachable (the test creates research with fake URLs)."""
        rid, _, _, _ = _create_research(tmp_path)
        from scout.research.tools.crud import research_verify
        r = json.loads(research_verify({"research_id": rid}))
        assert r.get("status") != "error", f"research_verify failed: {r}"
        assert r.get("total_sources", 0) >= 2
        _delete_research(rid)

    def test_verify_missing_id(self):
        from scout.research.tools.crud import research_verify
        r = json.loads(research_verify({"research_id": ""}))
        assert r.get("status") == "error"

    def test_verify_nonexistent_id(self):
        from scout.research.tools.crud import research_verify
        r = json.loads(research_verify({"research_id": "doesnotexist"}))
        assert r.get("status") == "error"
