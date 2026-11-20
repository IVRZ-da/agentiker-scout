---
name: agentiker-scout
description: "Bug-Hunt mit Scout: Scan-Presets, Triage, Fix-Pipeline."
version: 0.6.2
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

## Tools (3 Dispatcher, 42 Ops)

Seit v0.6.5 sind die 50 Einzel-Tools zu **drei Namespace-Dispatchern** fusioniert
(Analogie zu code_intel v0.6.25). Jeder Dispatcher nimmt `op` plus die Parameter des
gewählten Ops. **Ob du sie direkt aufrufst oder über `tool_call`, entscheidet nicht das
Plugin, sondern `tools.tool_search.enabled` in der config:** `off` = alle Plugin-Tools
liegen eager im Set und werden direkt aufgerufen (`tool_call` existiert dann gar nicht),
`auto`/`on` = deferred über die Bridge. Nie aus dem Plugin-Zustand auf die Aufrufart
schliessen — erst den Schalter nachsehen, sonst stehen `tool_call`-Beispiele in einer
Session, in der es das Tool nicht gibt (und umgekehrt).

| Dispatcher | Ops | Aufgabe |
|---|---:|---|
| `analysis` | 20 | Code- & Architektur-Analyse |
| `bughunt` | 13 | Vulnerability-Scanning, Findings, Fixes |
| `research` | 9 | Web-Recherche + Honcho-Synthese |

```python
analysis(op="inspect", path="/srv/app", depth=3)
bughunt(op="start", project="/srv/app")
bughunt(op="scan", patterns=["medusa"], preset="medusa-full")
research(op="start", query="...", depth=3)
```

Die alten Namen (`analysis_inspect`, `bug_hunt_scan`, …) funktionieren weiter als
`op`-Wert — nicht mehr als eigener Tool-Name. `SCOUT_NAMESPACES=0` stellt die
1:1-Registrierung aller 42 Tools wieder her (deferred, ohne Core-Rebind).

**Scan-Typen (op=`scan`):** grep, code_security_scan, code_search_by_error, code_todo_finder, code_duplicates, code_merge_conflict, code_search, code_diagnostics

**Patterns:** 67 Built-in (43→67: +5 Security, +6 Code-Quality, +5 Java, +5 C/C++, +3 Ruby;
zwei Severity-Buckets ohne eigene Regel entfallen)

### 🔴 Bug-Hunt-Session: Nutzungsregeln (sonst unbrauchbarer Report)

- **`bug_hunt_scan(path=…)` zeigt auf das Projekt, wie es ist.** Fremdcode und
  Build-Ausgaben sind seit 0.6.1 ausgeschlossen (`shared/scan_paths.py`:
  `node_modules`, `dist`, `.venv`, `.git`, Lockfiles, `*.min.js`); der Scan über
  die Projektwurzel ist damit in Ordnung. Eigene Ausschlüsse ergänzen:
  `SCOUT_SCAN_EXCLUDES=generated,fixtures`. Wenn ein Projekt bewusst in `build/`
  sucht, dort eine zweite Session mit eigenem `path` starten.
