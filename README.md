# Scout Plugin — Hermes Agent

Unified analysis, bug-hunt, and web-research plugin with shared pattern pipeline. 42 tools across 3 domains.

- **Version:** 0.1.2
- **Author:** agentiker
- **License:** MIT
- **Total Tools:** 43

---

## Tool-Übersicht

### Analysis — Code & Architecture Analysis (13 Tools)

| Tool | Description |
|------|-------------|
| `analysis_inspect` |  |
| `analysis_report` |  |
| `analysis_architecture` |  |
| `analysis_deadcode` |  |
| `analysis_performance` |  |
| `analysis_security` |  |
| `analysis_ask` |  |
| `analysis_diff` |  |
| `analysis_trend` |  |
| `analysis_watch` |  |
| `analysis_graph` |  |
| `analysis_ui_gap` |  |
| `analysis_pattern_discover` |  |

### Bug-Hunt — Automated Bug Pattern Scanning (13 Tools)

| Tool | Description |
|------|-------------|
| `bug_hunt_start` | Start a new bug-hunt session. |
| `bug_hunt_finding` | Add a finding to a session. |
| `bug_hunt_list` | List findings for a session, filterable. |
| `bug_hunt_close` | Close a bug-hunt session. |
| `bug_hunt_scan` | Run automated scans using pattern library. |
| `bug_hunt_triage` | Update severity/status for findings. |
| `bug_hunt_verify` | Verify if a finding's bug still exists. |
| `bug_hunt_fix` | Generate an auto-fix prompt for a bug finding. |
| `bug_hunt_report` | Generate a structured bug-hunt report. |
| `bug_hunt_export` | Export findings as JSON or Markdown. |
| `bug_hunt_history` | Search past bug-hunt sessions. |
| `bug_hunt_pattern` | List, inspect, search, save, or manage bug patterns. |
| `bug_hunt_stats` | Statistics about findings in a session. |

### Research — Web Research & Synthesis (17 Tools)

| Tool | Description |
|------|-------------|
| `research_start` | Startet eine neue Recherche. Validiert die Query, erzeugt eine research_id und l… |
| `research_save` | Speichert die Ergebnisse einer Recherche. |
| `research_delete` | Löscht eine Recherche inklusive Plan- und Ergebnis-Dateien. |
| `research_cleanup` | Bereinigt alte oder verwaiste Research-Daten. |
| `research_tag` | Verwaltet Tags für eine Recherche (add/remove/set/clear). |
| `research_update` | Aktualisiert eine bestehende Recherche (erweitern/korrigieren). |
| `research_verify` | Prüft Quellen-URLs auf Erreichbarkeit und validiert Findings. |
| `research_auto` | Startet eine vollautonome Recherche. Rüstet einen Sub-Agenten aus der selbststän… |
| `research_search` | Durchsucht gespeicherte Research-Ergebnisse mit BM25-Volltextsuche. Unterstützt … |
| `research_status` | Zeigt Status und Details einer Recherche an. |
| `research_stats` | Zeigt Metriken und Statistiken über alle Recherchen. |
| `research_export` | Exportiert Research-Ergebnisse als Markdown oder Text. |
| `research_compare` | Vergleicht 2-3 Research-IDs. |
| `research_synthesize` | Synthetisiert passende Research-Ergebnisse via Honcho. |
| `research_merge` | Fasst mehrere Recherchen zu einer zusammen (dedupliziert). |
| `research_export_all` | Exportiert ALLE gespeicherten Recherchen als Bundle. |
| `research_schedule` | Plant periodische Recherchen via Hermes cronjob. |

---

## Latest Changes

## [0.1.2] — 2026-06-22

### Tests — E2E-Konvertierung
- **E2E-Tests in Unit-Tests konvertiert:** Alle 81 E2E-Tests (gated via E2E_TEST=1) wurden analysiert:
  - 44 Research-Tests: **gelöscht** (100% durch existierende Unit-Tests abgedeckt)
  - 14 Bughunt-Tests: **gelöscht** (100% redundant)
  - 15 Analysis-Tools-Tests: **migriert** nach `tests/test_analysis/test_e2e_converted.py` (tmp_path statt Plugin-Source)
  - 3 Pattern-Tests: **migriert** nach `tests/test_bughunt/test_shared_patterns.py`
  - 1 Edge-Case-Test: **migriert** nach `tests/test_bughunt/test_e2e_converted.py`
  - 2 Workflow-Tests: **migriert** als `pytest.mark.integration` in `tests/test_integration/`
- **`test_e2e/` Verzeichnis gelöscht** — kein E2E-TEST=1 Gate mehr
- **`pytest.ini`:** `integration` Marker registriert
- Resultat: 882 Tests, 0 von E2E_TEST abhängig

---

## Development

### Setup

```bash
# Pre-commit hook aktivieren
git config core.hooksPath .githooks

# Tests ausführen
python3 -m pytest tests/ -q --tb=short

# Ruff Lint
python3 -m ruff check . --select F,E,T,W,I
```

Siehe `CONTRIBUTING.md` und `BRANCHING.md` für Details.