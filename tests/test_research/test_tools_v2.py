"""
test_tools_v2.py — Tests für die Tools: research_tag, research_update, research_search (Tags).
"""

import json

import pytest
from conftest import make_research_tools


@pytest.fixture
def rt(tmp_path):
    return make_research_tools(tmp_path)


# ---------------------------------------------------------------------------
# research_tag
# ---------------------------------------------------------------------------

class TestResearchTag:
    def test_add_tags(self, rt):
        """Tags zu einer Recherche hinzufuegen."""
        start = json.loads(rt.research_start({"query": "Tag Test"}))
        rid = start["research_id"]
        rt.research_save({
            "research_id": rid, "summary": "Done",
            "status": "completed", "tags": ["cbd", "legal"],
        })
        result = json.loads(rt.research_tag({
            "research_id": rid, "tags": ["deutschland", "eu"], "action": "add",
        }))
        assert result["tag_count"] == 4
        assert "deutschland" in result["tags"]
        assert "eu" in result["tags"]

    def test_remove_tags(self, rt):
        start = json.loads(rt.research_start({"query": "Remove Tags"}))
        rid = start["research_id"]
        rt.research_save({
            "research_id": rid, "summary": "Done",
            "status": "completed", "tags": ["a", "b", "c", "d"],
        })
        result = json.loads(rt.research_tag({
            "research_id": rid, "tags": ["b", "d"], "action": "remove",
        }))
        assert result["tag_count"] == 2
        assert "a" in result["tags"]
        assert "c" in result["tags"]
        assert "b" not in result["tags"]

    def test_set_tags(self, rt):
        start = json.loads(rt.research_start({"query": "Set Tags"}))
        rid = start["research_id"]
        rt.research_save({
            "research_id": rid, "summary": "Done",
            "status": "completed", "tags": ["old", "obsolete"],
        })
        result = json.loads(rt.research_tag({
            "research_id": rid, "tags": ["neu"], "action": "set",
        }))
        assert result["tag_count"] == 1
        assert result["tags"] == ["neu"]

    def test_clear_tags(self, rt):
        start = json.loads(rt.research_start({"query": "Clear Tags"}))
        rid = start["research_id"]
        rt.research_save({
            "research_id": rid, "summary": "Done",
            "status": "completed", "tags": ["a", "b"],
        })
        result = json.loads(rt.research_tag({
            "research_id": rid, "tags": [], "action": "clear",
        }))
        assert result["tag_count"] == 0
        assert result["tags"] == []

    def test_tag_missing_id(self, rt):
        result = json.loads(rt.research_tag({"tags": ["x"]}))
        assert "error" in result

    def test_tag_nonexistent(self, rt):
        result = json.loads(rt.research_tag({"research_id": "nonexistent", "tags": ["x"]}))
        assert "error" in result

    def test_tag_invalid_action(self, rt):
        start = json.loads(rt.research_start({"query": "Bad Action"}))
        rid = start["research_id"]
        rt.research_save({"research_id": rid, "summary": "Done", "status": "completed"})
        result = json.loads(rt.research_tag({
            "research_id": rid, "tags": ["x"], "action": "invalid",
        }))
        assert "error" in result

    def test_tag_deduplicates(self, rt):
        start = json.loads(rt.research_start({"query": "Dedup"}))
        rid = start["research_id"]
        rt.research_save({
            "research_id": rid, "summary": "Done",
            "status": "completed", "tags": ["cbd"],
        })
        result = json.loads(rt.research_tag({
            "research_id": rid, "tags": ["cbd", "cbd", "legal"], "action": "add",
        }))
        assert result["tag_count"] == 2
        assert result["tags"] == ["cbd", "legal"]

    def test_tag_on_plan_only(self, rt):
        start = json.loads(rt.research_start({"query": "Plan Tag"}))
        rid = start["research_id"]
        result = json.loads(rt.research_tag({
            "research_id": rid, "tags": ["planned"], "action": "add",
        }))
        assert result["tag_count"] == 1
        assert "planned" in result["tags"]


# ---------------------------------------------------------------------------
# research_update
# ---------------------------------------------------------------------------

