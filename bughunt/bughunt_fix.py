"""Bug-Hunt Auto-Fix — generiert Subagent-Prompts für die automatische Fehlerbehebung.

Architektur:
1. bug_hunt_fix() lädt Finding + Pattern, generiert fix_prompt
2. Der Agent ruft delegate_task(goal=fix_prompt) auf
3. Der Subagent fixt den Code und verifiziert

Das Plugin ruft NICHT direkt delegate_task auf (nicht im Plugin-Kontext verfügbar).
"""
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def build_fix_prompt(finding: dict, pattern: Optional[dict] = None) -> str:
    """Build a delegate_task prompt for auto-fixing a bug finding.

    Args:
        finding: Finding dict (title, file, line, severity, evidence, etc.)
        pattern: Optional BugPattern dict (fix_description, scan_type, etc.)

    Returns:
        A self-contained prompt for delegate_task().
    """
    title = finding.get("title", "Unknown Bug")
    file_path = finding.get("file", "")
    line = finding.get("line", 0)
    evidence = finding.get("evidence", "")
    description = finding.get("description", "")
    pattern_id = finding.get("pattern_id", "")
    suggested_fix = finding.get("suggested_fix", "")
    severity = finding.get("severity", "P2")

    # Pattern details
    fix_description = ""
    scan_query = ""
    scan_file_glob = ""
    if pattern:
        fix_description = pattern.get("fix_description", "")
        scan_query = pattern.get("scan_query", "")
        scan_file_glob = pattern.get("scan_file_glob", "")

    # Use suggested_fix from finding or fix_description from pattern
    fix_instruction = suggested_fix or fix_description or "Manuell prüfen und fixen"

    # Build language-specific verification
    if file_path.endswith(".py"):
        verify_cmd = f"python3 -c \"compile(open('{file_path}').read(), '{file_path}', 'exec')\""
    elif file_path.endswith((".ts", ".tsx")):
        verify_cmd = "npx tsc --noEmit --pretty 2>&1 | head -20"
    else:
        verify_cmd = "Prüfe die Änderung manuell"

    prompt = f"""## Auto-Fix Task: {title}

### Finding
- **Severity:** {severity}
- **Pattern:** {pattern_id}
- **File:** {file_path}:{line}
- **Description:** {description}

### Evidence (aktueller Code Context)
```
{evidence[:500]}
```

### Fix-Anleitung
{fix_instruction}

### Scan-Informationen
- Scan-Typ: {pattern.get('scan_type', 'code_search') if pattern else 'code_search'}
- Such-Query: {scan_query}
- Datei-Glob: {scan_file_glob}

### Aufgabe
1. **Lokalisieren** — Öffne {file_path} und finde die betroffene Stelle um Zeile {line}
2. **Fix anwenden** — Wende den Fix gemäss der Fix-Anleitung an
3. **Verifizieren** — Führe aus: {verify_cmd}
4. **Bericht** — Teile mir mit ob der Fix erfolgreich war oder ob es Probleme gab

### Wichtige Hinweise
- Nur die betroffene Datei editieren, keine anderen Dateien verändern
- Nach dem Fix: Syntax-Prüfung durchführen
- Bei Unsicherheit: Schritt für Schritt vorgehen
- **Optional:** Nutze `analysis_review` nach dem Fix um den geänderten Code zu reviewen
  (analysis_review vergleicht main vs HEAD und zeigt Security/Complexity-Delta)
"""
    return prompt


def _ok(data: dict) -> str:
    """Success response — JSON-String für Tool-Output."""
    data.setdefault("status", "ok")
    return json.dumps(data, ensure_ascii=False)


def _err(msg: str) -> str:
    """Error response."""
    return json.dumps({"error": msg, "status": "error"}, ensure_ascii=False)
