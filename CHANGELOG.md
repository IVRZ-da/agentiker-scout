# Scout Plugin — CHANGELOG

## [0.5.2] — 2026-06-25
- **Pre-Commit-Hook:** `_check_readme_tools()` auf per-plugin `scripts/generate_readme.py` umgestellt (alter zentraler Pfad entfernt)

## [0.5.1] — 2026-06-25

### Changed — Bughunt-Core-Split + Complexity-Refactoring

**b1 — bughunt_core.py in core/ Subpackage gesplittet (796→64 Zeilen):**
- `bughunt/core/model.py`: Finding, BugHuntSession, Konstanten
- `bughunt/core/patterns.py`: Pattern-CRUD + init/getters
- `bughunt/core/persistence.py`: Session I/O + cleanup
- `bughunt/core/tracking.py`: BugHuntTracker + Reporting + validate_path
- `bughunt/bughunt_core.py`: Re-Export Facade (64 Zeilen)
- Test-Fixtures aktualisiert (namespace shims + DATA_DIR Isolation)

**b2 — bug_hunt_scan() refactored (Complexity 30→12, Rank C→B):**
- `_resolve_scan_patterns()`: Preset + Framework-Auflösung extrahiert
- `_pattern_matches_frameworks()`: Framework-Filter als eigene Funktion
- `_add_auto_findings()`: Finding-Erzeugung + Save extrahiert
- `_build_scan_result()`: Ergebnis-Dict-Bau extrahiert

## [0.5.0] — 2026-06-24

### Changed — Coverage-Offensive + Infrastruktur (P0-P7)

**P0 — Hotfix:**
- `test_plugin_yaml_valid`/`test_plugin_yaml_is_valid`: assertion `"scout"` → `"agentiker-scout"` gefixt
- `test_large_volume_performance`: Schwelle 500ms → 1000ms (stabilisiert mit --cov)
- Import-Tests für `bughunt/__init__.py`, `research/__init__.py`, `research_tools.py` (0% → getestet)

**P1 — Coverage shared/detectors/ (700+ Zeilen, 0%→100%):**
- 5 neue Test-Dateien (base, catalog, dependency_data, generic, loader)
- `detectors/`-Module: **0% → 81-100%** (base 93%, catalog 100%, dependency_data 100%, generic 84%, loader 81%, public 100%)
- `yaml_rule_loader.py`: **0% → 78%** (Bonuseffekt)
- `framework_query_move.py`: **13% → getestet** (3 Tests)

**P2 — Coverage pattern_loader + yaml_rule_loader + dependency_scanner:**
- `pattern_loader.py`: **23% → 99%**
- `yaml_rule_loader.py`: **78% → 100%**
- `dependency_scanner.py`: **21% → 98%**
- 21 neue Edge-Case-Tests (invalid entries, non-list languages, cache, etc.)

**P3 — Coverage graph_patterns + Legacy analysis_intent:**
- `graph_patterns.py`: **26% → 56%** (20 Tests: Mermaid, Pattern-Discovery)
- `shared/intent.py`: **28% → 57%** (Intent-Erkennung + on_pre_llm_call)
- `analysis_intent.py`: Legacy-Dokumentation präzisiert (Konsolidierungsplan)

**P4a — Coverage shared/honcho:**
- `honcho.py`: **16% → 67%** (19 Tests: Persistenz, Session-Tracking, Post-Tool-Call)
- `shared/intent.py`: **28% → 98%** (6 on_pre_llm_call Tests)

**P4b — Coverage shared/patterns + cache + registry:**
- `cache.py`: **50% → 100%**
- `registry.py`: **57% → 100%**
- `patterns_research.py`: **0% → 64%**
- `patterns.py`: **48% → 56%**
- 31 Tests in neuer `test_shared_infra.py`

**P5 — Coverage bughunt-hooks:**
- `bughunt_hooks.py`: **51% → 52%** (neue Tests für _is_bughunt_related, _map_security_severity)

