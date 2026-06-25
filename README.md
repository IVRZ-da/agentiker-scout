# 🔍 agentiker-scout — Hermes Plugin

> Unified analysis, bug-hunt, and web-research plugin with shared pattern pipeline.
> 43 tools across 3 domains — code analysis, vulnerability scanning, and autonomous web research.

[![Version](https://img.shields.io/badge/version-0.5.0-blue.svg)]()
[![Tests](https://img.shields.io/badge/tests-1390-green.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

# 🔍 agentiker-scout — Hermes Plugin

## 📋 Table of Contents

- [✨ Why?](#-why)
- [🚀 Quick Start](#-quick-start)
- [🛠 Tools](#-tools)
- [📦 Installation](#-installation)
- [🏗 Architecture](#-architecture)
- [🧪 Development](#-development)
- [🤝 Contributing](#-contributing)

---

## ✨ Why?

Hermes comes with basic search and read tools. When you need deeper insights — architecture analysis, vulnerability scanning, or multi-source web research — you'd normally juggle multiple tools and manual workflows.

**Scout combines three capabilities into one plugin:**

| Domain | What it does |
|--------|-------------|
| **Analysis** | Code & architecture analysis — dependency graphs, complexity, dead code, security, UI gaps, trend tracking |
| **Bug-Hunt** | Automated pattern-based vulnerability scanning — find bugs, triage, verify fixes, track history |
| **Research** | Autonomous web research — search → scrape → synthesize → save with full lifecycle management |

The **shared pattern pipeline** lets bug-hunt patterns feed into analysis scans and vice versa. Custom patterns discovered during analysis are immediately available for automated bug-hunt scans.

---

## 🚀 Quick Start

### Analyse einen Codebase

```python
# Architecture overview mit Dependency-Graph
analysis_architecture(path="/path/to/project", depth=2)
```

### Bug-Hunt starten

```python
# Session öffnen, Patterns scannen, Results sichern
bug_hunt_start(project="/path/to/project", scope="quick")
bug_hunt_scan(session_id="...", patterns=["security", "errors"])
bug_hunt_report(session_id="...", format="markdown")
```

### Autonome Recherche

```python
# Sub-Agent startet firecrawl_search → scrape → synthesize → save
research_auto(query="Neueste Medusa v2 Features 2026", depth=3)
```

---

## 🛠 Tools

<!-- README_AUTO -->

[![Version](https://img.shields.io/badge/version-0.5.2-blue.svg)]() [![Tests](https://img.shields.io/badge/tests-1652%20tests-green.svg)]() [![License](https://img.shields.io/badge/license-MIT-green.svg)]()

**Version:** 0.5.2

**Tests:** 1652 tests

**Tools (55):**


### Analysis — Code & Architecture (25 Tools)

| Tool | Description |
|------|-------------|
| `analysis_architecture` | Code & architecture analysis tool. |
| `analysis_ask` | Code & architecture analysis tool. |
| `analysis_code_move` | Code & architecture analysis tool. |
| `analysis_code_query` | Code & architecture analysis tool. |
| `analysis_deadcode` | Code & architecture analysis tool. |
| `analysis_dependency_risk` | Code & architecture analysis tool. |
| `analysis_diff` | Code & architecture analysis tool. |
| `analysis_diff_analysis` | Code & architecture analysis tool. |
| `analysis_duplicates` | Code & architecture analysis tool. |
| `analysis_framework` | Code & architecture analysis tool. |
| `analysis_graph` | Code & architecture analysis tool. |
| `analysis_graph_query` | Code & architecture analysis tool. |
| `analysis_inspect` | Code & architecture analysis tool. |
| `analysis_migration` | Code & architecture analysis tool. |
| `analysis_pattern_discover` | Code & architecture analysis tool. |
| `analysis_performance` | Code & architecture analysis tool. |
| `analysis_report` | Code & architecture analysis tool. |
| `analysis_review` | Code & architecture analysis tool. |
| `analysis_risk` | Code & architecture analysis tool. |
| `analysis_security` | Code & architecture analysis tool. |
| `analysis_test_insight` | Code & architecture analysis tool. |
| `analysis_timeline` | Code & architecture analysis tool. |
| `analysis_trend` | Code & architecture analysis tool. |
| `analysis_ui_gap` | Code & architecture analysis tool. |
| `analysis_watch` | Code & architecture analysis tool. |


### Bug-Hunt — Vulnerability Scanning (13 Tools)

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
| `research_start` | Startet eine neue Recherche. |
| `research_save` | Speichert die Ergebnisse einer Recherche. |
| `research_delete` | Löscht eine Recherche inklusive Plan- und Ergebnis-Dateien. |
| `research_cleanup` | Bereinigt alte oder verwaiste Research-Daten. |
| `research_tag` | Verwaltet Tags für eine Recherche (add/remove/set/clear). |
| `research_update` | Aktualisiert eine bestehende Recherche (erweitern/korrigieren). |
| `research_verify` | Prüft Quellen-URLs auf Erreichbarkeit und validiert Findings. |
| `research_auto` | Startet eine vollautonome Recherche. |
| `research_search` | Durchsucht gespeicherte Research-Ergebnisse mit BM25-Volltextsuche. |
| `research_status` | Zeigt Status und Details einer Recherche an. |
| `research_stats` | Zeigt Metriken und Statistiken über alle Recherchen. |
| `research_export` | Exportiert Research-Ergebnisse als Markdown oder Text. |
| `research_compare` | Vergleicht 2-3 Research-IDs. |
| `research_synthesize` | Synthetisiert passende Research-Ergebnisse via Honcho. |
| `research_merge` | Fasst mehrere Recherchen zu einer zusammen (dedupliziert). |
| `research_export_all` | Exportiert ALLE gespeicherten Recherchen als Bundle. |
| `research_schedule` | Plant periodische Recherchen via Hermes cronjob. |

### Recent Changelog

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

<!-- END README_AUTO -->

---



Enable the plugin in `~/.hermes/config.yaml`:

```yaml
plugins:
  enabled:
    - scout
```

Then install dependencies:

```bash
# Ins Hermes-Venv installieren (vom Plugin-Ordner aus)
cd ~/.hermes/plugins/agentiker-scout
~/.hermes/hermes-agent/venv/bin/pip install -e .

# Oder via Script
./scripts/install-deps.sh
```

**Dependencies:** `rich>=13.0`, `PyYAML>=6.0`, `packaging>=24.0`

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────┐
│                     Scout Plugin                     │
├────────────┬──────────────────┬──────────────────────┤
│  Analysis  │    Bug-Hunt      │      Research        │
│  13 Tools  │    13 Tools      │     17 Tools         │
│            │                  │                      │
│ • Inspect  │ • Start/Finding  │ • Auto-Research      │
│ • Arch     │ • Scan/Patterns  │ • Search/Save        │
│ • Deadcode │ • Triage/Verify  │ • Synthesize/Merge   │
│ • Security │ • Report/Export  │ • Schedule/Export    │
│ • UI Gap   │ • Fix/History    │ • Compare/Verify     │
│ • Risk     │                  │                      │
└────────────┴──────────────────┴──────────────────────┘
       │               │                  │
       └───────────────┴──────────────────┘
                       │
           ┌───────────▼───────────┐
           │  Shared Pattern       │
           │  Pipeline             │
           │  (patterns_core.py)   │
           │  • 45+ Built-in       │
           │  • Custom Patterns    │
           │  • Framework-Aware    │
           └───────────────────────┘
                       │
           ┌───────────▼───────────┐
           │  Persistence          │
           │  • Honcho (Sessions)  │
           │  • JSON (Research)    │
           │  • SQLite (Patterns)  │
           └───────────────────────┘
```

**Key design decisions:**
- **Intent-Priority-Scoring** — `bug > research > analysis` — when multiple domains could handle a query, the highest-priority handler wins
- **Shared Pattern Pipeline** — patterns from bug-hunt are available in analysis and vice versa
- **Single pre_llm_call Hook** — one hook handles all 3 domains instead of 3 separate hooks
- **Tool name compatibility** — `analysis_*`, `bug_hunt_*`, `research_*` namespaces preserved for backward compatibility

---

## 🧪 Development

```bash
cd ~/.hermes/plugins/agentiker-scout

# Tests ausführen
python3 -m pytest tests/ -q --tb=short

# Ruff Lint
python3 -m ruff check . --select F,E,T,W,I

# Pre-Commit Hook aktivieren
git config core.hooksPath .githooks
```

Aktuell: **1390 Tests** (45 skipped), Coverage per Pre-Commit Hook enforced.

---

## 📄 Changelog

Siehe `CHANGELOG.md` für vollständige Release-History.

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch
3. Add tests for your changes
4. Run `python3 -m pytest tests/ -q` — alle Tests müssen grün sein
5. Open a PR

Siehe `CONTRIBUTING.md` und `BRANCHING.md` für Details.

## 📄 License

[MIT](LICENSE)
