"""
Tool-Handler Tests für das scout.research Plugin.

Testet die 4 Tools mit Mocks für das Dateisystem.
Alle Tests nutzen tmp_path um die Plugin-Datenverzeichnisse zu simulieren.
"""

import json
import sys
import pytest

# ---------------------------------------------------------------------------
from conftest import make_research_tools


@pytest.fixture
def research_tools(tmp_path):
    """
    Importiert research_tools.py mit temporärem Plugin-Verzeichnis.
    """
    return make_research_tools(tmp_path)


# ---------------------------------------------------------------------------
# research_start Tests
# ---------------------------------------------------------------------------


class TestResearchStart:
    def test_start_valid_query(self, research_tools):
        """Start mit gültiger Query."""
        result = json.loads(research_tools.research_start({
            "query": "Climate Change Policy 2026",
            "depth": 3,
            "max_sources": 10,
        }))

        assert result["status"] == "planned"
        assert "research_id" in result
        assert len(result["research_id"]) == 8
        assert result["query"] == "Climate Change Policy 2026"
        assert result["depth"] == 3
        assert result["max_sources"] == 10
        assert "instruction" in result
        assert "research_save" in result["instruction"]

        # Prüfe dass Plan-Datei existiert
        plan_path = research_tools.PLANS_DIR / f"{result['research_id']}.json"
        assert plan_path.exists()

    def test_start_minimal_query(self, research_tools):
        """Start mit minimaler Query (nur query, default depth/sources)."""
        result = json.loads(research_tools.research_start({
            "query": "Climate Change",
        }))

        assert result["status"] == "planned"
        assert result["query"] == "Climate Change"
        assert result["depth"] == 3  # Default
        assert result["max_sources"] == 10  # Default

    def test_start_empty_query(self, research_tools):
        """Start mit leerer Query muss Fehler zurückgeben."""
        result = json.loads(research_tools.research_start({
            "query": "   ",
        }))

        assert result["status"] == "error"
        assert "error" in result

    def test_start_missing_query(self, research_tools):
        """Start ohne Query muss Fehler zurückgeben."""
        result = json.loads(research_tools.research_start({}))

        assert result["status"] == "error"
        assert "error" in result

    def test_start_depth_clamping(self, research_tools):
        """Depth muss auf 1-5 begrenzt werden."""
        result_too_low = json.loads(research_tools.research_start({
            "query": "Test Query", "depth": 0,
        }))
        assert result_too_low["depth"] == 1

        result_too_high = json.loads(research_tools.research_start({
            "query": "Test Query", "depth": 10,
        }))
        assert result_too_high["depth"] == 5

    def test_start_max_sources_clamping(self, research_tools):
        """max_sources muss auf 1-50 begrenzt werden."""
        result_low = json.loads(research_tools.research_start({
            "query": "Test Query", "max_sources": -1,
        }))
        assert result_low["max_sources"] == 1

        result_high = json.loads(research_tools.research_start({
            "query": "Test Query", "max_sources": 1000,
        }))
        assert result_high["max_sources"] == 50

    def test_start_long_query(self, research_tools):
        """Sehr lange Query muss abgelehnt werden."""
        long_query = "x" * 2001
        result = json.loads(research_tools.research_start({
            "query": long_query,
        }))

        assert result["status"] == "error"

    def test_start_unicode_query(self, research_tools):
        """Query mit Unicode/Sonderzeichen muss funktionieren."""
        result = json.loads(research_tools.research_start({
            "query": "Green Tech 💚 und Climate Solutions — (2026)",
        }))

        assert result["status"] == "planned"
        assert result["query"] == "Green Tech 💚 und Climate Solutions — (2026)"


# ---------------------------------------------------------------------------
# research_save Tests
# ---------------------------------------------------------------------------


