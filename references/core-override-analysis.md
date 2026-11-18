# Core-Override in scout: Wirkungsnachweis

`hermes plugins validate scout` meldet seit der Namespace-Fusion:

```
✗ no core override — rebinds Hermes core at runtime: toolsets._HERMES_CORE_TOOLS (__init__.py:68)
⚠ private core imports — __init__.py:56 toolsets
◇ Isolation — in-process only
```

Das ist ein **bewusster Trade-off** (Entscheidung Johannes, 2026-11-18), kein Versehen.

## Warum der Rebind existiert

`tools/tool_search.py::is_deferrable_tool_name()` deferrt jedes Plugin-Tool; nur Namen in
`toolsets._HERMES_CORE_TOOLS` bleiben eager im Tool-Prompt. Eine öffentliche Plugin-API
dafür gibt es nicht (Hermes 0.23.1). Ohne Rebind wären die drei Dispatcher nur über
`tool_search` → `tool_describe` → `tool_call` erreichbar — drei Turns statt einem.

## Was er bringt (gemessen)

| | vorher (42 Einzel-Tools, deferred) | nachher (3 Dispatcher, eager) |
|---|---:|---:|
| Schema-Katalog | 49.751 chars ≈ 12.438 Tok | 17.009 chars ≈ 4.252 Tok |
| Tokens pro Turn | 0 (deferred) | 4.252 |
| Turns pro Nutzung | 2–3 (Bridge) | 1 |
| Echte Nutzungen | 1.714 Calls (state.db) | — |

Rechnung: 19 Nutzungen/Tag × 1 vermiedener Turn × ~45.000 Tok Kontext ≈ 855.000 Tok/Tag
gespart, gegen 4.252 Tok/Turn dauerhaft (~136.000 Tok/Tag bei 40 Turns). Netto deutlich
positiv; Quelle: `references/tool-usage-baseline.md`.

## Warum die Allowlist statt Duldung

`scripts/validate_gate.py` prüft `hermes plugins validate --json` gegen
`references/core_override_allowlist.txt`. Der Eintrag ist begründet; wird der Check
**grün** (z. B. weil Hermes eine Eager-API bekommt), schlägt das Gate als *stale* fehl und
zwingt zum Aufräumen.

## Rückweg

`SCOUT_NAMESPACES=0` registriert wieder alle 42 Tools 1:1 (deferred) — ohne Rebind, ohne
Codeänderung. Für den öffentlichen Katalog wäre das der saubere Modus: `validate` ist dann
vollständig grün (so war es in v0.6.4), kostet aber den Bridge-Turn pro Nutzung.
