# Contributing to agentiker-scout

## Branch-Strategie

- **`main`** — stabil, geschützt. Nur via Pull-Request.

## Workflow

1. Branch von `main` erstellen (siehe `BRANCHING.md`)
2. Änderungen committen
3. Pre-Commit Hook aktivieren: `git config core.hooksPath .githooks`
4. Lokal testen:

   ```bash
   ruff check . --select F,E,T,W,I
   python3 -m pytest tests/ -q --tb=short
   ```

5. `CHANGELOG.md` aktualisieren
6. PR auf `main` stellen
7. Review durch Maintainer → Merge in `main`

## Was wir erwarten

| Check        | MUSS | Erklärung                                  |
|--------------|------|--------------------------------------------|
| Ruff Lint    | ✅   | `ruff check --select F,E,T,W,I tests/ src/`|
| Tests        | ✅   | `pytest tests/ -q`                         |
| CHANGELOG    | ✅   | Neuen Eintrag unter `[Unreleased]`         |
| Keine Secrets| ✅   | Pre-Commit Hook prüft automatisch          |

## Was wir NICHT wollen

- Commits mit persönlichen Daten (Email, System-Pfade)
- Direkte Pushs auf `main` (blocked durch Branch-Protection)
- PRs ohne CHANGELOG-Eintrag

## Security

Bei Sicherheitslücken: **Kein öffentliches Issue.** Direkt an den Maintainer wenden.
