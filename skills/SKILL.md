---
name: agentiker-scout
description: "Fusion von analysis, bughunt und deep-research in ein Plugin mit Shared Pattern Pipeline. 55 Tools, 69 Bug-Patterns, 3 Domains."
version: 0.5.0
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
├── plugin.yaml                 # Manifest v0.4.0
│
├── shared/                     # Gemeinsame Infrastruktur
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
│       ├── timeline.py         # analysis_timeline
│       ├── duplicates.py       # analysis_duplicates
│       ├── review.py           # analysis_review
│       ├── graph_query.py      # analysis_graph_query
│       ├── test_insight.py     # analysis_test_insight
│       └── migration.py        # analysis_migration
│
├── bughunt/                    # Bug-Scans (13 bug_hunt_* Tools)
├── research/                   # Web-Recherche (17 research_* Tools)
└── tests/                      # 1361+ Tests
│   ├── bughunt_hooks.py        # Auto-Pattern-Deduction
│   ├── bughunt_patterns.py     # 43 Built-in Patterns (7 Kategorien)
│   ├── bughunt_scanrunner.py   # grep-basierte Scan-Ausführung
│   ├── bughunt_fix.py          # Auto-Fix Prompt Generation
│   └── _fmt.py                 # Bughunt-spezifische Formatierung (rich)
│
├── research/                   # Web-Recherche (17 research_* Tools)
│   ├── research_tools.py       # Legacy Shim (re-exportiert tools/)
│   ├── research_hooks.py       # Firecrawl-Tracking + Honcho-Persistenz
│   └── tools/                  # Subpackage mit 4 Modulen
│
├── tests/                      # 1361+ Tests
│   ├── conftest.py             # Shared Mock-Infrastruktur
│   ├── test_analysis/          # 25 Tool-Tests
│   ├── test_bughunt/           # 323 Tests
│   └── test_research/          # 197 Tests
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

## Tools (55 total)

### Code-Analyse (25)
`analysis_inspect`, `analysis_architecture`, `analysis_deadcode`, `analysis_performance`,
`analysis_security`, `analysis_ask`, `analysis_diff`, `analysis_trend`, `analysis_watch`,
`analysis_graph`, `analysis_report`, `analysis_pattern_discover`, `analysis_ui_gap`,
`analysis_framework`, `analysis_code_query`, `analysis_code_move`,
`analysis_timeline`, `analysis_duplicates`, `analysis_dependency_risk`,
`analysis_diff_analysis`, `analysis_risk`,
`analysis_review`, `analysis_graph_query`, `analysis_test_insight`, `analysis_migration`

### Bug-Hunt (13)
`bug_hunt_start`, `bug_hunt_finding`, `bug_hunt_list`, `bug_hunt_close`, `bug_hunt_scan`, `bug_hunt_triage`, `bug_hunt_verify`, `bug_hunt_report`, `bug_hunt_export`, `bug_hunt_history`, `bug_hunt_pattern`, `bug_hunt_stats`, `bug_hunt_fix`

**Scan-Typen:** grep, code_security_scan, code_search_by_error, code_todo_finder, code_duplicates, code_merge_conflict, code_search, code_diagnostics

**Patterns:** 69 Built-in (43→69: +7 Security, +6 Code-Quality, +5 Java, +5 C/C++, +3 Ruby)

### Web-Recherche (17)
`research_start`, `research_save`, `research_search`, `research_status`, `research_delete`, `research_cleanup`, `research_export`, `research_compare`, `research_synthesize`, `research_schedule`, `research_auto`, `research_merge`, `research_tag`, `research_update`, `research_verify`, `research_export_all`, `research_stats`

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