class TestResearchSave:
    def test_save_completed(self, research_tools):
        """Save mit allen Feldern (completed)."""
        # Vorbereitung: research_start aufrufen
        start = json.loads(research_tools.research_start({
            "query": "Renewable Energy",
            "depth": 2,
        }))
        rid = start["research_id"]

        # Save
        result = json.loads(research_tools.research_save({
            "research_id": rid,
            "summary": "Die Energiewende in Deutschland schreitet voran. Neues Gesetz ab 2027.",
            "findings": json.dumps([
                {"finding": "Gesetzentwurf liegt vor", "sources": ["https://example.com/1"]},
                {"finding": "Branche erwartet Wachstum", "sources": ["https://example.com/2"]},
            ]),
            "sources": json.dumps([
                {"url": "https://example.com/1", "title": "News Artikel 1", "relevance": 0.9},
                {"url": "https://example.com/2", "title": "Analyse", "relevance": 0.8},
            ]),
            "status": "completed",
        }))

        assert result["status"] == "completed"
        assert result["query"] == "Renewable Energy"
        assert result["findings_count"] == 2
        assert result["sources_count"] == 2
        assert "honcho_conclude" in result["instruction"]

        # Prüfe dass Ergebnis-JSON existiert
        result_path = research_tools.RESULTS_DIR / f"{rid}.json"
        assert result_path.exists()

        # Plan muss gelöscht sein
        plan_path = research_tools.PLANS_DIR / f"{rid}.json"
        assert not plan_path.exists()

    def test_save_partial(self, research_tools):
        """Save mit partial status."""
        start = json.loads(research_tools.research_start({"query": "Test Query"}))
        rid = start["research_id"]

        result = json.loads(research_tools.research_save({
            "research_id": rid,
            "summary": "Teilergebnisse verfügbar.",
            "status": "partial",
        }))

        assert result["status"] == "partial"

    def test_save_missing_id(self, research_tools):
        """Save ohne research_id."""
        result = json.loads(research_tools.research_save({
            "summary": "Test",
            "status": "completed",
        }))

        assert result["status"] == "error"

    def test_save_invalid_id(self, research_tools):
        """Save mit nicht-existierender ID."""
        result = json.loads(research_tools.research_save({
            "research_id": "nonexistent",
            "summary": "...",
            "status": "completed",
        }))

        assert result["status"] == "error"

    def test_save_empty_summary(self, research_tools):
        """Save ohne Summary."""
        start = json.loads(research_tools.research_start({"query": "Test Query"}))
        result = json.loads(research_tools.research_save({
            "research_id": start["research_id"],
            "summary": "",
            "status": "completed",
        }))

        assert result["status"] == "error"

    def test_save_invalid_status(self, research_tools):
        """Save mit ungültigem Status."""
        start = json.loads(research_tools.research_start({"query": "Test Query"}))
        result = json.loads(research_tools.research_save({
            "research_id": start["research_id"],
            "summary": "Test",
            "status": "invalid_status",
        }))

        assert result["status"] == "error"

    def test_save_malformed_findings(self, research_tools):
        """Save mit kaputtem findings-JSON."""
        start = json.loads(research_tools.research_start({"query": "Test Query"}))
        result = json.loads(research_tools.research_save({
            "research_id": start["research_id"],
            "summary": "Test",
            "findings": "kein JSON{{{",
            "status": "completed",
        }))

        assert result["findings_count"] >= 0  # Darf nicht crashen
        # findings_raw ist kein gültiges JSON → wird als einzelnes Finding behandelt

    def test_save_without_start(self, research_tools):
        """Save ohne vorheriges research_start (nur von Hand research_id)."""
        # Direkt eine Ergebnis-Datei erzeugen ist auch OK?
        # research_save sucht nach Plan-Datei, nicht Ergebnis-Datei
        # Wenn beide nicht existieren → error
        result = json.loads(research_tools.research_save({
            "research_id": "handmade",
            "summary": "Manuell erstellte Zusammenfassung",
            "status": "completed",
        }))

        assert result["status"] == "error"  # Keine Plan-Datei gefunden

    def test_save_preserves_query_from_start(self, research_tools):
        """Die Query aus research_start muss in save erhalten bleiben."""
        start = json.loads(research_tools.research_start({
            "query": "Spezifische Query für Test",
            "depth": 3,
        }))
        rid = start["research_id"]

        # Plan-Datei direkt manipulieren um Query zu setzen (passiert in research_start bereits)
        result = json.loads(research_tools.research_save({
            "research_id": rid,
            "summary": "Zusammenfassung",
            "status": "completed",
        }))

        assert result["query"] == "Spezifische Query für Test"
        assert result["depth"] == 3

    def test_save_twice_rejected(self, research_tools):
        """Doppelter research_save mit gleicher ID muss Fehler geben."""
        start = json.loads(research_tools.research_start({
            "query": "Double Save Test",
        }))
        rid = start["research_id"]

        # Erster Save — muss funktionieren
        first = json.loads(research_tools.research_save({
            "research_id": rid,
            "summary": "Erster Save",
            "status": "completed",
        }))
        assert first["status"] == "completed"

        # Zweiter Save — muss Fehler geben (bereits gespeichert)
        second = json.loads(research_tools.research_save({
            "research_id": rid,
            "summary": "Zweiter Save sollte nicht klappen",
            "status": "completed",
        }))
        assert second["status"] == "error"
        assert "bereits" in second["error"].lower()


# ---------------------------------------------------------------------------
# research_search Tests
# ---------------------------------------------------------------------------


