---
name: agentiker-scout
description: "Fusion von analysis, bughunt und deep-research in ein Plugin mit Shared Pattern Pipeline. 42 Tools, 69 Bug-Patterns, 3 Domains."
version: 0.6.0
author: agentiker
tags: [analysis, bughunt, research, patterns, code-analysis, security, web-research]
related_skills: [plan-follow, code-intel-plugin-maintenance, hermes-plugin-development]
---

# Scout Plugin

Fusion von **analysis**, **bughunt** und **deep-research** in ein Plugin mit Shared Pattern Pipeline.

## Architektur

```
scout/                          # Plugin-Root
├── __init__.py                 # Ein register() für alle 3 Domains (3 Hooks statt 9)
├── _fmt.py                     # Shared Formatierung (ersetzt 3 Duplikate)
├── plugin.yaml                 # Manifest v2 (manifest_version: 2)
│
├── shared/                     # Gemeinsame Infrastruktur
│   ├── grep_batch.py            # ein grep fuer alle Patterns (BRE, Chunking, Einzel-Fallback)
│   └── paths.py                 # zentrale Datenpfade (SCOUT_DATA_DIR)
│   ├── intent.py               # 1× Keyword-Detection statt 3× (mit Prioritäts-Wertung)
│   ├── cache.py                # TTL-Cache (intent, pattern, analysis, research)
│   ├── honcho.py               # Einheitliche Honcho-Persistenz
│   ├── patterns.py             # Shared Pattern Repository (CRUD + Migration)
│   └── patterns_research.py    # Research-Patterns (4 Vorlagen)
│
├── analysis/                   # Code-Analyse (25 analysis_* Tools)
│   ├── analysis_core.py        # Session-Management + Honcho-Integration
│   ├── analysis_intent.py      # Intent-Erkennung (Legacy, von shared/intent.py abgelöst)
│   ├── analysis_session.py     # AnalysisSession-Klasse
│   ├── analysis_profiles.py    # Profile-System (all/code/architecture/...)
│   ├── analysis_tools.py       # 25 Tool-Handler Re-Export Facade
│   └── tools/                  # 15+ Tool-Module
│       ├── base.py             # Shared Pattern Execution + Path-Validierung
│       ├── schemas.py          # JSON-Schemas für alle 25 Tools
│       ├── inspect.py          # analysis_inspect
│       ├── arch_deadcode.py    # analysis_architecture, _deadcode, _dependency_risk, _risk
│       ├── diff_trend_watch.py # analysis_diff, _trend, _watch, _diff_analysis
│       ├── perf_sec.py         # analysis_performance, _security, _ask
│       ├── framework_query_move.py # analysis_framework, _code_query, _code_move
│       ├── graph_patterns.py   # analysis_graph, _pattern_discover
│       ├── report.py           # analysis_report
│       ├── ui_gap.py           # analysis_ui_gap
│       ├── ui_discovery.py     # UI-Layer-Erkennung
│       ├── mapping.py          # Coverage-Matrix
│       # timeline.py entfernt (0.6.0: code_timeline direkt nutzen)
│       # duplicates.py entfernt (0.6.0: code_duplicates direkt nutzen)
│       ├── review.py           # analysis_review
│       # graph_query.py entfernt (0.6.0: code_graph_query direkt nutzen)
│       ├── test_insight.py     # analysis_test_insight
│       # migration.py entfernt (0.6.0: code_migration direkt nutzen)
│
├── bughunt/                    # Bug-Scans (13 bug_hunt_* Tools)
├── research/                   # Web-Recherche (9 research_* Tools)
│   ├── planner.py              # Fragen zerlegen, Budget verteilen (pure)
│   ├── fetcher.py              # Firecrawl-Client (urllib, Retry, Degradation)
│   ├── orchestrator.py         # suchen -> parallel lesen -> Fundstellen extrahieren
└── tests/                      # 2614 Tests (Stand: scripts/generate_readme.py --check)
│   ├── bughunt_hooks.py        # Auto-Pattern-Deduction
│   ├── bughunt_patterns.py     # 43 Built-in Patterns (7 Kategorien)
│   ├── bughunt_scanrunner.py   # grep-basierte Scan-Ausführung
│   ├── bughunt_fix.py          # Auto-Fix Prompt Generation
│   └── _fmt.py                 # Bughunt-spezifische Formatierung (rich)
│
├── research/                   # Web-Recherche (9 research_* Tools)
│   ├── research_tools.py       # Legacy Shim (re-exportiert tools/)
│   ├── research_hooks.py       # Firecrawl-Tracking + Honcho-Persistenz
│   └── tools/                  # Subpackage mit 4 Modulen
│
├── tests/                      # 2614 Tests (Stand: scripts/generate_readme.py --check)
│   ├── conftest.py             # Shared Mock-Infrastruktur
│   ├── test_analysis/          # 25 Tool-Tests
│   ├── test_bughunt/           # 542 Tests
│   └── test_research/          # 281 Tests
│
├── skills/SKILL.md             # Companion Skill
├── CHANGELOG.md
└── data/                       # Runtime-Daten
```

