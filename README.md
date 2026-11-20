# 🔍 agentiker-scout — Hermes Plugin

> Unified analysis, bug-hunt, and web-research plugin with shared pattern pipeline.
> 50 tools across 3 domains — code analysis, vulnerability scanning, and autonomous web research.

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

[![Version](https://img.shields.io/badge/version-0.6.9-blue.svg)]() [![Tests](https://img.shields.io/badge/tests-2800%20tests-green.svg)]() [![License](https://img.shields.io/badge/license-MIT-green.svg)]()

**Version:** 0.6.9

**Tests:** 2800 tests

**Tools (50):**


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


### Research — Web Research & Synthesis (17 Tools)

| Tool | Description |
|------|-------------|
| `research_auto` | Run a research end to end: search, page reads, finding extraction and save. |
| `research_cleanup` | Remove stale research artefacts: orphaned plans (started but never saved) or all leftover files. |
| `research_compare` | Compare two or three stored researches: status, counts, tags, shared and unique sources. |
| `research_delete` | Delete a research with its plan and result files. |
| `research_export` | Render one research result as markdown or plain text. |
| `research_export_all` | Export every stored research into one document, newest first. |
| `research_merge` | Merge several researches into one, de-duplicating findings and sources. |
| `research_save` | Store the result of a research session: summary, findings and sources. |
| `research_schedule` | Register a recurring research run with the Hermes cron scheduler. |
| `research_search` | Full-text search across all stored research results (BM25 ranking, no external dependency). |
| `research_start` | Open a research session and either plan it or run it end to end. |
| `research_stats` | Aggregate numbers over the whole research store: sessions by status, total findings and sources, most used tags. |
| `research_status` | Show the state of one research session, or list all sessions with their status. |
| `research_synthesize` | Build a cross-cutting answer from several stored research results. |
| `research_tag` | Manage the tags of a research: add, remove, set or clear. |
| `research_update` | Modify, delete, tag, verify, merge or compare stored research results. |
| `research_verify` | Check every source URL of a stored research and flag findings without a URL. |

### Recent Changelog

## [0.6.9] — 2026-11-19

### 🐛 Live-Debug aller 42 Tools: stille Nullen, Alias-Totpunkt, UnboundLocal

Alle 42 Ops wurden ueber die echte Registrierung aufgerufen
(``scripts/debug_all_tools.py``) und zusaetzlich gegen echtes code_intel
(``scripts/e2e_code_intel_probe.py``). Die Unit-Suite war gruen — diese Bugs
kamen alle als *success mit leeren Feldern* zurueck.

- **Alias-Layer war toter Code.** ``code_symbols`` & Co. wurden nur an 2 von
  ~50 Stellen auf die Namespace-Dispatcher umgeschrieben, und
  ``registry_is_available()`` fragte die lokale Registry — dort steht ein
  Host-Tool nie, das Praedikat war also immer ``False``. Folge:
  ``Unknown tool: code_symbols``, von den Analysis-Tools als 0 Symbole / 0
  Findings ausgegeben. Jetzt zentral in ``Registry.dispatch()`` (deckt
  ``_call_tool``, ``_call_tool_direct`` und direkte Dispatch-Aufrufe ab) plus
  Fallback nach einem ``Unknown tool``; ``shared/tool_alias.py`` prueft die
  echte Host-Registry.
- **``_raw`` wird mitgesendet.** code_intel liefert ohne ``_raw`` ein rich-Panel
  (kein JSON). ``_call_tool`` setzt es jetzt und faellt bei ``TypeError`` je

## [0.6.8] — 2026-11-19

### 🔌 Hint folgt dem echten Bridge-Status

`tools.tool_search.enabled: off` setzt alle Plugin-Tools eager — dann existiert
`tool_call` nicht mehr. Der Intent-Hint hatte den Bridge-Block aber an
`namespaces_enabled()` gekoppelt (das nur die *Namensform* bestimmt) und nannte
weiter `tool_call(...)`: ein toter Tool-Name im Prompt, bei jedem Code-/Bug-
Intent.

- `_tool_search_active()` fragt jetzt `should_activate(load_config_readonly(), …)` —
  der Hint baut den Aufrufblock nur, wenn Hermes die Bridge tatsächlich aktiviert hat.
- Der Cache-Key von `_contexts_for_mode()` enthält beide Dimensionen
  (Namensform + Bridge-Status); ein Umschalten zur Laufzeit lässt keine toten
  Namen stehen.
- Test `test_eager_hints_have_no_bridge_payload` deckt den eager-Fall ab; die
  bestehenden Hint-Tests mocken den Bridge-Status statt ihn zu erben.

## [0.6.7] — 2026-11-18

### 📉 Deferral-Kosten gesenkt: Hints liefern den fertigen Aufruf

Messung vor diesem Release (state.db, 102.695 Tool-Calls): die drei Dispatcher
wurden seit der Fusion **0×** gerufen, die alten Einzel-Tools zuletzt am 16.11.
mit 762 Calls. Ein Hint, der `bughunt(op="scan")` nennt, aber nicht sagt, wie
das deferred Tool erreichbar ist, verweist ins Leere — das Modell weicht auf
`read_file`/`terminal` aus (33.943 bzw. 21.195 Calls).

- **`shared/intent.py`**: Die vier Intent-Contexts (`code`, `bug`, `research`,
  `framework`) tragen im Namespace-Modus eine Präambel mit kopierbarem
  `tool_call({"calls":[{...}]})`-Block samt Beispiel-op. Ein Turn statt drei
  (`tool_search` → `tool_describe` → `tool_call`). Legacy-Modus und die
  MCP-Contexts (`db`, `web`, `debug`) bleiben ohne Präambel — dort sind die
  Tools eager.
- **`shared/usage.py`** (neu): `post_tool_call`-Handler schreibt eine
  JSONL-Zeile pro Scout-Aufruf (`ts`, `plugin`, `tool`, `op`, `session_id`,
  `error`) nach `~/.hermes/logs/plugin-usage.jsonl`. Append-only, wirft nie.
  Ohne diese Zahlen bleibt „wird kaum genutzt" Bauchgefühl.

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