class TestResearchSearch:
    def test_search_empty(self, research_tools):
        """Suche wenn keine Ergebnisse gespeichert sind."""
        result = json.loads(research_tools.research_search({"query": "Green Tech"}))

        assert "results" in result
        assert isinstance(result["results"], list)
        assert "honcho_search" in result.get("instruction", "")

    def test_search_existing(self, research_tools):
        """Suche in vorhandenen Ergebnissen."""
        # Ergebnis-Datei anlegen
        rid = "test1234"
        result_data = {
            "id": rid,
            "query": "Climate Change Policy",
            "summary": "Die Auswirkungen des Klimawandels in Deutschland...",
            "findings": [{"finding": "Finding 1", "sources": []}],
            "sources": [{"url": "https://example.com", "title": "Quelle"}],
            "status": "completed",
            "saved_at": "2026-06-18T12:00:00",
        }
        (research_tools.RESULTS_DIR / f"{rid}.json").write_text(
            json.dumps(result_data)
        )

        # Suche nach Climate
        result = json.loads(research_tools.research_search({"query": "Climate Change"}))

        assert result["total"] >= 1
        assert any(r["query"] == "Climate Change Policy" for r in result["results"])

    def test_search_nonexistent_query(self, research_tools):
        """Suche nach nicht-existentem Begriff."""
        rid = "test5678"
        (research_tools.RESULTS_DIR / f"{rid}.json").write_text(
            json.dumps({"id": rid, "query": "Climate Change", "summary": "..."})
        )

        result = json.loads(research_tools.research_search({"query": "Steuergesetze"}))

        # Sollte nichts finden
        assert result["total"] == 0

    def test_search_multiple_results(self, research_tools):
        """Suche mit mehreren gespeicherten Ergebnissen."""
        for i, q in enumerate(["Renewable Energy", "Renewable Energy in Healthcare", "Solar Energy"]):
            (research_tools.RESULTS_DIR / f"res{i}.json").write_text(
                json.dumps({"id": f"res{i}", "query": q, "summary": f"Über {q}", "status": "completed"})
            )

        result = json.loads(research_tools.research_search({"query": "Energy"}))

        assert result["total"] >= 1

    def test_search_all(self, research_tools):
        """Suche ohne Query gibt alle Ergebnisse."""
        for i in range(5):
            (research_tools.RESULTS_DIR / f"res{i}.json").write_text(
                json.dumps({"id": f"res{i}", "query": f"Query {i}", "status": "completed"})
            )

        result = json.loads(research_tools.research_search({"query": ""}))

        assert result["total"] >= 5
        assert len(result["results"]) >= 5
        assert "honcho_search" in result.get("instruction", "")

    def test_search_limit(self, research_tools):
        """Limit muss funktionieren."""
        for i in range(10):
            (research_tools.RESULTS_DIR / f"res{i}.json").write_text(
                json.dumps({"id": f"res{i}", "query": f"Query {i}", "status": "completed"})
            )

        result = json.loads(research_tools.research_search({"query": "Query", "limit": 3}))

        assert len(result["results"]) <= 3


# ---------------------------------------------------------------------------
# research_status Tests
# ---------------------------------------------------------------------------


