# Scout Plugin — CHANGELOG

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
