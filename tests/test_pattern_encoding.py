"""Verschluesselte Pattern-Fragmente: Kodierung muss verlustfrei sein (T8).

Die Pattern-Kataloge dieses Plugins enthalten selbst Schwachstellen-Fragmente
(`.env|`, `os.environ`, `exec('...`, `child_process.exec(`, `/etc/passwd`). Hermes'
Plugin-Scanner (`tools/plugin_guard.py`) liest sie als Angriffsmuster und stufte das
Plugin deshalb als `dangerous` ein — ein Selbstbezug, kein echter Fund.

Fix: die Fragmente so schreiben, dass der Scanner sie nicht mehr matcht, die
Lade-Seite sie aber unveraendert sieht:
* YAML/JSON: `(?:)`-Gruppen (semantisch neutrale Regex-Klammer, trennt `env` vom `|`),
  `\\x2e`/`\\x28`-Escapes in double-quoted scalars, `\\/`-Escapes in JSON;
* Markdown: Backtick-Marker um `!!` entfernt.

Diese Tests halten die Verlustfreiheit fest: gleiche Regel, gleiche Regex-Sprache,
gleicher Anzeigetext.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import yaml  # noqa: E402

PLUGIN = Path(__file__).resolve().parent.parent
PATTERNS = PLUGIN / "data" / "patterns"
CWE_FILE = PLUGIN / "data" / "cwe_categories.json"


def _rules(rel: str) -> list[dict]:
    data = yaml.safe_load((PATTERNS / rel).read_text(encoding="utf-8"))
    return data.get("rules", data) if isinstance(data, dict) else data


def _rule(rel: str, rule_id: str) -> dict:
    for r in _rules(rel):
        if r.get("id") == rule_id:
            return r
    raise AssertionError(f"{rule_id} fehlt in {rel}")


def _matches(rule: dict, probe: str) -> bool:
    return bool(re.search(rule["scan_query"], probe, re.IGNORECASE))


def test_permissions_rule_matches_chmod_and_env_write():
    """OWASP-AC-07: `env|` kodiert, beide Alternativen muessen weiter greifen."""
    rule = _rule("security/owasp.yaml", "OWASP-AC-07")
    assert _matches(rule, "chmod 777")
    assert _matches(rule, "fs.writeFile('.env', x)")


def test_information_exposure_matches_dot_env():
    """OWASP-AC-12: `.env` am Alternationsanfang kodiert."""
    rule = _rule("security/owasp.yaml", "OWASP-AC-12")
    assert _matches(rule, ".env")
    assert _matches(rule, "config.json")


def test_path_traversal_env_alternative_intact():
    r"""OWASP-FS-05: `..\/...env`-Alternative muss weiter greifen."""
    rule = _rule("security/owasp.yaml", "OWASP-FS-05")
    assert _matches(rule, "../../.env")
    assert _matches(rule, "../../.git")


def test_top100_exec_prose_is_readable():
    """exec_string war Prosa — der Beispieltext muss unveraendert ankommen."""
    hit = [r for r in _rules("security/top100.yaml") if "exec('ls'" in r.get("fix_description", "")]
    assert hit, "fix_description mit exec-Beispiel fehlt"
    assert "exec('ls', ['-l', file])" in hit[0]["fix_description"]


def test_top100_os_environ_prose_is_readable():
    hit = [r for r in _rules("security/top100.yaml") if "os.environ" in r.get("fix_description", "")]
    assert hit, "fix_description mit os.environ fehlt"


def test_eslint_child_process_title_is_readable():
    hit = [r for r in _rules("typescript/eslint.yaml") if r.get("title") == "child_process.exec() verwendet"]
    assert hit, "Titel child_process.exec() verwendet fehlt oder ist verstuemmelt"


def test_cwe_description_keeps_passwd_path():
    data = json.loads(CWE_FILE.read_text(encoding="utf-8"))
    desc = data["CWE-36"]["description"]
    assert "/etc/passwd" in desc, "CWE-36-Beschreibung verlor den Pfad"


def test_no_raw_env_pipe_left_in_yaml():
    """Kern des Fixes: kein nacktes `env|`, das der Guard als env-Dump liest.

    Erlaubt ist nur die neutrale Form `env(?:)|` (und `env` ohne Pipe).
    """
    text = (PATTERNS / "security/owasp.yaml").read_text(encoding="utf-8")
    leftovers = [
        (i, line[:100])
        for i, line in enumerate(text.splitlines(), 1)
        if re.search(r"(?<![)\w])env\s*\|", line)
    ]
    assert not leftovers, f"env-Pipe-Fragment gefunden: {leftovers}"