- **Die Security-Patterns (S020–S024, J00x, CPP00x, RB00x) laufen in Scout
  selbst** (`scan_type=regex`, Regelsatz wie code_intel `code_security_scan`).
  S025/S026 („CRITICAL/HIGH Vulnerability") gibt es nicht mehr — das waren nur
  Severity-Buckets ohne eigene Regel. Ein Lauf mit „0 kritisch" ist trotzdem kein
  Beweis: Semgrep (`p/typescript p/nodejs p/secrets p/owasp-top-ten`) und eigene
  Tiefenanalyse parallel fahren.
- **Auto-Treffer vor dem Report gegen den Fremdcode prüfen** und Falschtreffer
  per `bug_hunt_triage(status="false_positive", notes=<Stelle im Fremdcode, die
  den Treffer entkräftet>)` schließen. Ein P0, den das SDK selbst abfängt
  (z. B. validierte `redirect_uri`), kostet sonst das Vertrauen in den ganzen
  Report.
- **`bug_hunt_list` ist gekürzt** (`findings_truncated`). Bei vielen Treffern
  zuerst filtern (`severity`, `file`, `status`) oder die Noise-Quelle per
  eigenem `path` ausschließen, statt sich auf die angezeigte Liste zu verlassen.
- **Findings sofort mit `bug_hunt_finding` festhalten** (Severity, `file`,
  `line`, `evidence` als echter Code/Befehl, `suggested_fix`). Sammeln und am
  Ende schreiben verliert die Belege bei Kontextkompression. Mehrere Findings
  gehören in EINEN `tool_call`-Block (ein Call pro Finding) — nicht in N Runden.
- **Ein Bug-Hunt beginnt immer mit `bug_hunt_start`.** Auch wenn die Aufgabe
  „nur" ein fremdes Repo betrifft und du sofort lesen könntest: erst Session
  öffnen, `bug_hunt_scan` laufen lassen, dann Tiefenanalyse. Ein manueller Hunt
  ohne Session produziert keinen exportierbaren Report und keine
  Pattern-Lernschleife — der Nutzer erwartet das Plugin im Einsatz, nicht
  daneben.
- **Subagent-/Delegations-Findings sind Behauptungen, keine Belege.** Vor dem
  Eintrag in den Report die zitierte Zeile selbst lesen. Zwei typische
  Fehlklassen: (a) Severity inflationär, weil die Vorbedingung fehlt (ein
  „P0 beliebiger lokaler Dateizugriff" ist P2, wenn der Codepfad nur im
  stdio-Modus existiert); (b) schlichtweg falsch, weil der Prüfcode eine Ebene
  tiefer liegt („confirm ist nicht an die Vorschau gebunden" — obwohl die
  Service-Methode die `confirmedIds` exakt gegen die Filterauswahl prüft).
  Verworfene Kandidaten mit Begründung in den Report aufnehmen, sonst jagt die
  nächste Session denselben Geist.
- **Severity kalibrieren, nicht erben:** P0 = Sicherheitslücke/Datenverlust
  ohne Vorbedingung, P1 = falsches Verhalten mit realer
  Eintrittswahrscheinlichkeit, P2 = Randfall/umgebungsabhängig, P3 = Härtung.
  „Nur im stdio-Modus erreichbar", „setzt fehlerhafte Konfiguration voraus"
  und „durch SDK abgefangen" sind Severity-Senker, die im Finding-Text stehen
  müssen.
- **Behauptungen dynamisch nachweisen, statt sie zu behaupten.** Für
  TS/JS-Repos: kleines Probe-Skript gegen die echten Module (`npx tsx`), siehe
  [references/bughunt-dynamic-probes.md](references/bughunt-dynamic-probes.md).
  Ein per Probe belegtes Finding („falsches Passwort → `verifyPassword` gibt
  `true`") trägt den Report; ein nur gelesenes nicht.
- **Verifikation in einem Rutsch abschließen:** alle geprüften IDs mit
  `bug_hunt_triage(finding_ids=[…], status="verified", notes="…")` in EINEM
  Call markieren — nicht 17 einzelne `bug_hunt_verify`-Aufrufe.

### 🔴 Nach dem Hunt: Fix-Runde (Report → Plan → grüne Suite)

Der Hunt ist die halbe Arbeit; die Fix-Runde hat eigene Fallen:

- **Ein Task pro Datei, nicht pro Finding.** Fünf P1/P2 im selben Modul gehören in
  EINEN Task (ein Verify-Lauf statt fünf), Reihenfolge P1 → P2 → P3, linear
  `depends_on` — ein Agent, keine Parallelität auf derselben Datei.
- **Verify = Typecheck && volle Suite**, als reine `&&`-Kette, nie mit Pipe auf
  `tail` und nie mit `exit $?`-Mask. Monolithische Test-Skripte haben keinen
  Filter — die volle Suite pro Task ist billiger als ein falsch-grüner Task.
- **Retrybare Status im Mock belegen nichts.** Ein `failNext` mit 503/429 wird
  vom Wiederhol-Loop des Clients verbraucht, der zweite Versuch gelingt, der Test
  ist grün ohne den Pfad zu prüfen. „Dauerhaft kaputt" = nicht-wiederholbarer
  Status (403); „Änderung kam an, meldete aber Fehler" = eigener Hook, der erst
  schreibt und dann 503 antwortet.
- **Fault-Injection braucht einen kalten Cache.** Ein injizierter Fehler wird nie
  verbraucht, wenn ein Produktions-Cache (Label-, Namens-, ETag-, Plan-Cache) die
  Antwort schon hält — der Test belegt dann den Cache, nicht den Fehlerpfad. Zwei
  Auswege: frische Entität (neue ID/neuer Plan, damit der Cache-Key kalt ist) oder
  die Service-Klasse direkt mit eigenem Client instanziieren
  (`new UserDirectory(new GraphClient(...))`) — deren Cache ist leer und der Test
  ist billiger als der MCP-Roundtrip. Und: der Fault-Key muss der Key-Bauart des
  Test-Doubles entsprechen (oft `METHOD + pathname`, ohne Query und ohne
  API-Präfix) — vorher die Key-Zeile im Mock lesen, sonst greift der Fault still
  nicht.
- **Paritäts-Checks mitpflegen.** Projekte prüfen automatisch README-Tabellen
  gegen registrierte Schemas und `.env.example` gegen die Env-Schema-Keys. Ein
  neues Feld oder eine neue Variable macht diese Prüfungen rot, obwohl der Fix
  stimmt — Schema + `.env.example` + README-Tabelle gehören in denselben Task.
- **Verhaltensändernde Sicherheitsfixes ankündigen.** `confirm`-Gates und
  Datei-Allowlists brechen bestehende Tests und Erwartungen: Default sicher
  wählen, Fehlermeldung nennt die Variable zum Freischalten, betroffenen Test
  auf das neue Verhalten umschreiben, dem Nutzer die Änderung am Ende nennen.

→ Ablauf, Test-Rezepte (Timeout, Body-Limit 413, Apply-then-Fail) und
Abschlussbericht: [references/hunt-to-fix-round.md](references/hunt-to-fix-round.md)

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
| Bug-Hunt automatisieren | `bug_hunt_scan` mit Pattern-IDs | `grep`+`regex` + manuelle Findings | 67 Built-in Patterns, auto-categorize |
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
  eindeutige IDs und gueltige Severities. Alle 67 Patterns haben Notes.
- **Jede Regel braucht einen Positiv-Test, sonst ist "kein Treffer" nicht von
  "Regel kaputt" zu unterscheiden.** Fuer `scan_type=regex` je eine Fixture-Datei
  mit gepflanzter Luecke (`~/.hermes/cache/scratch/vuln-fixture/`) und im Test
  behaupten, dass die Regel dort trifft — plus ein Negativ-Fall, damit die Regel
  nicht einfach alles matcht. Grund: eine Regel mit kaputtem Quoting liefert still
  0 Treffer und sieht im Report wie ein sauberes Projekt aus.
- **Regeln nicht auf nackte Property-/Methodennamen stuetzen.** `params.`,
  `query.`, `body.`, `exec(`, `open(`, `join(` treffen auch `regexp.exec(...)`,
  `Signer.open(...)` und `path.join(...)` — im TypeScript-Alltag zwei Falschtreffer
  pro Datei. Input-Belege qualifizieren (`req.params`, `request.args`, `ctx.body`),
  Shell-/Dateifunktionen mit Zusatzbedingung (`+ var`, `${`, `shell=True`).
  Reichweite lieber eine Ebene enger als Severity-Buckets ohne eigene Regel
  (S025/S026).

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

Drei Fallen beim Aufruf fremder Plugins:

- **Legacy-Namen gehoeren zentral in `Registry.dispatch()`, nicht an die Aufrufstellen.**
  code_intel (ab 0.6.25) registriert nur noch 7 Namespace-Dispatcher; `code_symbols`
  usw. laufen in `Unknown tool`. Ein Alias-Layer, den nur einzelne Aufrufer benutzen,
  ist wirkungslos: er existierte, hing aber an 2 von ~50 Stellen — der Rest lieferte
  `Unknown tool: code_symbols` und die Analysis-Tools gaben still leere Listen zurueck
  („✅ success" mit `symbols: 0`). `dispatch()` muss deshalb selbst aufloesen:
  Namen direkt probieren, bei aktivierten Namespaces auf `<dispatcher>` + `op`
  umschreiben und nach einer `Unknown tool`-Antwort in die Gegenrichtung wiederholen.
- **Das Verfuegbarkeits-Praedikat muss die Host-Registry fragen.**
  `registry.get_entry()` kennt nur plugin-interne Handler; fuer ein Host-Tool wie
  `code_search` liefert es immer `False` — dann schreibt `resolve_tool_call()` nie um.
  Richtig ist `tools.registry.registry.get_entry(name)` (ohne expliziten Scope sucht sie
  im aktuellen) **oder** die lokale Registry (`hermes_has_tool()`), nie nur letztere.
- **`Unknown tool` kommt als String zurueck, nicht als Exception.** Jede
  `except Exception: logger.debug(...)`-Kette schluckt ihn, und der Aufrufer sieht ein
  leeres Ergebnis statt eines Fehlers. Nach einem Dispatch fremder Tools das Ergebnis
  auf das Muster pruefen, bevor es als Daten weiterverarbeitet wird.

### code_intel-Ergebnisse maschinell lesen

- **`_raw=True` gibt JSON statt Rich-Panel.** Implementiert in `code_symbols_tool`,
  `code_diagnostics_tool`, `code_references_tool`, `code_tests_for_symbol_tool` — die
  `_handle_*`-Wrapper muessen den Parameter durchreichen. Taten sie nicht: der
  `_raw`-Vertrag endete eine Ebene zu frueh, `json.loads` scheiterte am Panel-Text und
  die Daten gingen verloren, nicht die Formatierung. `_call_tool` setzt `_raw` deshalb
  selbst und wiederholt ohne den Parameter, wenn ein Tool ihn nicht kennt.
- **Ein Ergebnis in 0–1 ms mit `status: ok` und leeren Feldern ist ein Fehler, kein
  schneller Lauf.** Echte Analyse kostet Millisekunden bis Sekunden; die Laufzeit ist
  das billigste Signal fuer „Backend nicht erreichbar / Dispatch ins Leere".
- Weitere code_intel-Fallen (Panel-Format, fehlende Grammatiken, doppelte
  Handler-Definitionen): Skill `agentiker-code-intel`.

## Live-Debug aller Ops (nach jeder Aenderung an Dispatch oder Tool-Daten)

`pytest` bleibt gruen, weil die Suite gegen Mocks laeuft. Die Fehler sitzen im
Dispatch-Pfad und in der Datenform — die findet nur ein Aufruf ueber die echte
Registrierung:

1. `scripts/debug_all_tools.py` ruft jeden der 42 Ops mit Fixture-Argumenten ueber
   `shared.tool_registry.collect()` auf und schreibt Status, Laufzeit, Ausgabegroesse
   und Vorschau nach `/tmp/scout_debug_report.json`. `SCOUT_TIMEOUT` begrenzt einzelne
   Ops, `analysis|bughunt|research` als Argument filtert auf eine Domain.
2. `scripts/e2e_code_intel_probe.py` stellt den Hermes-Host nach
   (`HostAdapter.dispatch_tool` + `HostRegistryView.get_entry`, dann
   `registry.bind_context(host)`) und laesst die Analysis-Handler gegen echten
   code_intel-Code laufen. Erwartung: Symbole > 0, Security-Findings > 0,
   Architecture-/Performance-Sections gefuellt. Laeuft mit dem Hermes-Python, nicht
   mit `/usr/bin/python3` (dort fehlen die Host-Module).
3. Sequenz-Ops in Kette testen (`start → finding → list → triage → verify → report →
   export → close` bzw. `research: start → save → update → status → search → stats →
   export → synthesize → cleanup`). Einzelaufrufe mit erfundener `session_id` belegen
   nur die Validierung, nicht den Pfad.
4. Jeder Fund bekommt einen Regressionstest in `tests/test_live_debug_regressions.py`.
   Die Bug-Klasse ist „✅ success mit leeren Feldern" — genau die faengt kein
   bestehender Test. Schema-Drift separat: `tests/test_registry_drift.py`
   (nach Schema-Aenderungen `scripts/gen_tool_registry.py` laufen lassen, sonst rot).
5. Fremde Plugin-Aenderungen (z. B. `_raw`-Durchreichung in code_intel) in der
   eigenen Suite nicht mitpruefen — dort laufen lassen und pre-existing Failures mit
   `git stash push -- <dateien>` → Test → `git stash pop` belegen, statt sie dem
   eigenen Fix anzulasten.

- **`collect()` liefert `ToolDef`s, deren `.handler` bei den JSON-dominierten Domaenen
  (bughunt, research) `None` ist** — dort steht die Registrierung in `handler_module` /
  `handler_name`. Ein Harness, der nur `tool.handler` nimmt, meldet fuer jeden dieser Ops
  "Handler nicht gefunden" und sieht wie ein Tool-Bug aus. Aufloesen mit
  `tool.handler or getattr(importlib.import_module(tool.handler_module), tool.handler_name)`.

Fixture-Argumente pro Op, die Bug-Klassen und das Host-Adapter-Muster:
[references/live-debug-ops.md](references/live-debug-ops.md)
