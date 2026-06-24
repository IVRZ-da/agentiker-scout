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

<!-- AUTO-GENERATED -->
| Tool | Description |
|------|-------------|
| `analysis_architecture` | Full architecture analysis: workspace structure → dependency graph → hot paths → cycles |
| `analysis_ask` | Natural language questions about a codebase — uses Honcho context |
| `analysis_code_move` | Move symbol between files via AST extraction |
| `analysis_code_query` | Smart query router — auto-selects best code intelligence tool |
| `analysis_deadcode` | Finds unused imports, unused functions, orphaned error handlers |
| `analysis_dependency_risk` | Code dependency health assessment with risk score (0-10) |
| `analysis_diff` | Compare two analysis results — shows added/removed/changed findings |
| `analysis_diff_analysis` | Compare two Git-refs: changed functions, complexity delta, blast radius |
| `analysis_duplicates` | Find duplicate/similar code blocks via AST comparison |
| `analysis_framework` | Framework profile detection — auto-detects tech stack with confidence scoring |
| `analysis_graph` | Generates Mermaid diagrams from analysis reports |
| `analysis_graph_query` | Knowledge graph queries: callers, callees, hot paths, cycles |
| `analysis_inspect` | Multi-step analysis: symbols → definitions → references → call hierarchy → cycles in one call |
| `analysis_migration` | YAML-based bulk pattern migrations with dry-run |
| `analysis_pattern_discover` | Discover code patterns that look like bugs but aren't covered by existing patterns |
| `analysis_performance` | Bottleneck analysis: complexity hotspots, slow paths, inlay hints |
| `analysis_report` | Generate structured analysis report and persist in Honcho |
| `analysis_review` | Automated code review: diff analysis + security + complexity delta |
| `analysis_risk` | Multi-factor risk assessment combining dependency risk, complexity, dead code, security |
| `analysis_security` | Scans for orphaned error handlers, vulnerability patterns, security anti-patterns |
| `analysis_test_insight` | Test coverage analysis for a symbol or project |
| `analysis_timeline` | Symbol evolution over git history — commits, complexity trend, author distribution |
| `analysis_trend` | Trend analysis over time — queries Honcho for past analysis results |
| `analysis_ui_gap` | Discovers UI layers (Next.js, Medusa admin, API routes, Go handlers) and compares against backend modules |
| `analysis_watch` | Set up recurring cron-based analysis on a path with change detection |
| `bug_hunt_close` | Close a session with optional summary |
| `bug_hunt_export` | Export findings as JSON or Markdown |
| `bug_hunt_finding` | Add a finding (title, severity P0-P3, category, evidence, fix) |
| `bug_hunt_fix` | Generate auto-fix prompt for a finding |
| `bug_hunt_history` | Search past bug-hunt sessions by project |
| `bug_hunt_list` | List findings filtered by severity, status, category, or file |
| `bug_hunt_pattern` | List, inspect, save, or manage bug patterns (45+ built-in) |
| `bug_hunt_report` | Generate structured report (JSON/Markdown) grouped by severity |
| `bug_hunt_scan` | Run automated scans using the 45+ pattern library |
| `bug_hunt_start` | Start a new bug-hunt session with scope (quick/comprehensive/custom) |
| `bug_hunt_stats` | Statistics about findings in a session |
| `bug_hunt_triage` | Update finding severity/status with notes |
| `bug_hunt_verify` | Verify if a finding's bug still exists in the code |
| `research_auto` | Autonomous research: spawns a sub-agent that searches → scrapes → synthesizes → saves |
| `research_cleanup` | Clean old or orphaned research data |
| `research_compare` | Compare 2-3 research results side by side |
| `research_delete` | Delete a research including plan and result files |
| `research_export` | Export a research as Markdown or text |
| `research_export_all` | Export ALL researches as JSON/Markdown/CSV |
| `research_merge` | Merge 2-5 researches into one (deduplicated) |
| `research_save` | Save results with summary, findings, sources, tags |
| `research_schedule` | Schedule periodic research via Hermes cron |
| `research_search` | Full-text search over saved research with BM25 ranking |
| `research_start` | Start a new research — validates query, creates plan file |
| `research_stats` | Metrics and statistics about all researches |
| `research_status` | Show status and details of a research |
| `research_synthesize` | Synthesize related research via Honcho |
| `research_tag` | Manage tags for a research (add/remove/set/clear) |
| `research_update` | Update an existing research (append findings/sources) |
| `research_verify` | Verify source URLs and validate findings |
<!-- END AUTO-GENERATED -->

---



Enable the plugin in `~/.hermes/config.yaml`:

```yaml
plugins:
  enabled:
    - scout
```

Then install dependencies:

```bash
# Ins Hermes-Venv installieren
~/.hermes/hermes-agent/venv/bin/pip install -e /home/jo/.hermes/plugins/scout/

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
cd /home/jo/.hermes/plugins/scout

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