class TestResearchUpdate:
    def test_update_summary(self, rt):
        start = json.loads(rt.research_start({"query": "Update Summary"}))
        rid = start["research_id"]
        rt.research_save({"research_id": rid, "summary": "Old", "status": "completed"})
        result = json.loads(rt.research_update({"research_id": rid, "summary": "New Summary"}))
        assert result["updated"] is True
        status = json.loads(rt.research_status({"research_id": rid}))
        assert "summary" in status
        assert "New Summary" in status["summary"]

    def test_update_status(self, rt):
        start = json.loads(rt.research_start({"query": "Update Status"}))
        rid = start["research_id"]
        rt.research_save({"research_id": rid, "summary": "Done", "status": "completed"})
        result = json.loads(rt.research_update({"research_id": rid, "status": "partial"}))
        assert result["updated"] is True

    def test_append_findings(self, rt):
        start = json.loads(rt.research_start({"query": "Append Findings"}))
        rid = start["research_id"]
        rt.research_save({
            "research_id": rid, "summary": "Done", "status": "completed",
            "findings": [{"finding": "First finding", "sources": ["url1"]}],
        })
        result = json.loads(rt.research_update({
            "research_id": rid,
            "append_findings": [{"finding": "Second finding", "sources": ["url2"]}],
        }))
        assert result["updated"] is True
        assert result["findings_count"] >= 2

    def test_append_sources(self, rt):
        start = json.loads(rt.research_start({"query": "Append Sources"}))
        rid = start["research_id"]
        rt.research_save({
            "research_id": rid, "summary": "Done", "status": "completed",
            "sources": [{"url": "https://example.com/1"}],
        })
        result = json.loads(rt.research_update({
            "research_id": rid,
            "append_sources": [{"url": "https://example.com/2", "title": "New Source"}],
        }))
        assert result["updated"] is True
        assert result["sources_count"] >= 2

    def test_update_not_saved(self, rt):
        start = json.loads(rt.research_start({"query": "Not Saved"}))
        rid = start["research_id"]
        result = json.loads(rt.research_update({"research_id": rid, "summary": "Test"}))
        assert "error" in result

    def test_update_no_changes(self, rt):
        start = json.loads(rt.research_start({"query": "No Changes"}))
        rid = start["research_id"]
        rt.research_save({"research_id": rid, "summary": "Done", "status": "completed"})
        result = json.loads(rt.research_update({"research_id": rid}))
        assert "error" in result

    def test_update_invalid_status(self, rt):
        start = json.loads(rt.research_start({"query": "Bad Status"}))
        rid = start["research_id"]
        rt.research_save({"research_id": rid, "summary": "Done", "status": "completed"})
        result = json.loads(rt.research_update({"research_id": rid, "status": "invalid"}))
        assert "error" in result

    def test_update_adds_timestamp(self, rt):
        start = json.loads(rt.research_start({"query": "Timestamp Check"}))
        rid = start["research_id"]
        rt.research_save({"research_id": rid, "summary": "Done", "status": "completed"})
        result = json.loads(rt.research_update({"research_id": rid, "summary": "Updated"}))
        assert "updated_at" in result


# ---------------------------------------------------------------------------
# research_search mit Tags
# ---------------------------------------------------------------------------

class TestResearchSearchTags:
    def test_search_by_tag(self, rt):
        start = json.loads(rt.research_start({"query": "CBD Legal"}))
        rid = start["research_id"]
        rt.research_save({
            "research_id": rid, "summary": "CBD research",
            "status": "completed", "tags": ["cbd", "legal"],
        })
        result = json.loads(rt.research_search({"query": "", "tags": ["cbd"]}))
        assert result["total"] >= 1

    def test_search_by_multiple_tags(self, rt):
        r1 = json.loads(rt.research_start({"query": "Steuern 2026"}))
        rt.research_save({
            "research_id": r1["research_id"], "summary": "Taxes",
            "status": "completed", "tags": ["steuern", "2026"],
        })
        r2 = json.loads(rt.research_start({"query": "CBD Bio"}))
        rt.research_save({
            "research_id": r2["research_id"], "summary": "CBD organic",
            "status": "completed", "tags": ["cbd", "bio"],
        })
        result = json.loads(rt.research_search({"query": "", "tags": ["cbd"]}))
        assert result["total"] >= 1

    def test_search_tag_no_match(self, rt):
        result = json.loads(rt.research_search({"query": "", "tags": ["nonexistent999"]}))
        assert result["total"] == 0

    def test_search_query_and_tag(self, rt):
        start = json.loads(rt.research_start({"query": "CBD Legalisierung Deutschland"}))
        rid = start["research_id"]
        rt.research_save({
            "research_id": rid, "summary": "CBD legal in DE",
            "status": "completed", "tags": ["cbd", "legal"],
        })
        result = json.loads(rt.research_search({"query": "Legalisierung", "tags": ["cbd"]}))
        assert result["total"] >= 1

    def test_export_includes_tags(self, rt):
        start = json.loads(rt.research_start({"query": "Tagged Research"}))
        rid = start["research_id"]
        rt.research_save({
            "research_id": rid, "summary": "Test",
            "status": "completed", "tags": ["tag1", "tag2"],
        })
        result = json.loads(rt.research_status({"research_id": rid}))
        assert result is not None


