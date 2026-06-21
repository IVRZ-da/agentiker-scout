# Scout Plugin — CHANGELOG

## [0.2.0] — 2026-06-22

### Massive Framework-Erkennung — 30 → 732 Technologien

#### YAML-Rule-Engine (P1)
- **Neues YAML-Rule-System:** `shared/yaml_rule_loader.py` + `data/rules/*.yaml`
- Dynamischer Loader: `data/rules/` rekursiv scannen, validieren, cachen
- 38 manuelle YAML-Rules (alle 36 Python-Detectors migriert + 2 neue)
- YamlRuleLoader als Singleton + Detector-Cache für Performance
- 41 neue Tests

#### specfy/stack-analyser Konverter (P2) — +689 Technologien
- `scripts/convert_specfy_rules.py` — parst 700+ TypeScript-Rules automatisch
- 9 Kategorien: backend (188), database (87), frontend (62), infra (273),
  language (32), testing (10), ui_library (32), ci (34), package_manager (14)
- Deduplizierung: 26 Überschneidungen zu bestehenden Rules erkannt
- 17 Regeln ohne brauchbare Marker korrekt übersprungen

#### Package-Manager Auto-Discovery (P3)
- **GenericDependencyDetector** — parst automatisch package.json, go.mod,
  requirements.txt, Cargo.toml
- 85 bekannte npm-Packages, 55 PyPI, 50 Go-Module, 45 Cargo-Crates
- 46 Prefix-Matcher für @scoped/ Pakete
- Unbekannte Dependencies → `category: other` mit low confidence
- 28 neue Tests

#### dotenv + Docker Scanning (P4)
- **dotenv-Detection:** `.env.example`/`.env` KEY_PREFIX erkennen
  (SENTRY_, STRIPE_, OTEL_, GOOGLE_, AWS_, DATABASE_, REDIS_, etc.)
- **Docker-Detection:** docker-compose.yml Services + Dockerfile FROM
- 42 neue Tests + Integration in detect()

#### Performance: 29x schneller (P5)
- **_FileIndex** — einmal os.walk() statt 1500× rglob()
- **Glob-Cache** — Regex-Kompilierung einmalig pro Pattern
- **YAML-Detector-Cache** — type()-Aufrufe einmalig
- detect(): 2.9s → 0.049s | detect_fast(): 2.5s → 0.191s
- 17 Performance-Tests
- **Version:** 0.1.4 → 0.2.0 (Feature-Release)

## [0.1.4] — 2026-06-22

### Framework Skill + Pattern-Discovery Integration
- **Neuer Companion Skill:** `skills/framework-detection.md` mit vollständiger Doku
- **analysis_pattern_discover framework-bewusst:** `frameworks`-Parameter + Auto-Detection
- **Framework-gefilterte Pattern-Suche** via `get_patterns_for_frameworks()`
- **Ruff-Lint bereinigt:** 29 pre-existing Fehler (F401, F811, E402, E741) in 12 Dateien
- **Version:** 0.1.3 → 0.1.4

## [0.1.3] — 2026-06-22

### Framework Auto-Detection + Framework-spezifische Patterns
- **Neue Datei:** `shared/framework_detector.py` — Framework Detection Engine
  - Erkennt 30+ Technologien: Medusa-v2, Next.js, React, Vue, Svelte, Go Chi/Fiber, FastAPI/Django, PostgreSQL/Redis, Docker/systemd/nginx, GitHub/Forgejo Actions, npm/yarn/pnpm
  - Evidence-Tracking pro Framework mit Confidence-Scoring
  - zwei Modi: `detect()` (voll) + `detect_fast()` (nur High-Confidence-Marker)
  - `FrameworkDetector` Klasse + `detect_frameworks()` Convenience-API
  - Inspiriert von specfy/stack-analyser (+700 Technologien)
- **Neue Felder in BugPattern:** `frameworks: List[str]` + `frameworks_required: bool`
  - Alle 43 Patterns automatisch annotiert (Kategorie-basiert)
  - 23 generische Patterns (["*"]), 20 frameworks-spezifisch
- **Framework-basierte Pattern-Filterung:** `bug_hunt_scan()` erkennt automatisch den Tech-Stack und filtert Patterns
  - Parameter `frameworks=[]` für manuelle Überschreibung
  - Framework-Kontext in Scan-Ergebnissen
- **Framework-Presets:** 8 vordefinierte Presets
  - `medusa-full` (31), `medusa-admin` (5), `medusa-backend` (26), `nextjs-storefront` (26)
  - `go-backend` (28), `python-backend` (23), `typescript-generic` (26), `all` (43)
  - `resolve_preset()` + `list_presets()` API
- **Neues Tool:** `analysis_framework(path, fast)` — zeigt Framework-Profil
- **Intent-Erkennung:** Neue Domain `framework` in shared/intent.py
  - Priority: bug > research > framework > db > web > code
- **38 Unit-Tests** für Framework Detection Engine (0 failed, 0.16s)
- **Version:** 0.1.2 → 0.1.3

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