class TestResearchStatus:
    def test_status_planned(self, research_tools):
        """Status einer geplanten (nicht gespeicherten) Recherche."""
        start = json.loads(research_tools.research_start({"query": "Test Query"}))
        rid = start["research_id"]

        result = json.loads(research_tools.research_status({"research_id": rid}))

        assert result["research_id"] == rid
        assert result["status"] == "planned"
        assert result["query"] == "Test Query"

    def test_status_completed(self, research_tools):
        """Status einer abgeschlossenen Recherche."""
        start = json.loads(research_tools.research_start({"query": "Renewable Energy"}))
        rid = start["research_id"]

        research_tools.research_save({
            "research_id": rid,
            "summary": "Abgeschlossen.",
            "status": "completed",
        })

        result = json.loads(research_tools.research_status({"research_id": rid}))

        assert result["status"] == "completed"
        assert "honcho_search" in result.get("message", "")

    def test_status_not_found(self, research_tools):
        """Status einer nicht-existenten Recherche."""
        result = json.loads(research_tools.research_status({"research_id": "nonexistent"}))

        assert result["status"] == "not_found"

    def test_status_empty_id(self, research_tools):
        """Status ohne research_id."""
        result = json.loads(research_tools.research_status({"research_id": ""}))

        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Integration: Start → Firecrawl → Save → Search
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_full_workflow(self, research_tools):
        """Kompletten Workflow testen: Start → Save → Search → Status."""
        # 1. Start
        start = json.loads(research_tools.research_start({
            "query": "Climate Change Policy Europe 2026",
            "depth": 3,
        }))
        rid = start["research_id"]
        assert start["status"] == "planned"

        # 2. Save
        save = json.loads(research_tools.research_save({
            "research_id": rid,
            "summary": "Die EU hat neue Klimaschutzmaßnahmen vorangetrieben. "
                       "Neue Regulierung ab Q3 2026 erwartet.",
            "findings": json.dumps([
                {"finding": "Emissionsreduktion in Vorbereitung", "sources": ["url1"]},
                {"finding": "Marktwachstum von 15% erwartet", "sources": ["url2"]},
                {"finding": "Grenzüberschreitender Handel wird vereinfacht", "sources": ["url3"]},
            ]),
            "sources": json.dumps([
                {"url": "https://example.com/eu-climate", "title": "EU Klimagesetz"},
                {"url": "https://example.com/market", "title": "Marktanalyse 2026"},
                {"url": "https://example.com/trade", "title": "EU Handelsregulierung"},
            ]),
            "status": "completed",
        }))
        assert save["status"] == "completed"
        assert save["findings_count"] == 3
        assert save["sources_count"] == 3
        assert "honcho_conclude" in save["instruction"]

        # 3. Search
        search = json.loads(research_tools.research_search({"query": "Climate Policy"}))
        assert search["total"] >= 1
        assert any("Climate" in r["query"] for r in search["results"])

        # 4. Status
        status = json.loads(research_tools.research_status({"research_id": rid}))
        assert status["status"] == "completed"
        assert status["sources_count"] == 3
        assert status["findings_count"] == 3

    def test_multiple_independent_researches(self, research_tools):
        """Mehrere unabhängige Recherchen hintereinander."""
        queries = [
            "Climate Change Policy",
            "Green Technology Research",
            "Solar Energy EU",
        ]

        for q in queries:
            start = json.loads(research_tools.research_start({"query": q}))
            save = json.loads(research_tools.research_save({
                "research_id": start["research_id"],
                "summary": f"Ergebnisse zu {q}",
                "status": "completed",
            }))
            assert save["status"] == "completed"

        # Alle sollten durchsuchbar sein
        search = json.loads(research_tools.research_search({"query": "Climate Change"}))
        climate_results = [r for r in search["results"] if "Climate" in r["query"]]
        assert len(climate_results) >= 1

        search2 = json.loads(research_tools.research_search({"query": "Solar"}))
        solar_results = [r for r in search2["results"] if "Solar" in r["query"]]
        assert len(solar_results) >= 1


# ---------------------------------------------------------------------------
# Edge Cases & Error Handling
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_special_characters_in_query(self, research_tools):
        """Sonderzeichen in Query."""
        queries = [
            "CO2 & NOx: Unterschiede?",
            "Climate Data Analysis Methods",
            "Preise 2025/2026 | Marktbericht",
            "Einführung von §31a BtMG",
            "Solar, Wind & Co. - Ein Überblick!",
        ]
        for q in queries:
            result = json.loads(research_tools.research_start({"query": q}))
            assert result["status"] == "planned", f"Query '{q}' fehlgeschlagen"

    def test_empty_findings_save(self, research_tools):
        """Save mit leeren findings (keine Findings)."""
        start = json.loads(research_tools.research_start({"query": "Test Query"}))
        result = json.loads(research_tools.research_save({
            "research_id": start["research_id"],
            "summary": "Keine Findings",
            "findings": "[]",
            "status": "completed",
        }))
        assert result["findings_count"] == 0

    def test_missing_data_dirs(self, tmp_path):
        """Falls data/-Verzeichnisse fehlen, darf kein Crash passieren."""
        import importlib.util
        from pathlib import Path

        # tools/base.py in Isolation laden (checkt Datenverzeichnisse)
        _research_dir = Path(__file__).resolve().parent.parent.parent / "research"
        base_path = _research_dir / "tools" / "base.py"
        mod_name = f"tools.base.{tmp_path.name}"

        spec = importlib.util.spec_from_file_location(mod_name, base_path)
        mod = importlib.util.module_from_spec(spec)
        mod.PLUGIN_DIR = tmp_path
        # KEINE data/-Verzeichnisse anlegen!
        mod.DATA_DIR = tmp_path / "data"
        mod.PLANS_DIR = tmp_path / "data" / "plans"
        mod.RESULTS_DIR = tmp_path / "data" / "results"
        mod.__package__ = "scout.research.tools"

        sys.modules[mod_name] = mod
        sys.modules["scout.research.tools.base"] = mod
        spec.loader.exec_module(mod)

        # research_search auf leerem Verzeichnis — benutzt base
        # Lade search.py mit gepatchter base
        search_path = _research_dir / "tools" / "search.py"
        s_spec = importlib.util.spec_from_file_location(
            f"tools.search.{tmp_path.name}", search_path)
        s_mod = importlib.util.module_from_spec(s_spec)
        s_mod.__package__ = "scout.research.tools"
        sys.modules[f"tools.search.{tmp_path.name}"] = s_mod
        s_spec.loader.exec_module(s_mod)

        result = json.loads(s_mod.research_search({"query": "irgendwas"}))
        assert "results" in result
