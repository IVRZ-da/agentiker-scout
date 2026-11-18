# Core-Override in scout: Entscheidung und Rückweg

## Stand: Rebind entfernt (Variante C, 2026-11-18)

`hermes plugins validate scout` ist **vollständig grün**. Der frühere Rebind von
`toolsets._HERMES_CORE_TOOLS` (Katalog-Regel 9: keine Runtime-Overrides von
Hermes-Core) ist ersatzlos entfernt. Die drei Dispatcher sind damit **deferred**:
jeder Aufruf läuft über `tool_call([{name, arguments}])`.

## Warum der Rebind überhaupt existierte

`tools/tool_search.py::is_deferrable_tool_name()` deferrt jedes Plugin-Tool; nur
Namen in `toolsets._HERMES_CORE_TOOLS` oder Tools aus `_DIRECT_SURFACE_TOOLSETS`
bleiben eager. Eine öffentliche Plugin-API dafür gibt es nicht — geprüft in
Hermes 0.23.1 und auf Upstream-`main`:

* `ctx.register_tool(...)` hat keinen `eager`/`defer`-Parameter.
* `plugin.yaml` kennt kein solches Feld (`_KNOWN_MANIFEST_FIELDS`).
* Nur `tools.tool_search.defer: []` (Nutzer-Config) macht alles eager — global,
  verwirft die Token-Ersparnis von Tool Search.

## Was der Rebind gekostet hätte / was der Verzicht kostet (gemessen)

| | 42 Einzel-Tools (deferred) | 3 Dispatcher eager (alt) | 3 Dispatcher deferred (jetzt) |
|---|---:|---:|---:|
| Schema-Katalog | 49.751 chars ≈ 12.438 Tok | 17.009 chars ≈ 4.252 Tok | 17.009 chars ≈ 4.252 Tok |
| Tokens pro Turn | 0 | 4.252 | 0 |
| Turns pro Nutzung | 2–3 (Bridge) | 1 | 2 (`tool_call`) |

Der Verzicht kostet einen zusätzlichen Turn pro Nutzung. Gemessene Basis: 1.714
echte Calls in ~90 Tagen ≈ 19/Tag ≈ 1 Nutzung pro 3–5 Agenten-Turns an aktiven
Tagen (`references/tool-usage-baseline.md`). Anders als bei plan_follow (dort
werden `plan_current`/`plan_complete` **pro Task** gerufen) ist die Analyse-/
Bughunt-Nutzung stoßweise — der Bridge-Turn fällt selten an, die 4.252
Schema-Tokens fielen in jeden Turn.

## Warum nicht einfach `SCOUT_NAMESPACES=0`

Der Legacy-Modus registriert 42 Einzel-Tools 1:1 deferred — gleiche Bridge-Kosten,
aber 42 statt 3 Katalogeinträge und keine `op`-Fehlerqualität. Kein Vorteil.

## Rückweg, falls Hermes einen Eager-Seam bekommt

Upstream-Issue ist offen (eager-Seam für Plugin-Tools). Sobald ein offizieller
Weg existiert (`register_tool(..., eager=True)` oder `plugin.yaml: eager_tools`),
gilt:

1. `EAGER_TOOLS = ("analysis", "bughunt", "research")` in `__init__.py` setzen.
2. `_mark_tools_eager()` durch den offiziellen Aufruf ersetzen — **kein** Rebind
   auf Core-Attribute (der Regressionstest
   `test_plugin_never_writes_core_attributes` hält das).
3. `hermes plugins validate` muss grün bleiben; die Allowlist bleibt leer.

## Gate-Verlauf

`scripts/validate_gate.py` prüfte `hermes plugins validate --json` gegen
`references/core_override_allowlist.txt`. Der frühere Eintrag
(`no core override: bewusst …`) ist entfallen, weil der Check grün geworden ist —
genau der *stale*-Fall, den das Gate erzwingt. Die Allowlist ist jetzt leer.
