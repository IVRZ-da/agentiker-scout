# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |

## Reporting a Vulnerability

Please report security vulnerabilities to **johannes@ivory.green**.

You will receive a response within 48 hours. If the issue is confirmed, a hotfix
will be released as soon as possible, typically within 24 hours.

## Scope

This plugin runs inside Hermes Agent and has access to:
- File system operations via configured tool permissions
- Network access for web research and API calls
- Environment variables and configuration files

Any vulnerability that allows:
- Arbitrary code execution outside tool boundaries
- Unauthorized file system access
- Credential leakage via tool output
- Remote code injection through web research endpoints

...is considered in scope.

## Security Measures

- Pre-commit hooks scan for secrets and tokens before every commit
- All tool registrations are validated at plugin load time
- Bug-hunt patterns include security-focused vulnerability scanning

## `hermes plugins validate` — bekannte False Positives

`hermes plugins validate <dir>` fuehrt den Install-Scanner (`tools.plugin_guard.scan_plugin`)
ueber das **gesamte Verzeichnis** aus, inklusive gitignorierter Laufzeitdaten.
Dadurch meldet der "security scan" scheinbar gefaehrlichen Code:

| Gemeldete Datei | Was es wirklich ist |
| --------------- | ------------------- |
| `data/patterns/**/*.yaml` (owasp, top100, eslint) | Bug-Hunt-**Pattern-Definitionen**: Regex-Strings wie `os.system` oder `subprocess.run`, die als Suchmuster dienen - kein ausfuehrbarer Code |
| `bughunt/data/sessions/*.json` | gespeicherte Scan-Ergebnisse (Fundstellen aus fremden Repos) |
| `data/cwe_categories.json` | statische CWE-Kategorien |

Nachgemessen: derselbe Scanner auf einem **clean clone** (`git archive HEAD`)
liefert `verdict: safe` und **0** Findings der Stufe critical/high.

Konsequenz fuer CI/Admission:

```bash
rm -rf /tmp/scout-stage && mkdir -p /tmp/scout-stage
git archive HEAD | tar -x -C /tmp/scout-stage
hermes plugins validate /tmp/scout-stage
```

Bekannte Einschraenkung: Laufzeitdaten liegen weiterhin im Plugin-Verzeichnis
(`data/`, `bughunt/data/`). Solange das so ist, ist `validate` nur auf einem
sauberen Stand aussagekraeftig. Ein Auslagern der Daten (z. B. nach
`~/.hermes/plugin-data/agentiker-scout/`) ist als eigene Aufgabe vorgemerkt.