# ---------------------------------------------------------------------------
# research_merge
# ---------------------------------------------------------------------------

class TestResearchMerge:
    def test_merge_two(self, rt):
        r1 = json.loads(rt.research_start({"query": "CBD Legal"}))
        rt.research_save({
            "research_id": r1["research_id"], "summary": "CBD research",
            "status": "completed", "tags": ["cbd"],
            "findings": [{"finding": "CBD ist legal in DE"}],
            "sources": [{"url": "https://example.com/cbd"}],
        })
        r2 = json.loads(rt.research_start({"query": "Hanf Anbau"}))
        rt.research_save({
            "research_id": r2["research_id"], "summary": "Hemp growing",
            "status": "completed", "tags": ["hanf"],
            "findings": [{"finding": "Hanf braucht wenig Wasser"}],
            "sources": [{"url": "https://example.com/hanf"}],
        })
        result = json.loads(rt.research_merge({
            "research_ids": [r1["research_id"], r2["research_id"]],
        }))
        assert "research_id" in result
        assert result["findings_count"] == 2
        assert result["sources_count"] == 2
        assert "cbd" in result["tags"]
        assert "hanf" in result["tags"]

    def test_merge_deduplicates_findings(self, rt):
        r1 = json.loads(rt.research_start({"query": "Query A"}))
        rt.research_save({
            "research_id": r1["research_id"], "summary": "A", "status": "completed",
            "findings": [{"finding": "Gleiches Finding"}, {"finding": "Unique A"}],
        })
        r2 = json.loads(rt.research_start({"query": "Query B"}))
        rt.research_save({
            "research_id": r2["research_id"], "summary": "B", "status": "completed",
            "findings": [{"finding": "Gleiches Finding"}, {"finding": "Unique B"}],
        })
        result = json.loads(rt.research_merge({
            "research_ids": [r1["research_id"], r2["research_id"]],
        }))
        assert result["findings_count"] == 3

    def test_merge_too_few(self, rt):
        result = json.loads(rt.research_merge({"research_ids": ["only"]}))
        assert "error" in result

    def test_merge_too_many(self, rt):
        result = json.loads(rt.research_merge({"research_ids": ["1","2","3","4","5","6"]}))
        assert "error" in result

    def test_merge_nonexistent(self, rt):
        result = json.loads(rt.research_merge({"research_ids": ["abc123", "def456"]}))
        assert "error" in result


# ---------------------------------------------------------------------------
# research_stats
# ---------------------------------------------------------------------------

class TestResearchStats:
    def test_stats_empty(self, rt):
        result = json.loads(rt.research_stats({}))
        assert result["total_researches"] == 0

    def test_stats_with_data(self, rt):
        r1 = json.loads(rt.research_start({"query": "CBD"}))
        rt.research_save({"research_id": r1["research_id"], "summary": "CBD", "status": "completed", "tags": ["cbd"]})
        r2 = json.loads(rt.research_start({"query": "Hanf"}))
        rt.research_save({"research_id": r2["research_id"], "summary": "Hanf", "status": "completed", "tags": ["hanf", "anbau"]})
        result = json.loads(rt.research_stats({}))
        assert result["total_researches"] == 2
        assert "top_tags" in result

    def test_stats_with_orphans(self, rt):
        rt.research_start({"query": "Orphan"})
        result = json.loads(rt.research_stats({}))
        assert result["orphan_plans"] >= 1


# ---------------------------------------------------------------------------
# BM25-Suche
# ---------------------------------------------------------------------------

class TestBM25Search:
    def test_bm25_ranks_relevant_higher(self, rt):
        r1 = json.loads(rt.research_start({"query": "CBD Legalisierung in Deutschland"}))
        rt.research_save({
            "research_id": r1["research_id"],
            "summary": "CBD ist in Deutschland legal unter bestimmten Auflagen.",
            "status": "completed",
        })
        r2 = json.loads(rt.research_start({"query": "Steuertipps 2026"}))
        rt.research_save({
            "research_id": r2["research_id"],
            "summary": "Steuertipps f\u00fcr das Jahr 2026: Freibetr\u00e4ge.",
            "status": "completed",
        })
        result = json.loads(rt.research_search({"query": "CBD Legalisierung"}))
        assert result["total"] >= 1
        first = result["results"][0]
        assert "CBD" in first["query"] or "CBD" in first["summary"]

    def test_bm25_with_findings(self, rt):
        r1 = json.loads(rt.research_start({"query": "Europe CBD Laws"}))
        rt.research_save({
            "research_id": r1["research_id"], "summary": "Overview", "status": "completed",
            "findings": [{"finding": "Niederlande erlauben CBD-Verkauf in Coffeeshops"}],
        })
        result = json.loads(rt.research_search({"query": "Niederlande Coffeeshops"}))
        assert result["total"] >= 1

    def test_search_bm25_enabled_flag(self, rt):
        result = json.loads(rt.research_search({"query": "irgendwas"}))
        assert result.get("bm25_enabled") is True

    def test_search_empty_with_bm25(self, rt):
        result = json.loads(rt.research_search({"query": ""}))
        assert "results" in result


