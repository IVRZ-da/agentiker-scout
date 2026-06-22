---
name: scout
description: "Fusion von analysis, bughunt und deep-research in ein Plugin mit Shared Pattern Pipeline. 46 Tools, 3 Domains, E2E-testing."
version: 0.3.3
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
├── plugin.yaml                 # Manifest v0.1.0
│
├── shared/                     # Gemeinsame Infrastruktur
│   ├── intent.py               # 1× Keyword-Detection statt 3× (mit Prioritäts-Wertung)
│   ├── cache.py                # TTL-Cache (intent, pattern, analysis, research)
│   ├── honcho.py               # Einheitliche Honcho-Persistenz
│   ├── patterns.py             # Shared Pattern Repository (CRUD + Migration)
│   └── patterns_research.py    # Research-Patterns (4 Vorlagen)
│
├── analysis/                   # Code-Analyse (12 analysis_* Tools)
│   ├── analysis_core.py        # Session-Management + Honcho-Integration
│   ├── analysis_intent.py      # Intent-Erkennung (Legacy, von shared/intent.py abgelöst)
│   ├── analysis_session.py     # AnalysisSession-Klasse
│   ├── analysis_profiles.py    # Profile-System (all/code/architecture/...)
│   ├── analysis_tools.py       # 12 Tool-Handler
│   └── tools/                  # UI-Discovery + Extractors
│       ├── base.py             # Shared Pattern Execution + Path-Validierung
│       ├── schemas.py          # JSON-Schemas für alle 12 Tools
│       ├── ui_discovery.py     # UI-Layer-Erkennung (Next.js, Medusa, Go)
│       ├── ui_gap.py           # Gap-Detection (Module ohne Pages)
│       ├── mapping.py          # Coverage-Matrix
│       └── extractors/         # Framework-Extraktoren
│
├── bughunt/                    # Bug-Scans (13 bug_hunt_* Tools)
│   ├── bughunt_core.py         # BugHuntSession + Finding + Pattern-Management
│   ├── bughunt_tools.py        # 13 Tool-Handler
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
├── tests/                      # 949+ Tests
│   ├── conftest.py             # Shared Mock-Infrastruktur
│   ├── test_analysis/          # 429 Tests
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

## Tools (42 total)

### Code-Analyse (12)
`analysis_inspect`, `analysis_architecture`, `analysis_deadcode`, `analysis_performance`, `analysis_security`, `analysis_ask`, `analysis_diff`, `analysis_trend`, `analysis_watch`, `analysis_graph`, `analysis_report`, `analysis_pattern_discover`, `analysis_ui_gap`

### Bug-Hunt (13)
`bug_hunt_start`, `bug_hunt_finding`, `bug_hunt_list`, `bug_hunt_close`, `bug_hunt_scan`, `bug_hunt_triage`, `bug_hunt_verify`, `bug_hunt_report`, `bug_hunt_export`, `bug_hunt_history`, `bug_hunt_pattern`, `bug_hunt_stats`, `bug_hunt_fix`

### Web-Recherche (17)
`research_start`, `research_save`, `research_search`, `research_status`, `research_delete`, `research_cleanup`, `research_export`, `research_compare`, `research_synthesize`, `research_schedule`, `research_auto`, `research_merge`, `research_tag`, `research_update`, `research_verify`, `research_export_all`, `research_stats`

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