## Pattern Pipeline

```
bug_hunt_close() → _auto_deduce_patterns() → shared/patterns.save_pattern()
                                                      │
analysis_security/deadcode → shared/patterns.run() ◄──┘
                                                      │
analysis_pattern_discover → scannt → vergleicht ◄─────┘
                                                      │
research_start(pattern=...) → patterns_research.get() ←┘
research_save → findings → _auto_deduce_patterns() ────┘
```

## Tools (56 total)

### Code-Analyse (25)
`analysis_inspect`, `analysis_architecture`, `analysis_deadcode`, `analysis_performance`,
`analysis_security`, `analysis_ask`, `analysis_diff`, `analysis_trend`, `analysis_watch`,
`analysis_graph`, `analysis_report`, `analysis_pattern_discover`, `analysis_ui_gap`,
`analysis_framework`, `analysis_dependency_risk`, `analysis_pattern_discover`,
`analysis_diff_analysis`, `analysis_risk`, `analysis_review`, `analysis_test_insight`
`analysis_diff_analysis`, `analysis_risk`,
`analysis_review`, `analysis_graph` (Mermaid), `analysis_ui_gap`, `analysis_ui_inspect`

### Bug-Hunt (13)
`bug_hunt_start`, `bug_hunt_finding`, `bug_hunt_list`, `bug_hunt_close`, `bug_hunt_scan`, `bug_hunt_triage`, `bug_hunt_verify`, `bug_hunt_report`, `bug_hunt_export`, `bug_hunt_history`, `bug_hunt_pattern`, `bug_hunt_stats`, `bug_hunt_fix`

**Scan-Typen:** grep, code_security_scan, code_search_by_error, code_todo_finder, code_duplicates, code_merge_conflict, code_search, code_diagnostics

**Patterns:** 69 Built-in (43→69: +7 Security, +6 Code-Quality, +5 Java, +5 C/C++, +3 Ruby)

### Web-Recherche (17)
`research_start`, `research_save`, `research_search`, `research_status`, `research_cleanup`, `research_update` (Aktionen: patch/delete/tag/verify/merge/compare), `research_export` (`all=true` fuer alles), `research_synthesize`, `research_stats`

## Entscheidungsmatrix: Welches Tool für welche Aufgabe?

