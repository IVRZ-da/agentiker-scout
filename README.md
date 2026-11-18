# 🔍 agentiker-scout — Hermes Plugin

> Unified analysis, bug-hunt, and web-research plugin with shared pattern pipeline.
> 42 tools across 3 domains — code analysis, vulnerability scanning, and autonomous web research.

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

[![Version](https://img.shields.io/badge/version-0.6.6-blue.svg)]() [![Tests](https://img.shields.io/badge/tests-2775%20tests-green.svg)]() [![License](https://img.shields.io/badge/license-MIT-green.svg)]()

**Version:** 0.6.6

**Tests:** 2775 tests

**Tools (62):**


### Analysis — Code & Architecture (20 Tools)

| Tool | Description |
|------|-------------|
| `analysis_architecture` | Full architecture analysis: workspace structure to dependency graph to hot paths to cycle detection to complexity hotspots. |
| `analysis_ask` | Ask a natural language question about a codebase using Honcho context. |
| `analysis_deadcode` | Dead code analysis: unused imports, unused functions, orphaned error handlers. |
| `analysis_dependency_risk` | Rate dependency risks (score 0-10) for a file or project. |
| `analysis_diff` | Compare two analysis results and show what changed — structured diff. |
| `analysis_diff_analysis` | Compare two git refs and show changed functions with complexity delta. |
| `analysis_framework` | Show the framework profile of a project with confidence scoring. |
| `analysis_graph` | Generate a Mermaid diagram from analysis results (dependency, cycles, summary). |
| `analysis_inspect` | Multi-step code analysis: symbols → definition → references → call hierarchy. |
| `analysis_pattern_discover` | Discover code patterns that look like bugs but aren't covered by shared patterns. |
| `analysis_performance` | Performance analysis: bottlenecks, complexity hotspots, slow paths. |
| `analysis_report` | Generate a structured analysis report from findings and persist in Honcho. |
| `analysis_review` | Automated code review between git refs: diff + security + complexity delta. |
| `analysis_risk` | Multi-factor risk assessment: dependency + complexity + deadcode + security + hotspots. |
| `analysis_security` | Security analysis: orphaned error handlers, vulnerability patterns, anti-patterns. |
| `analysis_test_insight` | Analyze test coverage of a symbol or project, generate scaffolds. |
| `analysis_trend` | Trend analysis over time: symbol count, dead code, complexity hotspots. |
| `analysis_ui_gap` | UI gap analysis: backend modules without admin/storefront pages, orphan pages. |
| `analysis_ui_inspect` | UI element analysis: A11y tree + DOM inspection + console/network check. |
| `analysis_watch` | Set up recurring analysis watch (cron job) with change reporting. |


### Bug-Hunt — Vulnerability Scanning (13 Tools)

| Tool | Description |
|------|-------------|
| `bug_hunt_start` | Open a bug-hunt session for a project before you record anything. |
| `bug_hunt_finding` | Record one bug finding inside an existing session. |
| `bug_hunt_list` | List findings of a session, optionally filtered by severity, status, category or file. |
| `bug_hunt_close` | Close a bug-hunt session and freeze it with a summary. |
| `bug_hunt_scan` | Run the automated pattern scan against a project and create findings from matches. |
| `bug_hunt_triage` | Classify findings: set a workflow status (triaged, false_positive, fixed, . |
| `bug_hunt_verify` | Mark findings as verified after you reproduced or confirmed them. |
| `bug_hunt_fix` | Record that a finding was fixed, with the fix description and optional commit reference. |
| `bug_hunt_report` | Render the session report as markdown or JSON, optionally grouped by severity, category or file. |
| `bug_hunt_export` | Export a session report to a file on disk. |
| `bug_hunt_history` | List past bug-hunt sessions with project, date, status and finding counts. |
| `bug_hunt_pattern` | Read or manage the pattern catalogue: list patterns, show one in detail, list categories, or save a new custom pattern from a confirmed finding. |
| `bug_hunt_stats` | Summarise a session: findings by severity, by status, by category and the top affected files. |


### Research — Web Research & Synthesis (9 Tools)

| Tool | Description |
|------|-------------|
| `research_start` | Open a research session and either plan it or run it end to end. |
| `research_save` | Store the result of a research session: summary, findings and sources. |
| `research_cleanup` | Remove stale research artefacts: orphaned plans (started but never saved) or all leftover files. |
| `research_update` | Modify, delete, tag, verify, merge or compare stored research results. |
| `research_search` | Full-text search across all stored research results (BM25 ranking, no external dependency). |
| `research_status` | Show the state of one research session, or list all sessions with their status. |
| `research_stats` | Aggregate numbers over the whole research store: sessions by status, total findings and sources, most used tags. |
| `research_export` | Render one research result as markdown or plain text. |
| `research_synthesize` | Build a cross-cutting answer from several stored research results. |


### analysis (20 Tools)

| Tool | Description |
|------|-------------|
| `analysis_inspect` | One-shot deep dive into a file or directory: symbols, definitions, references, call hierarchy and diagnostics, weighted by depth 1-5. |
| `analysis_report` | Assemble a structured analysis report from findings and recommendations, optionally persisting it. |
| `analysis_architecture` | Map a project: workspace structure, dependency graph, hot paths, import cycles, complexity hotspots. |
| `analysis_deadcode` | Find code nothing uses: unused imports, unused functions, orphaned error handlers. |
| `analysis_performance` | Look for performance problems: complexity hotspots, diagnostics, hot paths, inlay hints. |
| `analysis_security` | Security pass: runs the security pattern catalogue and error-handling checks over a path. |
| `analysis_ask` | Ask a natural-language question about the codebase and answer it from stored analysis context. |
| `analysis_diff` | Compare two analysis reports and show what changed between them. |
| `analysis_trend` | Track how metrics developed across successive runs: finding counts, complexity, coverage. |
| `analysis_watch` | Watch a path and report changes since the last run, so repeated checks stay cheap. |
| `analysis_graph` | Render analysis results as a Mermaid diagram: dependency graph, cycles or summary view. |
| `analysis_ui_gap` | Compare backend capabilities with frontend usage to find endpoints the UI never calls. |
| `analysis_pattern_discover` | Find bug-shaped code that the shared pattern catalogue does not cover yet. |
| `analysis_framework` | Identify the frameworks and tooling of a project with confidence scores. |
| `analysis_dependency_risk` | Rate dependency risk for a file or project: outdated, unmaintained or heavily coupled dependencies. |
| `analysis_diff_analysis` | Compare two git refs and show which symbols changed, with complexity delta and blast radius. |
| `analysis_risk` | Rate the risk of a change or a file: dependency risk, test coverage, blast radius. |
| `analysis_review` | Pre-commit style review: diff analysis plus review assistant plus a security pass. |
| `analysis_test_insight` | Work out which tests cover a symbol, and optionally draft new ones. |
| `analysis_ui_inspect` | Inspect rendered UI: DOM structure, selectors and accessibility issues for a route. |

### Recent Changelog

## [0.6.6] — 2026-11-18

### 🎟️ Katalogfähig: Core-Rebind entfernt (Regel 9)

Der Hermes-Plugin-Katalog lässt keine Runtime-Overrides von Hermes-Core zu
(Regel 9). `hermes plugins validate` hat den Rebind von
`toolsets._HERMES_CORE_TOOLS` deshalb als `no core override` abgelehnt — das
Plugin war damit nicht einreichbar.

- **`_mark_tools_eager()` entfernt**, `EAGER_TOOLS = ()`. Die drei Dispatcher
  sind jetzt deferred: jeder Aufruf läuft über `tool_call`. Preis: ein
  zusätzlicher Bridge-Turn pro Nutzung (Analyse/Bughunt wird stoßweise gerufen,
  nicht pro Turn wie `plan_current`). Messwerte und Rückweg:
  `references/core-override-analysis.md`.
- **Gate geleert**: `references/core_override_allowlist.txt` enthält keinen
  Eintrag mehr — `scripts/validate_gate.py` bricht jetzt bei jedem roten Check.
- **Regressionstest** `test_plugin_never_writes_core_attributes`: kein
  Schreibzugriff auf Core-Modul-Attribute mehr im Quellbaum.
- **`hermes plugins validate` ist vollständig grün** — Katalog-Entry folgt.

## [0.6.5] — 2026-11-18

### 🔀 Namespace-Fusion: 42 Tools → 3 Dispatcher

Die Tool-Fläche wurde von 42 Einzel-Tools auf drei Namespace-Dispatcher
(`analysis`, `bughunt`, `research`) mit `op`-Parameter reduziert. Das spart in
jedem Turn Schema-Tokens; der Katalog wird per Replay der echten Registrierung
erzeugt, nicht handgepflegt.

- **`namespaces.py`** neu: Dispatcher-Bau + `op`-Enum je Namespace,
  Legacy-Schalter `SCOUT_NAMESPACES=0` schaltet die Einzel-Tools zurück.
- **Eager-Set über Allowlist**: nur die tatsächlich in jedem Turn gebrauchten
  Tools sind eager, der Rest wird deferred nachgeladen.
- **Intent-Hints modusabhängig** (`shared/intent.py`): Hinweise nennen die
  op-Namen des aktiven Modus statt toter Einzel-Tool-Namen.
- **Schema-Budget-Gate**: `scripts/tool_schema_audit.py` misst chars/Tokens der
  registrierten Fläche, `scripts/pre-commit-hook` blockt bei Überschreitung.
- **`scripts/validate_gate.py`** + `references/core_override_allowlist.txt`:
  Wirkungsnachweis für jeden Core-Rebind statt Sammel-Freigabe.
- **Tests**: `test_namespaces.py`, `test_namespace_coverage.py` (jeder `op` hat

## [0.6.4] — 2026-11-18

### 🔒 Security-Scan-Selbstbezug behoben (`validate` grün)

`hermes plugins validate scout` meldete das Plugin selbst als `dangerous`, weil
die Security-Patterns als Klartext-Fragmente im Quellcode standen und der eigene
Scan darauf ansprang.

- **Pattern-Fragmente kodiert** in `bughunt/data/patterns_data.json` abgelegt,
  der Loader setzt sie zur Laufzeit zusammen — der Scan trifft nur noch fremden
  Code, `validate` läuft ohne `dangerous`-Fund durch.
- **`requires_hermes: ">=0.23.1"`** in `plugin.yaml` deklariert.
- **Manifest-Gate im Pre-Commit**: `gen_manifest_capabilities --check` verhindert
  driftende `provides_tools`-Listen.
- **`tests/test_pattern_encoding.py`**: positive Tests pro Regel belegen, dass die
  zusammengesetzten Patterns weiterhin echt treffen.

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

Aktuell: **siehe Test-Badge oben** — die Zahl wird von `scripts/generate_readme.py --check`
aus der echten Sammlung erzeugt, damit sie nicht driftet. Pre-Commit-Hook erzwingt Tests
und Coverage.

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

## Compatibility

Tested against **Hermes Agent v0.23.1** (Python 3.13 and 3.14).

- `pre_llm_call` is called with `user_message` + `conversation_history` (Hermes >= 0.23);
  the plugin also still accepts the legacy `messages` kwarg.
- Manifest v2 (`manifest_version: 2`) with generated `provides_tools` / `provides_hooks`:
  `python3 scripts/gen_manifest_capabilities.py` (add `--check` in CI).
- Tool dispatch goes through `ctx.dispatch_tool` (public plugin API) - no `sys.modules`
  patching of Hermes core packages.