**P6 — Pre-Commit Coverage-Gate:**
- `.coveragerc` erstellt mit `fail_under=69`
- Pre-Commit Check 13: `--cov --cov-fail-under=69` (nur bei vollem Test-Suite)
- Gesamt-Coverage von ~61% auf **~70%** gesteigert

**P7 — Complexity-Refactoring:**
- `analysis_risk_tool`: Complexity **29→~13** (6 Repeat-Blöcke → data-driven-Schleife)
- 151 Tests bestätigen: kein Verhaltensänderung

### Added — Bughunt code-intel Integration (original)

**Phase 1 — Neue Scan-Typen:**
- `code_security_scan`: 16 integrierte Vulnerability-Patterns via Registry Dispatch
- `code_search_by_error`: Orphaned Error-Handler Analyse
- `code_todo_finder`: TODO/FIXME/HACK Scanner
- Graceful Degradation: Fehlende Tools brechen den Scan nicht ab (🔴 F2)

**Phase 2 — Neue Bug Patterns (43→69, +26):**
- Security (S020-S026): 7 Patterns mit scan_type=code_security_scan
- Code-Quality (C020-C025): 6 Patterns (TODOs, Duplicates, Merge-Conflicts, Error Handler)
- Java (J001-J005): 5 Patterns (Log Forging, Null Pointer, SQL, Deserialization, Credentials)
- C/C++ (CPP001-CPP005): 5 Patterns (Buffer Overflow, Memory Leak, Use-After-Free, Integer Overflow, Format String)
- Ruby (RB001-RB003): 3 Patterns (Mass Assignment, Command Injection, SQL Injection)

**Phase 3 — Cross-Tool Integration:**
- Auto-Findings: analysis_security Ergebnisse → BugHunt-Findings (Dedup via TTL-Cache, 🔴 F3)
- Bug-Timeline: analysis_timeline + code_git_blame in bug_hunt_history
- Risk-Priorisierung: analysis_risk Risk-Score in bug_hunt_stats
- _call_tool Import in bughunt_tools (fallback-sicher)

**Phase 4 — Bug-Fix + Framework Patterns:**
- analysis_review Hinweis in bug_hunt_fix Prompt
- Framework-specific patterns (Java, C/C++, Ruby)

### Changed
- **Scan-Runner**: batch_grep_scans unterstützt jetzt 3 code_intel scan_types
- **bug_hunt_history**: Neuer `path`/`symbol` Parameter für Timeline
- **bug_hunt_stats**: Neuer `risk_score`/`risk_level` Output
- **bughunt_hooks**: Deduplizierungs-Cache für Auto-Findings (5min TTL)
- **Plugin-Version**: 0.4.0→0.5.0

### Tests
- 292+ Bughunt-Tests grün, 0 Failures
- 1383+ Gesamt-Tests grün
- 69 Built-in Patterns (vorher 43)

## [0.4.0] — 2026-06-23

### Added — 9 neue Analyse-Tools (16→25)

**Phase 1a — Composite-Tools (3):**
- `analysis_timeline` — Composite aus code_timeline + code_git_log_symbol + code_diff_analysis
- `analysis_duplicates` — Wrapper für code_duplicates (AST-basierte Duplikat-Erkennung)
- `analysis_dependency_risk` — Composite Risk Score (code_dependency_risk + complexity + hot_paths)

**Phase 1b+2 — Erweiterungen + Mittlere Komplexität (2):**
- `analysis_diff_analysis` — Git-Diff mit Impact-Analyse (code_diff_analysis + code_git_diff_file)
- `analysis_risk` — Multi-Faktor Risk Score (6 Kategorien: dependencies, complexity, deadcode, security, hotspots, duplicates)

**Phase 3+4 — Höhere Komplexität (4):**
- `analysis_review` — Automated Code Review (code_review_assistant + security_scan + diff_analysis)
- `analysis_graph_query` — Knowledge Graph Query (code_index + code_graph_query)
- `analysis_test_insight` — Testabdeckungs-Analyse (code_tests_for_symbol + generate_tests)
- `analysis_migration` — YAML-basierte Bulk Migration (code_migration)

