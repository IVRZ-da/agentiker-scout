# Tool-Nutzung scout — Messung vor der Fusion-Entscheidung (T9)

Messbasis: `~/.hermes/state.db` (SQLite), Tabelle `messages`, Stand 2026-11-18.
Zählung über `tool_name` (direkte Calls). Bridge-Aufrufe (`tool_call`) sind mitgezählt,
sofern der Tool-Name in den Argumenten steht — die Spalte `sessions.tool_names` ist in
dieser Installation leer und wurde nicht verwendet.

Gesamt: **98.292 Tool-Calls** in 1.532 Sessions. Davon **1.714 scout-Tools = 1,7 %**.

## Nutzung pro Tool (Top 20)

| Tool | Calls |
|---|---:|
| bug_hunt_finding | 762 |
| bug_hunt_scan | 95 |
| bug_hunt_start | 91 |
| analysis_inspect | 90 |
| bug_hunt_triage | 81 |
| analysis_architecture | 61 |
| bug_hunt_close | 57 |
| analysis_deadcode | 54 |
| bug_hunt_stats | 49 |
| bug_hunt_report | 43 |
| analysis_security | 37 |
| analysis_framework | 35 |
| bug_hunt_fix | 32 |
| analysis_diff | 29 |
| analysis_performance | 26 |
| bug_hunt_pattern | 22 |
| analysis_risk | 20 |
| analysis_ui_gap | 16 |
| research_start | 15 |
| research_save | 12 |

## Entscheidungsregel

- **Deferral** kostet 0 Schema-Tokens pro Turn, aber pro Nutzung 1–2 Extra-Turns
  (`tool_describe` → `tool_call`). Jeder Extra-Turn sendet den vollen Kontext erneut.
- **Fusion + eager** kostet die Dispatcher-Schemata in **jedem** Turn, dafür entfällt
  der Bridge-Umweg.

Rechnung mit gemessenen Werten:

```
1.714 Nutzungen / ~90 Tage   ≈ 19 Nutzungen pro Tag
                             ≈ 1 Nutzung pro 3–5 Agenten-Turns an aktiven Tagen
Extra-Turn pro Nutzung        = 1 (tool_call, Schema liegt nach tool_describe vor)
Eager-Kosten 3 Dispatcher     = 17.009 Zeichen ≈ 4.252 Tokens pro Turn (gemessen)
```

Bei 1 Nutzung pro 3–5 Turns ist der Bridge-Umweg teurer als 4.252 Tokens dauerhaft:
jeder vermiedene Extra-Turn spart einen kompletten Kontext-Durchlauf.

**Fusion: ja** — 42 Tools → 3 Namespace-Dispatcher (`analysis`, `bughunt`, `research`),
Katalog per Replay der echten Registrierung, Legacy-Schalter `SCOUT_NAMESPACES=0`.

Einschränkung: `bug_hunt_finding` (762 Calls) allein rechtfertigt die Fusion; die
Research-Tools (research_*: 39 Calls) sind Grenzfall — sie bleiben trotzdem im
`research`-Dispatcher, weil ein einzelner Dispatcher billiger ist als drei Schemata.

## Gegenprobe: was die Fusion NICHT ändert

Die Parameter-Union je Namespace wächst mit der Zahl der Ops. Bei scout sind die Ops
innerhalb einer Gruppe ähnlich (`analysis_inspect(path, depth)`, `analysis_security(path)`),
deshalb bleibt die Union nahe am größten Einzelschema — anders als bei `plan_create`
(Sequenz-Protokoll), wo die Fusion verworfen wurde.
