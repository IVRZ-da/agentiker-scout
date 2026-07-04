# 🔍 agentiker-scout — Hermes Plugin

> Unified analysis, bug-hunt, and web-research plugin with shared pattern pipeline.
> 43 tools across 3 domains — code analysis, vulnerability scanning, and autonomous web research.
>
> [![Version](https://img.shields.io/badge/version-0.5.16-blue.svg)]() [![Tests](https://img.shields.io/badge/tests-2148%20tests-green.svg)]() [![License](https://img.shields.io/badge/license-MIT-green.svg)]()

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

### Installation
```bash
cd ~/.hermes/plugins
git clone https://github.com/IVRZ-da/agentiker-scout.git
cd agentiker-scout
pip install -e .
```

### Analyse einen Codebase
```python
analysis_architecture(path="/path/to/project", depth=2)
```

### Bug-Hunt starten
```python
session = bug_hunt_start(project="/path/to/project", scope="quick")
bug_hunt_scan(session_id=session["session_id"], patterns=["security", "errors"])
bug_hunt_report(session_id=session["session_id"], format="markdown")
```

### Autonome Recherche
```python
research_auto(query="Neueste Medusa v2 Features 2026", depth=3)
```

### Cross-Plugin: code-intel Analyse-Findings scouten
```python
analysis_deadcode(path="src/")
analysis_security(path="src/")
# Findings automatisch in scout Pattern-Library
bug_hunt_pattern(action="list_categories")
```
```

---

## 🛠 Tools

<!-- README_AUTO -->

[![Version](https://img.shields.io/badge/version-0.5.16-blue.svg)]() [![Tests](https://img.shields.io/badge/tests-2148%20tests-green.svg)]() [![License](https://img.shields.io/badge/license-MIT-green.svg)]()

**Version:** 0.5.16

**Tests:** 2148 tests

**Tools (56):**


### Analysis — Code & Architecture (26 Tools)

| Tool | Description |
|------|-------------|
| `analysis_architecture` | Full architecture analysis: workspace structure to dependency graph to hot paths to cycle detection to complexity hotspots. |
| `analysis_ask` | Ask a natural language question about a codebase using Honcho context. |
| `analysis_code_move` | Move a symbol (function/class) between files via AST extraction. |
| `analysis_code_query` | Smart query router for code intelligence — auto-selects the best tool. |
| `analysis_deadcode` | Dead code analysis: unused imports, unused functions, orphaned error handlers. |
| `analysis_dependency_risk` | Rate dependency risks (score 0-10) for a file or project. |
| `analysis_diff` | Compare two analysis results and show what changed — structured diff. |
| `analysis_diff_analysis` | Compare two git refs and show changed functions with complexity delta. |
| `analysis_duplicates` | Find duplicate or similar code blocks via AST comparison. |
| `analysis_framework` | Show the framework profile of a project with confidence scoring. |
| `analysis_graph` | Generate a Mermaid diagram from analysis results (dependency, cycles, summary). |
| `analysis_graph_query` | Search the Knowledge Graph of a project (callers, callees, hot paths). |
| `analysis_inspect` | Multi-step code analysis: symbols → definition → references → call hierarchy. |
| `analysis_migration` | Run YAML-based bulk migrations across a project (dry-run by default). |
| `analysis_pattern_discover` | Discover code patterns that look like bugs but aren't covered by shared patterns. |
| `analysis_performance` | Performance analysis: bottlenecks, complexity hotspots, slow paths. |
| `analysis_report` | Generate a structured analysis report from findings and persist in Honcho. |
| `analysis_review` | Automated code review between git refs: diff + security + complexity delta. |
| `analysis_risk` | Multi-factor risk assessment: dependency + complexity + deadcode + security + hotspots. |
| `analysis_security` | Security analysis: orphaned error handlers, vulnerability patterns, anti-patterns. |
| `analysis_test_insight` | Analyze test coverage of a symbol or project, generate scaffolds. |
| `analysis_timeline` | Show symbol evolution across git history with complexity trend. |
| `analysis_trend` | Trend analysis over time: symbol count, dead code, complexity hotspots. |
| `analysis_ui_gap` | UI gap analysis: backend modules without admin/storefront pages, orphan pages. |
| `analysis_ui_inspect` | UI element analysis: A11y tree + DOM inspection + console/network check. |
| `analysis_watch` | Set up recurring analysis watch (cron job) with change reporting. |


### Bug-Hunt — Vulnerability Scanning (13 Tools)

| Tool | Description |
|------|-------------|
| `bug_hunt_start` | Start a bug-hunt session. |
| `bug_hunt_finding` | Add a finding to a session. |
| `bug_hunt_list` | List findings for a session. |
| `bug_hunt_close` | Close a bug-hunt session. |
| `bug_hunt_scan` | Run automated scans using pattern library. |
| `bug_hunt_triage` | Update severity/status for findings. |
| `bug_hunt_verify` | Verify if a finding's bug still exists. |
| `bug_hunt_fix` | Generate an auto-fix prompt for a bug. |
| `bug_hunt_report` | Generate a structured bug-hunt report. |
| `bug_hunt_export` | Export findings as JSON or Markdown. |
| `bug_hunt_history` | Search past bug-hunt sessions. |
| `bug_hunt_pattern` | List, inspect, save, or manage bug patterns. |
| `bug_hunt_stats` | Statistics about findings in a session. |


### Research — Web Research & Synthesis (17 Tools)

| Tool | Description |
|------|-------------|
| `research_start` | Start a new research session. |
| `research_save` | Save research results. |
| `research_delete` | Delete a research session. |
| `research_cleanup` | Cleanup old research data. |
| `research_tag` | Manage tags for a research session. |
| `research_update` | Update existing research data. |
| `research_verify` | Verify source URLs and findings. |
| `research_auto` | Autonomous web research agent. |
| `research_search` | Search saved research results. |
| `research_status` | Show research status and details. |
| `research_stats` | Show research metrics and statistics. |
| `research_export` | Export research as Markdown or text. |
| `research_compare` | Compare 2-3 research results. |
| `research_synthesize` | Synthesize research via Honcho. |
| `research_merge` | Merge multiple research sessions. |
| `research_export_all` | Export all research as a bundle. |
| `research_schedule` | Schedule periodic research. |

### Recent Changelog

## [0.5.16] — 2026-06-30

### Changed
- **Tool-Descriptions in README** — 25 Analysis-Tools mit individuellen Beschreibungen statt generischem "Code & architecture analysis tool."
- **Badges oben ergänzt** — Version, Tests, License im Header

[0.5.15] — 2026-06-28
### P3 — Lazy Loading + Keywords
- **intent.py:** Double-Scan eliminiert (Gate + Detection → Single-Pass)
- **yaml_rule_loader.py:** `import yaml` lazy (module → function-level, spart ~100ms Startzeit)
- **pattern_loader.py:** `import yaml` lazy (module → function-level)
- **Tests:** 2103 passed, 45 skipped, 0 failures

## [0.5.14] — 2026-06-28
### P2 — Code-Struktur (bughunt_tools.py Split + research_search Refactoring)
- **bughunt_tools.py:** 943→28 Zeilen (Re-Export Facade)
- **tools/ subpackage:** base.py, session.py, scan.py, patterns.py, history.py
- **research_search:** Complexity 30→~12 (5 Helfer extrahiert)
- **Mock-Pfade:** auf tools.base korrigiert (Import-Capture Pattern)
- **Tests:** 2103 passed, 45 skipped, 0 failures

## [0.5.13] — 2026-06-28
### P1 — Daten-Auslagerung (patterns_data.py + dependency_scanner.py)
- **patterns_data.py:** 1050→113 Zeilen (−937), Daten laden lazy aus `patterns_data.json`
- **dependency_scanner.py:** 924→473 Zeilen (−451), VULNERABILITIES laden lazy aus `vulnerabilities.json`
- **BugPattern-Klasse + Scanner-Logik** bleiben in Python (kein API-Bruch)
- **Lazy Loading:** `_ensure_loaded()` + `_ensure_vulnerabilities_loaded()` erst bei erstem Zugriff
- **Tests:** 2103 passed, 45 skipped, 0 failures

<!-- END README_AUTO -->

---

## ⚠️ Limitations

| Limitation | Description |
|------------|-------------|
| **Analysis Depth** | Deep analysis of very large monorepos (>500 files) may require increased timeouts. |
| **Bug-Hunt False Positives** | Automated pattern-based scanning may produce false positives; findings should be manually triaged before action. |
| **Web Research Reliability** | Autonomous research depends on external website availability, site structure changes, and may produce incomplete results on JavaScript-heavy pages. |
| **Tool Dependencies** | Some analysis and bug-hunt features require `ast-grep`, `tree-sitter`, and `ruff` to be installed alongside the plugin. |

---

## 🔄 Subagent-Integration

Scout plugin tools can be called directly by subagents. When a subagent runs analysis, bug-hunt, or research tasks, it uses the Scout tool namespaces:

- `analysis_*` — Code & Architecture Analysis
- `bug_hunt_*` — Vulnerability Scanning
- `research_*` — Web Research & Synthesis

**Empfohlene Workflows:**

1. **Bug-Hunt Sub-Agent:** Startet `bug_hunt_start` → `bug_hunt_scan` → `bug_hunt_report`
2. **Research Sub-Agent:** Startet `research_start` → `research_search` → `research_synthesize`
3. **Analysis Sub-Agent:** Runs `analysis_architecture` → `analysis_report` for architecture documentation

> **Inspired** by [agentiker-code-intel](https://git.agentiker.de/johannes/agentiker-code-intel) — shared pattern pipeline concept

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

# Run tests
python3 -m pytest tests/ -q --tb=short

# Ruff Lint
python3 -m ruff check . --select F,E,T,W,I

# Pre-Commit Hook aktivieren
git config core.hooksPath .githooks
```

Aktuell: **2148 Tests** (45 skipped), Coverage per Pre-Commit Hook enforced.

---

## 📄 Changelog

See `CHANGELOG.md` for full release history.

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch
3. Add tests for your changes
4. Run `python3 -m pytest tests/ -q` — all tests must pass
5. Open a PR

See `CONTRIBUTING.md` and `BRANCHING.md` for details.

## 📄 License

[MIT](LICENSE)