### Changed
- **analysis_inspect depth=5**: 3 neue Layer (8=timeline, 9=duplicates, 10=dependency_risk)
- **analysis_deadcode**: Neue Parameter max_files/timeout
- **analysis_security**: code_security_scan Integration (parallel zu eigenen Patterns)
- **analysis_framework**: 3 neue LSP-Detectors (Java, C/C++, Ruby)
- **analysis_ask**: Output radikal gekürzt (kein Full-Data-Dump mehr)
- **Tool-Count**: 46→55 (analysis: 16→25, bughunt: 13, research: 17)
- **Version**: 0.3.4→0.4.0

### Tests
- 38 neue Tests für alle neuen Tools
- 1361+ Tests grün, 0 Failures
- Framework-Detector: YAML-Rule-Test für cpp/ruby als known_without_yaml markiert

## [0.3.4] — 2026-06-22

### Bug-Hunt Fixes (8 Findings)
- **P1 Fix: 3 fehlende Tools in Registry** — `analysis_framework`, `analysis_code_query`,
  `analysis_code_move` waren in `analysis_tools.py` implementiert aber nicht in
  `scout_tool_registry.json` registriert. Agent konnte sie nicht nutzen.
  Fix: Einträge ergänzt, `ANALYSIS_FRAMEWORK_SCHEMA` in `schemas.py` angelegt.
  Tool-Count: 43→46 (analysis: 13→16).
- **P1 Fix: Silent Catches (3 Stellen)** — `shared/honcho.py` (`_get_analysis_session`,
  `_get_bughunt_session`, `_get_research_session`) hatten `except Exception: pass` ohne
  Logging. Fix: `logger.debug()` nachgerüstet.
- **P2 Fix: `research/research_core.py` fehlte** — `shared/honcho.py:58` importierte
  `get_active_research()` aus nicht existenter Datei. Fix: Datei mit Tracker-basierter
  Implementierung angelegt.
- **P2 Fix: `analysis_intent.py` Legacy-Marker** — Als DEPRECATED markiert, auf
  `shared/intent.py` als Nachfolger verwiesen.
- **P2 Fix: Companion Skill Drift** — `skills/SKILL.md` von v0.1.0/42-Tools auf
  v0.3.3/46-Tools aktualisiert.
- 1316 Tests grün, 45 skipped, 0 Failures.

### Bug-Hunt Fixes (v0.3.4+ — 5 Findings nach Release)
- **P2 Fix: CHANGELOG-Reihenfolge** — v0.3.4-Eintrag war unsortiert zwischen v0.3.2,
  v0.3.3 fehlte als separater Eintrag. Reihenfolge korrigiert.
- **P2 Fix: Companion Skill Drift** — Skill zeigte 42 Tools/v0.3.3 statt 46 Tools/v0.3.4
- **P3 Fix: pytest.ini DeprecationWarnings** — `filterwarnings` ergänzt (590 Warnings)
- **P3 Fix: DEPRECATED-Markierung in analysis_intent.py** — Korrigiert auf "partiell abgelöst"
- **P3 Fix: Tool-Count dynamisch** — `__init__.py`-Docstring nutzt `len(registry)` statt 46
- 1316 Tests grün, 45 skipped, 0 Failures.

## [0.3.3] — 2026-06-22

### Refactoring
- **framework_detector.py Split** — 2003-Zeilen-Monolith in `shared/detectors/` Subpackage
  aufgeteilt (6 Module + `__init__.py` + Re-Export Facade für Rückwärtskompatibilität):
  `base.py` (Data Classes, _TechDetector, _FileIndex), `catalog.py` (37 Detector-Instanzen),
  `dependency_data.py` (Lookup-Tabellen), `loader.py` (FrameworkDetector-Klasse),
  `generic.py` (GenericDependencyDetector), `public.py` (Convenience-API).
  1316 Tests grün, 45 skipped, 0 Failures.

## [0.3.2] — 2026-06-22