| Situation | Tool | Statt | Grund |
|-----------|------|-------|-------|
| Source-Code nach Symbolen durchsuchen | `code_search` / `code_symbols` | `grep` / `search_files` | AST-sicher, keine False-Positives |
| Datei-Struktur verstehen | `code_overview` / `code_capsule` | `read_file` | Token-Ersparnis 10-50x |
| Go-to-Definition | `code_definition` | `grep -rn "def foo"` | LSP-praezise |
| Referenzen finden | `code_references` | `grep -rn "foo("` | Cross-File, LSP |
| Impact vor Refactoring | `code_impact` / `code_blast_radius` | Manuelle Analyse | Automatisch, transitiv |
| Complexity messen | `code_complexity` | `radon cc` | Integriert, mit Breakdown |
| Error-Handling finden | `code_search_by_error` | `grep "except\\|throw"` | Error-Typ-bewusst |
| Unused Code finden | `code_unused_finder` | Manuelles Grep | AST-basiert |
| Duplikate finden | `code_duplicates` | `grep` + manuell | AST-Vergleich |
| TODO/FIXME finden | `code_todo_finder` | `grep -rn "TODO"` | Git-basiert, strukturiert |
| Grosse Refactorings | `code_refactor` / `code_batch_refactor` | `sed` / `patch` | AST-bewusst, Dry-Run |
| Plugin/Projekt analysieren | `analysis_inspect(depth=3)` | `search_files` + `read_file` | All-in-one: Symbole + Struktur + Diagnostics |
| Architektur-Checks | `analysis_architecture` | `grep` + `tree` | Abhängigkeitsgraph + Zyklen |
| Dead Code erkennen | `analysis_deadcode` | `grep` nach Imports | AST-gestützt, Cross-File |
| Performance-Hotspots | `analysis_performance` | Manuelle Analyse | Complexity + Hot Paths |
| Security-Scan | `analysis_security` oder `code_security_scan` | `grep` nach Secrets | Pattern-basiert, 30+ Rules |
| Bug-Hunt automatisieren | `bug_hunt_scan` mit Pattern-IDs | `grep` + manuelle Findings | 69 Built-in Patterns, auto-categorize |
| Bug-Hunt Session verwalten | `bug_hunt_start/finding/list/triage` | Todo-Liste | Strukturiert, persistiert, exportierbar |
| Web-Recherche | `research_auto(query)` oder `mcp_firecrawl_firecrawl_search` | `web_search` | Tiefe Recherche, auto-synthetisiert |

### Eine Registrierungs-Wahrheit (seit 0.6.0)

Die Tool-Definitionen liegen bei der Domaene, nicht in einer zentralen Datei:

```
analysis    analysis/analysis_tools.py::TOOL_HANDLERS   (Schema + Handler)
bughunt     bughunt/data/tool_schemas.json              (Name, Handler, Schema)
research    research/data/tool_schemas.json             (dito)
```

`shared/tool_registry.py::collect()` vereinigt sie zu **einer** Liste.
`scout_tool_registry.json` ist nur noch ein erzeugtes Artefakt (Konsolidat fuer
Lint, README, Evals) — kein Input mehr. Nach jeder Tool-Aenderung:

```
python3 scripts/gen_tool_registry.py --manifest   # Konsolidat + plugin.yaml
python3 scripts/generate_readme.py                # README
```

`tests/test_registry_drift.py` scheitert, sobald Registrierung, Konsolidat,
Manifest oder README auseinanderlaufen — nachgewiesen per Mutation (ein
entferntes Tool macht 5 Tests rot).

### Scan-Performance (seit 0.6.0)

- Alle grep-Patterns laufen in **einem** Subprozess pro `--include`-Gruppe
  (`shared/grep_batch.py`) statt einem Prozess pro Pattern. Ergebnisse sind
  identisch, der Dateibaum wird nur einmal durchlaufen.
- Patterns sind **grep-BRE**, nicht Python-Regex. Ein kaputtes Pattern laesst
  den Chunk einzeln nachfassen, statt die Nachbarn zu verschlucken.
- `scan_type="code_search"` mit Regex in `scan_query` wird als grep ausgefuehrt —
  vorher liefen diese 13 Patterns nie, weil `code_search` ein AST-Tool ist.
- `_timeout_executor` hat 4 Worker statt 1.
- `scripts/lint_patterns.py` erzwingt `false_positive_notes` (>= 20 Zeichen),
  eindeutige IDs und gueltige Severities. Alle 69 Patterns haben Notes.

### Recherche: plan vs. auto (seit 0.6.0)

- `research_start(query, mode="plan")` — Standard. Liefert Plan + Arbeitsschritte,
  das Modell fuehrt sie aus.
- `research_start(query, mode="auto")` — laeuft hier durch: Suche, paralleles Lesen
  (6 Threads), Fundstellen-Extraktion, optional eine Nachfassrunde bei `depth>=4`.
  Ergebnis sind **Fundstellen mit Quellenbezug**, keine fertige Prosa — die Synthese
  bleibt beim Modell.
- `schedule="24h"` merkt einen wiederkehrenden Auftrag; `research_status(show_orphans=true)`
  meldet faellige Auftraege als `schedules_due`. Kein Cron im Plugin.