class TestSearchStatusFilter:
    def test_filter_by_status(self, rt):
        r1 = json.loads(rt.research_start({"query": "Completed"}))
        rt.research_save({"research_id": r1["research_id"], "summary": "Done", "status": "completed"})
        r2 = json.loads(rt.research_start({"query": "Partial"}))
        rt.research_save({"research_id": r2["research_id"], "summary": "Partial", "status": "partial"})
        result = json.loads(rt.research_search({"query": "", "status": "completed"}))
        assert result["total"] >= 1
        for r in result["results"]:
            assert r["status"] == "completed"

    def test_filter_status_no_match(self, rt):
        result = json.loads(rt.research_search({"query": "", "status": "failed"}))
        if result["total"] > 0:
            for r in result["results"]:
                assert r["status"] == "failed"


# ---------------------------------------------------------------------------
# research_verify
# ---------------------------------------------------------------------------

class TestResearchVerify:
    def test_verify_no_sources(self, rt):
        start = json.loads(rt.research_start({"query": "No Sources"}))
        rid = start["research_id"]
        rt.research_save({"research_id": rid, "summary": "Done", "status": "completed"})
        result = json.loads(rt.research_verify({"research_id": rid}))
        assert result["total_sources"] == 0

    def test_verify_nonexistent(self, rt):
        result = json.loads(rt.research_verify({"research_id": "nonexistent"}))
        assert "error" in result

    def test_verify_missing_id(self, rt):
        result = json.loads(rt.research_verify({}))
        assert "error" in result


# ---------------------------------------------------------------------------
# research_auto
# ---------------------------------------------------------------------------

class TestResearchAuto:
    def test_auto_starts_research(self, rt):
        """research_auto startet eine Recherche."""
        result = json.loads(rt.research_auto({"query": "CBD Legalisierung", "depth": 3, "max_sources": 5}))
        assert result["research_id"] is not None
        assert result["auto_mode"] is True
        assert "instruction" in result

    def test_auto_missing_query(self, rt):
        result = json.loads(rt.research_auto({}))
        assert "error" in result

    def test_auto_depth_clamping(self, rt):
        result = json.loads(rt.research_auto({"query": "Depth Test", "depth": 99, "max_sources": 99}))
        assert result["depth"] == 5
        assert result["max_sources"] == 20

    def test_auto_creates_plan_file(self, rt):
        """research_auto erzeugt Plan-Datei."""
        result = json.loads(rt.research_auto({"query": "Plan File Test"}))
        rid = result["research_id"]
        assert (rt.PLANS_DIR / f"{rid}.json").exists()


# ---------------------------------------------------------------------------
# research_export_all
# ---------------------------------------------------------------------------

class TestResearchExportAll:
    def test_export_all_empty(self, rt):
        """Export ohne Daten."""
        result = json.loads(rt.research_export_all({"format": "json"}))
        assert result["format"] == "json"
        assert result["total"] == 0

    def test_export_all_json(self, rt):
        """JSON-Export."""
        r = json.loads(rt.research_start({"query": "CBD"}))
        rt.research_save({"research_id": r["research_id"], "summary": "CBD", "status": "completed"})

        result = json.loads(rt.research_export_all({"format": "json"}))
        assert result["total"] >= 1
        assert "content" in result

    def test_export_all_markdown(self, rt):
        """Markdown-Export."""
        r = json.loads(rt.research_start({"query": "CBD Legalisierung"}))
        rt.research_save({"research_id": r["research_id"], "summary": "CBD legal in DE", "status": "completed"})

        result = json.loads(rt.research_export_all({"format": "markdown"}))
        assert result["total"] >= 1
        assert "content" in result

    def test_export_all_csv(self, rt):
        """CSV-Export."""
        r = json.loads(rt.research_start({"query": "CBD"}))
        rt.research_save({"research_id": r["research_id"], "summary": "CBD test", "status": "completed"})

        result = json.loads(rt.research_export_all({"format": "csv"}))
        assert result["total"] >= 1
        assert "content" in result

    def test_export_all_invalid_format(self, rt):
        """Ungültiges Format."""
        result = json.loads(rt.research_export_all({"format": "pdf"}))
        assert "error" in result
