# Live-Debug der 42 Scout-Ops

Die Unit-Suite laeuft gegen Mocks (`tests/conftest.py`) und bleibt gruen, waehrend
die Tools live leer zurueckkommen. Bug-Klasse: **„✅ success mit leeren Feldern"**.

## 1. Dispatch-Harness (`scripts/debug_all_tools.py`)

```bash
PY=/home/jo/.hermes/tools/python-3.14.9+20261021-linux-x64/bin/python3
cd /home/jo/.hermes/plugins/scout
SCOUT_TIMEOUT=120 $PY scripts/debug_all_tools.py            # alle 42
SCOUT_TIMEOUT=120 $PY scripts/debug_all_tools.py analysis   # eine Domain
```

Aufbau: `shared.tool_registry.collect()` liefert 42 `ToolDef`; der Handler kommt aus
`tool.handler` **oder** `handler_module`/`handler_name` (beide Formen sind im Umlauf).
Pro Op: Fixture-Argumente, `signal.alarm` als Timeout, Status/ms/out_len/preview nach
`/tmp/scout_debug_report.json`.

Status-Klassifikation, die sich bewaehrt hat:

| Status | Bedeutung |
|---|---|
| `ok` | Ausgabe nicht leer |
| `empty` | Rueckgabe leer/whitespace — fast immer ein echter Bug |
| `suspect` | Ausgabe enthaelt `Unknown tool`, `Traceback`, `not supported`, `ModuleNotFoundError` |
| `error` | Exception |
| `timeout` | > `SCOUT_TIMEOUT` |
| `skipped` | Ops mit Seiteneffekt (z. B. `bug_hunt_fix` spawnt Subagent) bewusst ausgelassen |

## 2. Fixture-Argumente

Ziel ist ein echtes kleines Repo — das Plugin selbst funktioniert:
`TARGET=/home/jo/.hermes/plugins/scout` (git-Repo, Python, wenig Dateien).

```python
# analysis
analysis_inspect       {"path": TARGET, "depth": 1, "persist": False}
analysis_architecture  {"path": TARGET, "format": "text", "depth": 1}
analysis_deadcode      {"path": TARGET, "kinds": ["imports"], "max_files": 40}
analysis_security      {"path": TARGET, "persist": False}
analysis_diff_analysis {"path": TARGET, "base": "HEAD~3", "head": "HEAD"}
analysis_review        {"path": TARGET, "base": "HEAD~1", "head": "HEAD"}
analysis_watch         {"action": "list"} → {"action": "create", ...} → {"action": "remove"}

# bughunt (Sequenz, session_id aus start uebernehmen)
bug_hunt_start   {"project": TARGET, "scope": "quick", "focus_areas": ["debug"]}
bug_hunt_finding {"session_id": sid, "title": "Probe", "severity": "P3"}
bug_hunt_scan    {"session_id": sid, "patterns": ["security"], "path": TARGET}
bug_hunt_close   {"session_id": sid, "summary": "Debug beendet"}

# research
research_start {"query": "...", "mode": "plan", "depth": 1, "max_sources": 3}
research_save  {"research_id": rid, "summary": "...", "status": "partial"}
```

`persist=False` bei den Analysis-Ops haelt Honcho aus dem Spiel. `mode="plan"` bei
`research_start` vermeidet Netzcalls.

Fallstricke beim Fixture-Bau:

- `analysis_inspect` liefert einen **JSON-String**, kein dict. Fuer `analysis_diff` /
  `analysis_graph` erst `json.loads`, sonst werden die `report`-Parameter uebersprungen.
- `session_id`/`finding_id`/`research_id` aus der Antwort extrahieren, nicht raten:
  die IDs sind kurz (`b131a687-f2a`, `e524944b`, `2f1845c3`), ein UUID-Regex greift nicht.
- `bug_hunt_pattern(action="list")` vor dem Fix ~69 KB — im Harness Output begrenzen.

## 3. Host-Adapter (`scripts/e2e_code_intel_probe.py`)

Alles, was von code_intel abhaengt, ist im Standalone-Harness wertlos: ohne Host
liefert `registry.dispatch` immer `None` und die Tools schreiben leere
Ersatzstrukturen. Der Probe stellt den Host nach:

```python
# code_intel-Katalog bauen, ohne PluginContext
from code_intel import namespaces as ci_ns
col = Collector()                       # sammelt register_tool(name, toolset, schema, handler)
cat = ci_ns.build_catalog(_register_ast_tools, register_lsp_tools)
for spec in ci_ns.build_tool_specs(cat):
    col.register_tool(spec["name"], spec["name"], spec["schema"], spec["handler"])

class HostAdapter:                      # was ctx.dispatch_tool macht
    def dispatch_tool(self, name, args, **kw):
        entry = self.tools.get(name)
        if entry is None:
            return json.dumps({"error": f"Unknown tool: {name}"})
        return entry["handler"](dict(args or {}), **kw)

reg_mod.hermes_registry = lambda: HostRegistryView(tools)   # kennt nur die 7 Namen
reg_mod.registry.bind_context(HostAdapter(tools))
```

Erwartung nach dem Fix (gemessen gegen `scout/shared`):

```
analysis_inspect        symbols=50
analysis_deadcode       finding-blocks=['unused_imports']
analysis_security       vulnerabilities_found=9
analysis_architecture   sections=3/3 gefuellt
analysis_performance    sections=3/3 gefuellt
Fehler: 0
```

Mit Hermes-Python starten (`/home/jo/.hermes/tools/python-3.14.9.../bin/python3`),
nicht `/usr/bin/python3` — dort fehlen `tree_sitter`, `ruamel` usw.

## 4. Bug-Klassen, die dieser Harness findet

| Symptom | Ursache | Pruefung |
|---|---|---|
| `symbols: 0`, `findings: {}`, Laufzeit 0–1 ms | Dispatch lief ins Leere (`Unknown tool`) | Ergebnis auf `Unknown tool` pruefen, `hermes_has_tool()` testen |
| Felder da, Werte leer | Datenform nicht erkannt (`results[]` statt `symbols[]`) | echte Tool-Antwort mit `json.loads` ansehen |
| `json.loads` scheitert an Box-Zeichen | Rich-Panel statt JSON | `_raw=True` senden |
| `sections_completed: 3` bei 3× `null` | Summary zaehlt Abschnitte, nicht Inhalte | Sections auf Wahrheitswert pruefen, nicht den Zaehler |
| `performance` 5–6 s, `framework` 5–6 s | echter Lauf (Abstieg im Dateibaum) | kein Bug, aber Timeout grosszuegig setzen |
| `status: error` in einem Feld | Handler-Validierung, nicht Dispatch | Feldspezifische Pflichtparameter pruefen |

## 5. Abschluss

- Regressionstests in `tests/test_live_debug_regressions.py` (ein Test pro Bug-Klasse,
  mit dem beobachteten Symptom im Docstring).
- `scripts/gen_tool_registry.py` laufen lassen, wenn sich Schemas geaendert haben —
  `tests/test_registry_drift.py::test_generator_is_idempotent` wird sonst rot.
- Fremdes Plugin mitgeaendert? Dessen Suite separat fahren und pre-existing Failures
  per `git stash push -- <dateien>` → Test → `git stash pop` belegen.
- Nach Aenderungen an `__init__.py`/Handlern greifen sie im laufenden Hermes erst nach
  einem Neustart (bereits importierte Module werden nicht neu geladen).