- Bei nicht erreichbarem Firecrawl: ehrlicher Fehler, kein leeres "fertig".
  Konfiguration ueber `SCOUT_FIRECRAWL_URL` (Default http://127.0.0.1:3002)
  und `SCOUT_FIRECRAWL_TIMEOUT`.

| Schnelle Web-Suche | `mcp_firecrawl_firecrawl_search` | `web_search` | Firecrawl ist FIRST laut SOUL.md |
| DB Health-Check | `mcp_postgres_mcp_analyze_db_health` | Manuelle Queries | Indizes, Connections, Vacuums in einem |
| UI Gap Analysis | `analysis_ui_gap` | Manuelles Form-Vergleichen | Backend vs Frontend automatisch |
| Code Review zwischen Branches | `analysis_review` oder `code_review_assistant` | Manuelles Diff-Checken | Security + Complexity + Dead Code |
| Framework erkennen | `analysis_framework` | `package.json` + `go.mod` lesen | Automatischer Tech-Stack |
| Nach Session-Details suchen | `session_search(query=...)` | `honcho_search` oder `grep` | FTS5, schnell, strukturiert |

### 🔴 Wann NIEMALS grep im Terminal

| Vermeiden | Weil | Stattdessen |
|-----------|------|-------------|
| `grep -rn "pattern" *.ts` | False Positives aus Kommentaren | `code_search` (AST) |
| `grep -rn "class Foo"` | Findet auch Kommentare/Strings | `code_symbols(kind="class")` |
| `grep -rn "import.*from"` | Kein Struktur-Bewusstsein | `code_search(preset="imports")` |
| `grep -rn "function"` | Matcht auch Aufrufe | `code_symbols(kind="function")` |
| `find . -name "*.ts"` | `search_files(target="files")` ist schneller | `search_files(target="files")` |
| `grep nach Fehlern in Logs` | ✅ **AUSNAHME** — Build/Git/Pre-Commit | `terminal("grep ...")` ist OK |

## Intent Detection (Single Hook)

Ein `pre_llm_call` Hook ersetzt 3 separate Hooks. Bei Keyword-Overlap gewinnt die spezifischere Domain:

| Eingabe | Erkannt | Grund |
|---------|---------|-------|
| "analysiere den bug" | bug | bug > code |
| "recherchiere und analysiere" | research | research > code |
| "scan auf security" | bug | bug priorisiert |
| "sql query langsam" | db | db > code |

## Deployment

```yaml
# ~/.hermes/config.yaml
plugins:
  enabled:
    - scout  # statt analysis, bughunt, deep-research

skills:
  external_dirs:
    - ~/.hermes/plugins/scout/skills/
```

Nach config-Änderung: `pkill hermes && hermes`

## Hook-Vertrag (Hermes 0.23.1)

Es gibt genau EINEN `pre_llm_call`-Hook: `shared/intent.py::on_pre_llm_call`.

Hermes uebergibt seit 0.23.1:

```text
session_id, task_id, turn_id, user_message, conversation_history,
is_first_turn, model, platform, parent_session_id, sender_id
```

`messages` gibt es NICHT mehr. `shared/intent._last_user_message(kwargs)` liest deshalb in
dieser Reihenfolge: `user_message` -> letzte User-Nachricht aus `conversation_history` ->
`messages` (Altverhalten). Content darf `str` oder eine Block-Liste sein.

Der Bug-Hunt-Sessionblock kommt nicht mehr aus einem eigenen (nie registrierten) Hook,
sondern aus `bughunt_hooks.session_context()`, das der Intent-Hook bei Domain `bug` anhaengt.

Regel: Ein Hook, der einen Kwarg liest, den Hermes nicht mehr sendet, faellt STILL aus
(kein Log, kein Fehler). Deshalb haelt `tests/test_shared/test_hook_contract.py` den
Kwarg-Satz fest.

## Tool-Dispatch

Domain-Module rufen Hermes-Tools ueber `scout.shared.registry.registry.dispatch(name, args)`.
In `register(ctx)` wird die echte Hermes-Registry via `ctx.dispatch_tool` angebunden.
KEIN `tools.registry`-Shim mehr: der zeigte frueher auf eine lokale Dummy-Registry,
wodurch `honcho_search`, `honcho_reasoning`, `code_search_by_error` usw. wirkungslos waren.