### Bug-Hunt Fixes (9 Findings)
- **P0 Fix: `_parallel_dispatch` try/except** — `from tools.registry import registry` in
  `analysis/tools/base.py:247` ohne Absicherung. Fix via try/except ImportError mit
  logger.warning + return {}.
- **P1 Fix: Silent Catches (8 Stellen)** — `except Exception: pass` in Pattern-Discovery
  (`_discover_python_patterns`, `_discover_ts_patterns`, `_discover_go_patterns`) und
  `increment_match_count` in `analysis/tools/base.py` durch logger.debug() ersetzt.
- **P1 Fix: Version Tags** — Git-Tags v0.2.0, v0.3.0, v0.3.1 nachgetragen (plugin.yaml
  war v0.3.1 aber nur v0.1.1 getaggt).
- **P2 Fix: Domain __init__.py** — `analysis/__init__.py`, `bughunt/__init__.py`,
  `research/__init__.py`, `shared/__init__.py` mit sinnvollen Re-Exports und __all__
  versehen (vorher leer/nutzlos).
- **P3 Fix: Script Silent Catches** — `scripts/convert_specfy_rules.py` print()-Warnungen
  statt pass in 2 except-Blöcken.
- 1316 Tests grün, 45 skipped, 0 Failures.

## [0.3.1] — 2026-06-22

### Fix
- **shared Namespace-Shim** — `from shared.X` Imports in 6 Modulen crashten mit
  "No module named 'shared'". Fix via `_ensure_shared_namespace()` in __init__.py,
  analog zum bestehenden `scout`-Shim. 1316 Tests grün.

## [0.3.0] — 2026-06-22

### Bug-Pattern Katalog — von 45 auf ~830 Patterns

#### PatternLoader + YAML-Katalog (P0)
- **Neue `shared/pattern_loader.py`** — Bug-Pattern Loader analog zu yaml_rule_loader
- `data/patterns/` Verzeichnis-Struktur mit 6 Kategorien
- PatternLoader mit Singleton, Kategorie-/Sprach-/Severity-Filter, Duplikat-Erkennung
- Fehlertolerant: korrupte YAML unterbricht nicht
- 66 Tests

#### Semgrep Registry Konverter (P1) — +425 Patterns
- `scripts/convert_semgrep_rules.py` — konvertiert 425 Semgrep-Regeln
- 340 Security + 85 Code-Quality Patterns
- Nur einfache `pattern:`-Regeln (kein AST/taint)
- Sprachverteilung: Python (247), JS/TS (105), Go (60), Rust (10)
- 40 Tests

#### OWASP Secure Coding + CWE Taxonomie (P2) — +86 Patterns
- 86 OWASP Patterns in 7 Kategorien (Input Validation, Auth, Session, Access Control, Crypto, Error Handling, File Security)
- `data/cwe_categories.json` mit 80 CWE-Entrys
- Für alle Sprachen (generisch)
- 44 Tests

#### ESLint/TypeScript-ESLint (P3) — +39 Patterns
- Top-ESLint Regeln: TS (10), Security (17), React Hooks (7), Import (5)
- Nur TS/JS mit präzisen Fix-Descriptions
- 24 Tests

#### DependencyVersionScanner (P4) — +50 GHSA-Vulnerabilities
- **Neuartiges Feature:** Version-basiertes Scanning statt grep
- `shared/dependency_scanner.py` mit SemVer-Vergleich (packaging library)
- 50 Top-GHSA Einträge (npm 28, PyPI 12, Go 7, Cargo 3)
- Parst package.json, requirements.txt, go.mod, Cargo.toml
- 74 Tests

#### Manuelle Kuratierung (P5) — +156 Patterns
- 106 Top-100 Security (CWE Top-25 + OWASP Top-10)
- 20 Medusa v2 Service/Workflow/Module/Admin Anti-Patterns
- 15 Next.js Pages/App Router + Middleware Patterns
- 15 React Hooks Anti-Patterns
- 56 Tests

#### Performance
- PatternLoader lädt 830+ Patterns in <50ms
- DependencyScanner scannt Projekt in <100ms
- **Version:** 0.2.0 → 0.3.0 (Feature-Release)

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
