# Scout Plugin — CHANGELOG

## [0.1.2] — 2026-06-22

### Repo-Setup
- **Repository eingerichtet:** `git.agentiker.de:johannes/agentiker-scout-plugin.git`
- **BRANCHING.md** erstellt (Branch-Konventionen nach Plugin-Standard)
- **LICENSE** (MIT) hinzugefügt
- **CONTRIBUTING.md** erstellt (Entwicklungsrichtlinien)
- **pyproject.toml** erstellt (build-system, ruff-Konfiguration, pytest)
- **scripts/generate_readme.py** — auto-generiert README.md aus plugin.yaml + Tool-Registry + CHANGELOG
- **Pre-commit Hook aktualisiert:** MODULE_TEST_MAP auf aktuelle Scout-Module (15 Einträge), VERSION-Check erweitert
- **README.md** automatisch generiert (Tool-Übersicht mit 43 Tools)
- **Version harmonisiert:** plugin.yaml 0.1.2, VERSION 0.1.2, pyproject.toml 0.1.2, CHANGELOG 0.1.2
- **Altes Repo ersetzt:** von `hermes-bot/scout` nach `johannes/agentiker-scout-plugin` migriert

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

## [0.1.1] — 2026-06-22

### Bug-Fixes (Bug-Hunt Welle 1)
- **P0 — Tool-Registrierung implementiert:** `register()` registriert jetzt alle 43 Tools
- **P0 — Registry-Shim:** `tools.registry` fehlte komplett — 19 Dispatch-Stellen crashten
- **P1 — _fmt.py Duplikate entfernt:** bughunt/_fmt.py, research/_fmt.py gelöscht (verwaist)
- **P1 — CUSTOM_001 E2E Test-Artifakt entfernt** aus custom_patterns.json
- **P1 — Silent Catch gefixt:** `except Exception: pass` → `logger.debug()`
- **P1 — Stubs implementiert:** `_build_tool_maps()` entfernt, `_ensure_dirs()` in register()
- **P2 — logging.raiseExceptions = False** Guard hinzugefügt
- **P2 — Git-Repo + pre-commit hook** eingerichtet
- **P2 — conftest-Isolation gefixt:** research/conftest überschrieb scout Paket

### Tests
- 814 passed, 45 skipped, 0 failed (vorher 7 failed)
- test_fmt.py Duplikate gelöscht (bughunt, research — testen shared scout/_fmt.py)

## [0.1.0] — 2026-06-21

**Initial release** — Fusion von analysis, bughunt und deep-research in ein Plugin.

### Features
- **3 Domains in einem Plugin:** Code-Analyse (12 Tools), Bug-Hunt (13 Tools), Web-Recherche (17 Tools)
- **Shared Pattern Pipeline:** Einheitliches Pattern-Repository statt 2 getrennten Systemen
- **Single Hook:** 1× pre_llm_call statt 3× (Intention-Deduplizierung)
- **Shared `_fmt.py`:** Ein Formatierungs-Modul statt 3 Duplikaten
- **Research-Patterns:** 4 wiederverwendbare Recherche-Vorlagen (EU-CBD, Competitor, Tech, News)
- **TTL-Cache:** Ein Cache-Layer für alle 3 Domains

### Migration
- analysis, bughunt, deep-research als eigenständige Plugins bleiben erhalten (deaktiviert)
- Alle Daten (Sessions, Patterns) bleiben erhalten
- Kein Datenverlust, kein Breaking Change für Agent-Workflows
