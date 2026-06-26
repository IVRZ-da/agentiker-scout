"""Tests für research/tools/crud.py — 85%+ Coverage Ziel."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ======================================================================
# Fixtures — NORMAL imports damit coverage messen kann
# ======================================================================

@pytest.fixture(autouse=True)
def setup_crud_env(tmp_path, monkeypatch):
    """Patched PLANS_DIR/RESULTS_DIR + reset_tracker Mock.

    Verwendet normale Imports (kein importlib) damit Coverage die
    scout.research.tools.crud Module messen kann.
    """
    # 1. Sicherstellen dass base die richtigen Pfade hat
    import scout.research.tools.base as base_mod

    plans_dir = tmp_path / "plans"
    results_dir = tmp_path / "results"
    plans_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(base_mod, "PLANS_DIR", plans_dir)
    monkeypatch.setattr(base_mod, "RESULTS_DIR", results_dir)
    monkeypatch.setattr(base_mod, "PLUGIN_DIR", tmp_path)
    monkeypatch.setattr(base_mod, "DATA_DIR", tmp_path / "data")
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)

    # 2. crud importieren (es importiert from .base → bekommt gepatchte Werte)
    # Modul neu laden damit es die gepatchten base-Werte bekommt
    if "scout.research.tools.crud" in sys.modules:
        del sys.modules["scout.research.tools.crud"]

    import scout.research.tools.crud as crud_mod

    # 3. reset_tracker mocken (wird in research_start und research_save verwendet)
    crud_mod.reset_tracker = lambda rid=None: None

    yield crud_mod, plans_dir, results_dir


@pytest.fixture
def crud(setup_crud_env):
    """Return the crud module."""
    return setup_crud_env[0]


@pytest.fixture
def pdir(setup_crud_env):
    """Return patched PLANS_DIR."""
    return setup_crud_env[1]


@pytest.fixture
def rdir(setup_crud_env):
    """Return patched RESULTS_DIR."""
    return setup_crud_env[2]


def _start_ok(crud, query="Test Query"):
    """Helper: start and return (research_id, parsed_result)."""
    result = json.loads(crud.research_start({"query": query}))
    return result.get("research_id", ""), result


# ======================================================================
# research_start — Tests
# ======================================================================

class TestResearchStart:
    """Deckt lines 46, 49, 73-74, 81, 86 ab."""

    def test_query_empty(self, crud):
        """Fehler wenn query fehlt."""
        result = json.loads(crud.research_start({"query": ""}))
        assert "error" in result

    def test_query_too_short(self, crud):
        """Fehler wenn query < 3 Zeichen (line 46)."""
        result = json.loads(crud.research_start({"query": "ab"}))
        assert "error" in result
        assert "zu kurz" in result.get("error", "")

    def test_query_is_test_string(self, crud):
        """Fehler wenn query ein Test-String ist (line 49)."""
        for test_val in ("test", "abc", "foo", "bar", "asdf", "xyz"):
            result = json.loads(crud.research_start({"query": test_val}))
            assert "error" in result, f"Expected error for query='{test_val}'"
            assert "Test" in result.get("error", "")

    def test_query_too_long(self, crud):
        """Fehler wenn query > 2000 Zeichen."""
        result = json.loads(crud.research_start({"query": "x" * 2001}))
        assert "error" in result
        assert "zu lang" in result.get("error", "")

    def test_reset_tracker_import_error(self, crud, monkeypatch):
        """reset_tracker import schlägt fehl — logger.debug (lines 73-74).

        Entfernt das Attribut 'reset_tracker' aus dem research_hooks-Modul,
        sodass der 'from scout.research.research_hooks import reset_tracker'
        im try-Block von research_start einen ImportError auslöst.
        """
        debug_msgs = []

        class _CatchLogger:
            def debug(self, msg, *args):
                debug_msgs.append(msg % args if args else msg)

        monkeypatch.setattr(crud, "logger", _CatchLogger())

        # Direkt auf das research_hooks-Modul zugreifen und reset_tracker entfernen
        import scout.research.research_hooks as rh_mod
        monkeypatch.delattr(rh_mod, "reset_tracker", raising=False)

        result = json.loads(crud.research_start({"query": "Python Testing Framework"}))
        assert "error" not in result
        assert any("reset_tracker" in str(m) for m in debug_msgs)

    def test_plan_follow_status_created(self, crud):
        """plan_follow_result hat status 'created' (line 81).

        Die tools.registry Mock aus conftest liefert status=ok+plan_id.
        """
        result = json.loads(crud.research_start({"query": "Künstliche Intelligenz"}))
        assert "error" not in result
        assert "research_id" in result

    def test_plan_follow_error(self, crud, monkeypatch):
        """plan_follow_result hat error (line 86)."""
        monkeypatch.setattr(
            crud,
            "_try_create_plan_follow_plan",
            lambda q, rid: {"status": "error", "error": "Mock-Fehler"}
        )
        result = json.loads(crud.research_start({"query": "Quantenphysik"}))
        assert "error" not in result

    def test_plan_follow_returns_none(self, crud, monkeypatch):
        """plan_follow_result ist None (plan_follow nicht verfügbar)."""
        monkeypatch.setattr(crud, "_try_create_plan_follow_plan", lambda q, rid: None)
        result = json.loads(crud.research_start({"query": "Machine Learning Grundlagen"}))
        assert "error" not in result

    def test_successful_start(self, crud, pdir):
        """Erfolgreicher Start einer Recherche."""
        result = json.loads(crud.research_start({
            "query": "Python Testing", "depth": 2, "max_sources": 5,
        }))
        assert "error" not in result
        rid = result.get("research_id")
        assert rid is not None
        assert (pdir / f"{rid}.json").exists()


# ======================================================================
# research_save — Tests
# ======================================================================

class TestResearchSave:
    """Deckt lines 168, 176-177, 185-186, 188, 197-198 ab."""

    def _setup_plan(self, crud, pdir) -> tuple:
        """Erzeugt einen Plan und gibt (research_id, plan_path) zurück."""
        rid, _ = _start_ok(crud, "Deep Learning Trends")
        assert (pdir / f"{rid}.json").exists()
        return rid, pdir / f"{rid}.json"

    def test_missing_research_id(self, crud):
        """Fehler wenn research_id fehlt."""
        result = json.loads(crud.research_save({}))
        assert "error" in result
        assert "erforderlich" in result.get("error", "")

    def test_invalid_research_id(self, crud):
        """Fehler bei ungültiger research_id."""
        result = json.loads(crud.research_save({"research_id": "abc/def"}))
        assert "error" in result
        assert "Pfad-Trennzeichen" in result.get("error", "")

    def test_no_plan_or_result(self, crud):
        """Fehler wenn weder Plan noch Ergebnis existiert."""
        result = json.loads(crud.research_save({"research_id": "nonexist"}))
        assert "error" in result

    def test_result_already_exists(self, crud, rdir, pdir):
        """Fehler wenn Ergebnis bereits existiert."""
        rid, _ = self._setup_plan(crud, pdir)
        (rdir / f"{rid}.json").write_text(json.dumps({"id": rid}))
        result = json.loads(crud.research_save({
            "research_id": rid, "summary": "Test",
        }))
        assert "error" in result
        assert "bereits gespeichert" in result.get("error", "")

    def test_missing_summary(self, crud, pdir):
        """Fehler wenn summary fehlt."""
        rid, _ = self._setup_plan(crud, pdir)
        result = json.loads(crud.research_save({"research_id": rid}))
        assert "error" in result
        assert "summary" in result.get("error", "")

    def test_invalid_status(self, crud, pdir):
        """Fehler bei ungültigem status."""
        rid, _ = self._setup_plan(crud, pdir)
        result = json.loads(crud.research_save({
            "research_id": rid, "summary": "Test", "status": "invalid",
        }))
        assert "error" in result
        assert "status muss" in result.get("error", "")

    def test_findings_not_a_list(self, crud, pdir):
        """findings ist kein list — wird zu [] (line 168)."""
        rid, _ = self._setup_plan(crud, pdir)
        result = json.loads(crud.research_save({
            "research_id": rid, "summary": "Zusammenfassung",
            "findings": {"not": "a list"},
        }))
        assert "error" not in result

    def test_findings_as_json_string(self, crud, pdir):
        """findings als JSON-String (lines 176-177)."""
        rid, _ = self._setup_plan(crud, pdir)
        result = json.loads(crud.research_save({
            "research_id": rid, "summary": "Test",
            "findings": json.dumps([
                {"finding": "Erkenntnis 1", "sources": ["https://example.com"]}
            ]),
            "sources": json.dumps([
                {"url": "https://example.com", "title": "Example", "relevance": 0.9}
            ]),
        }))
        assert "error" not in result

    def test_findings_json_decode_error(self, crud, pdir):
        """findings JSON-String ist kaputt — wird zu [] (line 166)."""
        rid, _ = self._setup_plan(crud, pdir)
        result = json.loads(crud.research_save({
            "research_id": rid, "summary": "Test",
            "findings": "{definitiv kein json}",
        }))
        assert "error" not in result

    def test_sources_json_decode_error(self, crud, pdir):
        """sources JSON-String ist kaputt — wird zu [] (lines 185-186)."""
        rid, _ = self._setup_plan(crud, pdir)
        result = json.loads(crud.research_save({
            "research_id": rid, "summary": "Test",
            "sources": "{auch kein json}",
        }))
        assert "error" not in result

    def test_sources_not_a_list(self, crud, pdir):
        """sources ist kein list — wird zu [] (line 188)."""
        rid, _ = self._setup_plan(crud, pdir)
        result = json.loads(crud.research_save({
            "research_id": rid, "summary": "Test",
            "sources": {"not": "a list"},
        }))
        assert "error" not in result

    def test_sources_as_strings(self, crud, pdir):
        """sources als Liste von Strings (lines 197-198)."""
        rid, _ = self._setup_plan(crud, pdir)
        result = json.loads(crud.research_save({
            "research_id": rid, "summary": "Test",
            "findings": [], "sources": ["https://example.com", "https://example.org"],
        }))
        assert "error" not in result

    def test_findings_as_string_items(self, crud, pdir):
        """findings als Liste von Strings (line 176-177)."""
        rid, _ = self._setup_plan(crud, pdir)
        result = json.loads(crud.research_save({
            "research_id": rid, "summary": "Test",
            "findings": ["Finding 1", "Finding 2"],
        }))
        assert "error" not in result

    def test_happy_path_with_tags(self, crud, pdir):
        """Erfolgreicher Save mit allen Optionen."""
        rid, _ = self._setup_plan(crud, pdir)
        result = json.loads(crud.research_save({
            "research_id": rid, "summary": "Wichtige Zusammenfassung",
            "status": "completed",
            "findings": [{"finding": "KI Trend 1", "sources": ["https://example.com"]}],
            "sources": [{"url": "https://example.com", "title": "Example", "relevance": 0.8}],
            "tags": ["ai", "deep-learning"],
        }))
        assert "error" not in result


# ======================================================================
# research_delete — Tests
# ======================================================================

class TestResearchDelete:

    def test_delete_plan_only(self, crud, pdir):
        """Löscht nur die Plan-Datei."""
        rid, _ = _start_ok(crud, "Zu löschende Recherche")
        del_result = json.loads(crud.research_delete({"research_id": rid}))
        assert "error" not in del_result
        assert del_result.get("deleted_plan") is True
        assert del_result.get("deleted_result") is False

    def test_delete_nonexistent(self, crud):
        """Fehler bei nicht existierender Recherche."""
        result = json.loads(crud.research_delete({"research_id": "nonexist"}))
        assert "error" in result

    def test_delete_invalid_id(self, crud):
        """Fehler bei ungültiger ID."""
        result = json.loads(crud.research_delete({"research_id": "../etc"}))
        assert "error" in result

    def test_delete_empty_id(self, crud):
        """Leere research_id."""
        result = json.loads(crud.research_delete({"research_id": ""}))
        assert "error" in result


# ======================================================================
# research_cleanup — Tests
# ======================================================================

class TestResearchCleanup:
    """Deckt lines 328-329, 332-342 ab."""

    def test_invalid_action(self, crud):
        """Fehler bei unbekannter action."""
        result = json.loads(crud.research_cleanup({"action": "invalid"}))
        assert "error" in result

    def test_cleanup_no_files(self, crud):
        """Cleanup wenn keine Dateien existieren."""
        result = json.loads(crud.research_cleanup({"action": "plans", "older_than_days": 1}))
        assert "error" not in result
        assert result.get("deleted_plans", 0) == 0

    def test_cleanup_plans_old_orphan(self, crud, pdir):
        """Löscht alte Orphan-Pläne (gültiges Datum)."""
        (pdir / "old001.json").write_text(json.dumps({
            "id": "old001", "query": "alte recherche",
            "created_at": "2020-01-01T00:00:00+00:00", "status": "planned",
        }))
        result = json.loads(crud.research_cleanup({"action": "plans", "older_than_days": 1}))
        assert "error" not in result
        assert not (pdir / "old001.json").exists()

    def test_cleanup_plans_invalid_created_at(self, crud, pdir):
        """Ungültiges created_at — wird übersprungen (lines 328-329)."""
        (pdir / "bad001.json").write_text(json.dumps({
            "id": "bad001", "query": "bad date",
            "created_at": "kein-datum", "status": "planned",
        }))
        result = json.loads(crud.research_cleanup({"action": "plans", "older_than_days": 1}))
        assert "error" not in result
        assert (pdir / "bad001.json").exists()  # nicht gelöscht

    def test_cleanup_all_action(self, crud, rdir):
        """action='all' — löscht auch alte Results (lines 332-342)."""
        (rdir / "res001.json").write_text(json.dumps({
            "id": "res001", "query": "old result",
            "saved_at": "2020-06-01T00:00:00+00:00",
        }))
        result = json.loads(crud.research_cleanup({"action": "all", "older_than_days": 1}))
        assert "error" not in result
        assert result.get("deleted_results", 0) >= 1
        assert not (rdir / "res001.json").exists()

    def test_cleanup_all_invalid_saved_at(self, crud, rdir):
        """Ungültiges saved_at — Result wird übersprungen (line 341-342)."""
        (rdir / "badres.json").write_text(json.dumps({
            "id": "badres", "query": "bad saved_at",
            "saved_at": "definitiv-kein-iso",
        }))
        result = json.loads(crud.research_cleanup({"action": "all", "older_than_days": 1}))
        assert "error" not in result
        assert (rdir / "badres.json").exists()

    def test_cleanup_all_empty_saved_at(self, crud, rdir):
        """Leeres saved_at — wird übersprungen."""
        (rdir / "no_saved.json").write_text(json.dumps({
            "id": "no_saved", "query": "no saved_at", "saved_at": "",
        }))
        result = json.loads(crud.research_cleanup({"action": "all", "older_than_days": 1}))
        assert "error" not in result
        assert (rdir / "no_saved.json").exists()

    def test_cleanup_default_action(self, crud):
        """Cleanup ohne action -> default 'plans'."""
        result = json.loads(crud.research_cleanup({}))
        assert "error" not in result


# ======================================================================
# research_tag — Tests
# ======================================================================

class TestResearchTag:
    """Deckt lines 368, 372, 388 ab."""

    def _setup_result(self, crud, rdir):
        """Erzeugt ein gespeichertes Result und gibt research_id zurück."""
        rid, _ = _start_ok(crud, "Tag Test Recherche")
        crud.research_save({"research_id": rid, "summary": "Test", "findings": []})
        return rid

    def test_missing_research_id(self, crud):
        """Fehler wenn research_id fehlt."""
        result = json.loads(crud.research_tag({}))
        assert "error" in result

    def test_validate_id_error(self, crud):
        """validate_id schlägt fehl (line 368)."""
        result = json.loads(crud.research_tag({"research_id": "../../etc"}))
        assert "error" in result
        assert "Pfad-Trennzeichen" in result.get("error", "")

    def test_tags_not_a_list(self, crud, rdir):
        """tags ist kein list — wird zu [str(tags)] (line 372)."""
        rid = self._setup_result(crud, rdir)
        result = json.loads(crud.research_tag({
            "research_id": rid, "tags": "single-tag",
        }))
        assert "error" not in result
        assert "single-tag" in result.get("tags", [])

    def test_existing_not_a_list(self, crud, rdir):
        """existing tags ist kein list — wird zu [] (line 388)."""
        rid = self._setup_result(crud, rdir)
        result_path = rdir / f"{rid}.json"
        data = json.loads(result_path.read_text())
        data["tags"] = {"some": "dict"}
        result_path.write_text(json.dumps(data))
        result = json.loads(crud.research_tag({
            "research_id": rid, "tags": ["new-tag"],
        }))
        assert "error" not in result

    def test_tag_add(self, crud, rdir):
        """Tag hinzufügen."""
        rid = self._setup_result(crud, rdir)
        result = json.loads(crud.research_tag({
            "research_id": rid, "tags": ["ai", "deep-learning"], "action": "add",
        }))
        assert "error" not in result
        assert "ai" in result.get("tags", [])
        assert "deep-learning" in result.get("tags", [])

    def test_tag_remove(self, crud, rdir):
        """Tag entfernen."""
        rid = self._setup_result(crud, rdir)
        crud.research_tag({"research_id": rid, "tags": ["ai", "ml"], "action": "add"})
        result = json.loads(crud.research_tag({
            "research_id": rid, "tags": ["ai"], "action": "remove",
        }))
        assert "error" not in result
        assert "ai" not in result.get("tags", [])
        assert "ml" in result.get("tags", [])

    def test_tag_set(self, crud, rdir):
        """Tags setzen (ersetzen)."""
        rid = self._setup_result(crud, rdir)
        result = json.loads(crud.research_tag({
            "research_id": rid, "tags": ["only-this"], "action": "set",
        }))
        assert "error" not in result
        assert result.get("tags") == ["only-this"]

    def test_tag_clear(self, crud, rdir):
        """Tags leeren."""
        rid = self._setup_result(crud, rdir)
        crud.research_tag({"research_id": rid, "tags": ["temp"], "action": "add"})
        result = json.loads(crud.research_tag({
            "research_id": rid, "tags": [], "action": "clear",
        }))
        assert "error" not in result
        assert result.get("tags") == []

    def test_tag_invalid_action(self, crud, rdir):
        """Unbekannte Aktion."""
        rid = self._setup_result(crud, rdir)
        result = json.loads(crud.research_tag({
            "research_id": rid, "tags": [], "action": "unknown",
        }))
        assert "error" in result

    def test_tag_result_not_found(self, crud):
        """Recherche nicht gefunden."""
        result = json.loads(crud.research_tag({
            "research_id": "nonexist", "tags": ["test"],
        }))
        assert "error" in result

    def test_tag_plan_fallback(self, crud, pdir):
        """Wenn kein Result existiert, fallback auf Plan."""
        rid, _ = _start_ok(crud, "Plan-only Recherche")
        tag_result = json.loads(crud.research_tag({
            "research_id": rid, "tags": ["plan-tag"], "action": "set",
        }))
        assert "error" not in tag_result
        assert "plan-tag" in tag_result.get("tags", [])

    def test_tag_empty_id(self, crud):
        """Leere research_id."""
        result = json.loads(crud.research_tag({"research_id": ""}))
        assert "error" in result


# ======================================================================
# research_update — Tests
# ======================================================================

class TestResearchUpdate:
    """Deckt lines 421, 425, 437, 458-461, 469-470, 477-480, 489-490 ab."""

    def _setup_result(self, crud, rdir):
        """Erzeugt ein gespeichertes Result."""
        rid, _ = _start_ok(crud, "Update Test")
        crud.research_save({
            "research_id": rid, "summary": "Original Summary",
            "findings": [{"finding": "Original", "sources": ["https://orig.com"]}],
            "sources": [{"url": "https://orig.com", "title": "Original", "relevance": 0.5}],
        })
        return rid

    def test_missing_research_id(self, crud):
        """Fehler wenn research_id fehlt (line 421)."""
        result = json.loads(crud.research_update({}))
        assert "error" in result
        assert "erforderlich" in result.get("error", "")

    def test_validate_id_error(self, crud):
        """validate_id schlägt fehl (line 425)."""
        result = json.loads(crud.research_update({"research_id": "a/b"}))
        assert "error" in result
        assert "Pfad-Trennzeichen" in result.get("error", "")

    def test_result_not_found(self, crud):
        """Kein gespeichertes Result vorhanden."""
        result = json.loads(crud.research_update({"research_id": "nonexist"}))
        assert "error" in result
        assert "Keine gespeicherte" in result.get("error", "")

    def test_corrupt_data_empty_file(self, crud, rdir):
        """Korrupte Daten — leere Datei (line 437)."""
        (rdir / "corrupt001.json").write_text("")
        result = json.loads(crud.research_update({"research_id": "corrupt001"}))
        assert "error" in result
        assert "korrupt" in result.get("error", "")

    def test_corrupt_data_invalid_json(self, crud, rdir):
        """Korrupte Daten — ungültiges JSON (line 437)."""
        (rdir / "corrupt002.json").write_text("{definitiv kein json}")
        result = json.loads(crud.research_update({"research_id": "corrupt002"}))
        assert "error" in result
        assert "korrupt" in result.get("error", "")

    def test_update_summary(self, crud, rdir):
        """Summary aktualisieren."""
        rid = self._setup_result(crud, rdir)
        result = json.loads(crud.research_update({
            "research_id": rid, "summary": "Aktualisierte Zusammenfassung",
        }))
        assert "error" not in result

    def test_update_status(self, crud, rdir):
        """Status aktualisieren."""
        rid = self._setup_result(crud, rdir)
        result = json.loads(crud.research_update({
            "research_id": rid, "status": "partial",
        }))
        assert "error" not in result

    def test_update_invalid_status(self, crud, rdir):
        """Ungültiger Status."""
        rid = self._setup_result(crud, rdir)
        result = json.loads(crud.research_update({
            "research_id": rid, "status": "invalid",
        }))
        assert "error" in result

    def test_append_findings_json_decode_error(self, crud, rdir):
        """append_findings JSON-Decode Error (lines 458-461)."""
        rid = self._setup_result(crud, rdir)
        result = json.loads(crud.research_update({
            "research_id": rid, "summary": "Updated",
            "append_findings": "{kaputt",
        }))
        assert "error" not in result

    def test_append_findings_string_list(self, crud, rdir):
        """append_findings als String (lines 469-470)."""
        rid = self._setup_result(crud, rdir)
        result = json.loads(crud.research_update({
            "research_id": rid, "summary": "Updated",
            "append_findings": json.dumps(["String Finding 1", "String Finding 2"]),
        }))
        assert "error" not in result

    def test_append_sources_json_decode_error(self, crud, rdir):
        """append_sources JSON-Decode Error (lines 477-480)."""
        rid = self._setup_result(crud, rdir)
        result = json.loads(crud.research_update({
            "research_id": rid, "summary": "Updated",
            "append_sources": json.dumps({"not": "a list"}),
        }))
        assert "error" not in result

    def test_append_sources_string_list(self, crud, rdir):
        """append_sources als String-Liste (lines 489-490)."""
        rid = self._setup_result(crud, rdir)
        result = json.loads(crud.research_update({
            "research_id": rid, "summary": "Updated",
            "append_sources": json.dumps([
                "https://new-source.com", "https://another-source.com",
            ]),
        }))
        assert "error" not in result

    def test_append_findings_dict(self, crud, rdir):
        """append_findings mit Dicts."""
        rid = self._setup_result(crud, rdir)
        result = json.loads(crud.research_update({
            "research_id": rid, "summary": "Updated",
            "append_findings": [
                {"finding": "Neue Erkenntnis", "sources": ["https://neu.com"]}
            ],
        }))
        assert "error" not in result

    def test_append_sources_dict(self, crud, rdir):
        """append_sources mit Dicts."""
        rid = self._setup_result(crud, rdir)
        result = json.loads(crud.research_update({
            "research_id": rid, "summary": "Updated",
            "append_sources": [
                {"url": "https://neu.com", "title": "Neu", "relevance": 0.7}
            ],
        }))
        assert "error" not in result

    def test_no_updates(self, crud, rdir):
        """Keine Änderungen — Fehler."""
        rid = self._setup_result(crud, rdir)
        result = json.loads(crud.research_update({"research_id": rid}))
        assert "error" in result
        assert "Keine Änderungen" in result.get("error", "")

    def test_update_empty_id(self, crud):
        """Leere research_id."""
        result = json.loads(crud.research_update({"research_id": ""}))
        assert "error" in result


# ======================================================================
# research_verify — Tests
# ======================================================================

class TestResearchVerify:
    """Deckt lines 525, 533, 546-588 ab."""

    def _setup_result(self, crud, rdir):
        """Erzeugt ein gespeichertes Result mit Sources."""
        rid, _ = _start_ok(crud, "Verify Test")
        crud.research_save({
            "research_id": rid, "summary": "Verify test summary",
            "findings": [{"finding": "Test", "sources": ["https://example.com"]}],
            "sources": [{"url": "https://example.com", "title": "Example", "relevance": 0.8}],
        })
        return rid

    def test_missing_research_id(self, crud):
        """Fehler wenn research_id fehlt."""
        result = json.loads(crud.research_verify({}))
        assert "error" in result

    def test_validate_id_error(self, crud):
        """validate_id schlägt fehl (line 525)."""
        result = json.loads(crud.research_verify({"research_id": "../../etc"}))
        assert "error" in result
        assert "Pfad-Trennzeichen" in result.get("error", "")

    def test_result_not_found(self, crud):
        """Kein gespeichertes Result."""
        result = json.loads(crud.research_verify({"research_id": "nonexist"}))
        assert "error" in result
        assert "Keine gespeicherte" in result.get("error", "")

    def test_corrupt_data(self, crud, rdir):
        """Korrupte Daten (line 533)."""
        (rdir / "corrupt_verify.json").write_text("")
        result = json.loads(crud.research_verify({"research_id": "corrupt_verify"}))
        assert "error" in result
        assert "korrupt" in result.get("error", "")

    def test_no_sources(self, crud, rdir):
        """Keine Sources — ok mit 0 Quellen."""
        rid, _ = _start_ok(crud, "No Sources Test")
        crud.research_save({
            "research_id": rid, "summary": "No sources", "findings": [], "sources": [],
        })
        verify_result = json.loads(crud.research_verify({"research_id": rid}))
        assert "error" not in verify_result
        assert verify_result.get("total_sources", -1) == 0

    def test_verify_with_sources(self, crud, rdir):
        """Verify mit Quellen (lines 546-588)."""
        rid = self._setup_result(crud, rdir)
        with patch.object(crud.urllib.request, "urlopen") as mock_urlopen:
            mock_response = type("MockResponse", (), {
                "status": 200,
                "__enter__": lambda s: s,
                "__exit__": lambda *a: None,
            })()
            mock_urlopen.return_value = mock_response
            verify_result = json.loads(crud.research_verify({"research_id": rid}))
            assert "error" not in verify_result
            assert verify_result.get("verified", 0) >= 1
            assert verify_result.get("failed", 0) == 0

    def test_verify_http_error(self, crud, rdir):
        """HTTP-Fehler (lines 570-578)."""
        rid = self._setup_result(crud, rdir)
        with patch.object(crud.urllib.request, "urlopen") as mock_urlopen:
            import urllib.error
            mock_urlopen.side_effect = urllib.error.HTTPError(
                "https://example.com", 404, "Not Found", {}, None
            )
            verify_result = json.loads(crud.research_verify({"research_id": rid}))
            assert "error" not in verify_result
            assert verify_result.get("failed", 0) >= 1

    def test_verify_url_error(self, crud, rdir):
        """URL-Error (lines 570-578)."""
        rid = self._setup_result(crud, rdir)
        with patch.object(crud.urllib.request, "urlopen") as mock_urlopen:
            import urllib.error
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
            verify_result = json.loads(crud.research_verify({"research_id": rid}))
            assert "error" not in verify_result
            assert verify_result.get("failed", 0) >= 1

    def test_verify_generic_exception(self, crud, rdir):
        """Generische Exception (lines 579-586)."""
        rid = self._setup_result(crud, rdir)
        with patch.object(crud.urllib.request, "urlopen") as mock_urlopen:
            mock_urlopen.side_effect = RuntimeError("Überraschung!")
            verify_result = json.loads(crud.research_verify({"research_id": rid}))
            assert "error" not in verify_result
            assert verify_result.get("failed", 0) >= 1

    def test_verify_empty_url(self, crud, rdir):
        """Quelle mit leerer URL — wird übersprungen."""
        rid = self._setup_result(crud, rdir)
        result_path = rdir / f"{rid}.json"
        data = json.loads(result_path.read_text())
        data["sources"].append({"url": "", "title": "Empty", "relevance": 0})
        result_path.write_text(json.dumps(data))
        with patch.object(crud.urllib.request, "urlopen") as mock_urlopen:
            mock_response = type("MockResponse", (), {
                "status": 200, "__enter__": lambda s: s, "__exit__": lambda *a: None,
            })()
            mock_urlopen.return_value = mock_response
            verify_result = json.loads(crud.research_verify({"research_id": rid}))
            assert "error" not in verify_result

    def test_verify_with_source_as_string(self, crud, rdir):
        """Source als String (line 551 'else str(s)')."""
        rid, _ = _start_ok(crud, "String Source Test")
        (rdir / f"{rid}.json").write_text(json.dumps({
            "id": rid, "query": "String Source Test",
            "sources": ["https://example.com/string-source"],
        }))
        with patch.object(crud.urllib.request, "urlopen") as mock_urlopen:
            mock_response = type("MockResponse", (), {
                "status": 200, "__enter__": lambda s: s, "__exit__": lambda *a: None,
            })()
            mock_urlopen.return_value = mock_response
            verify_result = json.loads(crud.research_verify({"research_id": rid}))
            assert "error" not in verify_result
            assert verify_result.get("verified", 0) >= 1

    def test_verify_empty_id(self, crud):
        """Leere research_id."""
        result = json.loads(crud.research_verify({"research_id": ""}))
        assert "error" in result


# ======================================================================
# research_auto — Tests
# ======================================================================

class TestResearchAuto:
    """Tests für research_auto (line 625)."""

    def test_auto_missing_query(self, crud):
        """Fehler wenn query fehlt."""
        result = json.loads(crud.research_auto({}))
        assert "error" in result
        assert "erforderlich" in result.get("error", "")

    def test_auto_success(self, crud):
        """Erfolgreicher Start einer autonomen Recherche."""
        result = json.loads(crud.research_auto({
            "query": "Autonome Recherche Test", "depth": 2, "max_sources": 3,
        }))
        assert "error" not in result
        assert "research_id" in result
        assert result.get("auto_mode") is True

    def test_auto_start_error_handling(self, crud, monkeypatch):
        """Fehler in research_start wird weitergegeben (line 625)."""
        monkeypatch.setattr(
            crud,
            "research_start",
            lambda args: json.dumps({"status": "error", "error": "Simulierter Fehler"})
        )
        result = json.loads(crud.research_auto({"query": "FehlerTest"}))
        assert "error" in result


# ======================================================================
# _enforce_max_results — Tests
# ======================================================================

class TestEnforceMaxResults:
    """Deckt lines 114, 117-121 ab."""

    def test_results_dir_not_exists(self, crud, tmp_path, monkeypatch):
        """RESULTS_DIR existiert nicht — return (line 114)."""
        monkeypatch.setattr(crud, "RESULTS_DIR", tmp_path / "nonexistent")
        crud._enforce_max_results()

    def test_max_results_cleanup(self, crud, rdir):
        """Löscht älteste Results wenn > MAX_RESULTS (lines 117-121)."""
        for i in range(101):
            (rdir / f"res{i:03d}.json").write_text(
                json.dumps({"id": f"res{i:03d}", "query": f"Result {i}"})
            )
        crud.MAX_RESULTS = 100
        crud._enforce_max_results()
        remaining = list(rdir.glob("*.json"))
        assert len(remaining) <= 100

    def test_max_results_with_unlink_error(self, crud, rdir, monkeypatch):
        """OSError beim unlink wird gecatcht (lines 119-121)."""
        for i in range(102):
            (rdir / f"res_unlink{i:03d}.json").write_text(
                json.dumps({"id": f"res{i:03d}", "query": f"Result {i}"})
            )
        crud.MAX_RESULTS = 100
        original_unlink = Path.unlink

        def _fail_unlink(self):
            if "res_unlink000" in str(self):
                raise OSError("Permission denied")
            return original_unlink(self)

        monkeypatch.setattr(Path, "unlink", _fail_unlink)
        crud._enforce_max_results()

    def test_enforce_max_results_cleanup_loop(self, crud, rdir):
        """Mehrere Runden Cleanup (loop >1)."""
        for i in range(105):
            (rdir / f"loop_res{i:03d}.json").write_text(
                json.dumps({"id": f"loop{i:03d}", "query": f"Loop Result {i}"})
            )
        crud.MAX_RESULTS = 100
        crud._enforce_max_results()
        remaining = list(rdir.glob("*.json"))
        assert len(remaining) <= 100


# ======================================================================
# research_update Struktur — Details
# ======================================================================

class TestResearchUpdateStructure:

    def _setup_result(self, crud, rdir):
        rid, _ = _start_ok(crud, "Struct Test")
        crud.research_save({
            "research_id": rid, "summary": "Struct", "findings": [], "sources": [],
        })
        return rid

    def test_append_findings_dict_structure(self, crud, rdir):
        """append_findings Dict wird korrekt strukturiert (lines 464-468)."""
        rid = self._setup_result(crud, rdir)
        result = json.loads(crud.research_update({
            "research_id": rid, "summary": "Updated",
            "append_findings": [
                {"finding": "Test Finding", "sources": ["https://src.com"]}
            ],
        }))
        assert "error" not in result

    def test_append_sources_dict_structure(self, crud, rdir):
        """append_sources Dict wird korrekt strukturiert (lines 483-488)."""
        rid = self._setup_result(crud, rdir)
        result = json.loads(crud.research_update({
            "research_id": rid, "summary": "Updated",
            "append_sources": [
                {"url": "https://src.com", "title": "Source", "relevance": 0.9}
            ],
        }))
        assert "error" not in result

    def test_append_findings_not_list_after_decode(self, crud, rdir):
        """append_findings nach JSON-Decode kein list — ignoriert."""
        rid = self._setup_result(crud, rdir)
        result = json.loads(crud.research_update({
            "research_id": rid, "summary": "Updated Summary",
            "append_findings": json.dumps({"not": "a list"}),
        }))
        assert "error" not in result

    def test_append_sources_not_list_after_decode(self, crud, rdir):
        """append_sources nach JSON-Decode kein list — ignoriert."""
        rid = self._setup_result(crud, rdir)
        result = json.loads(crud.research_update({
            "research_id": rid, "summary": "Updated",
            "append_sources": json.dumps({"not": "a list"}),
        }))
        assert "error" not in result

    def test_append_findings_dict_no_sources_key(self, crud, rdir):
        """append_findings ohne 'sources' Schlüssel."""
        rid = self._setup_result(crud, rdir)
        result = json.loads(crud.research_update({
            "research_id": rid, "summary": "Updated",
            "append_findings": [{"finding": "No Sources"}],
        }))
        assert "error" not in result

    def test_append_sources_dict_partial(self, crud, rdir):
        """append_sources mit minimalen Feldern."""
        rid = self._setup_result(crud, rdir)
        result = json.loads(crud.research_update({
            "research_id": rid, "summary": "Updated",
            "append_sources": [{"url": "https://partial.com"}],
        }))
        assert "error" not in result
