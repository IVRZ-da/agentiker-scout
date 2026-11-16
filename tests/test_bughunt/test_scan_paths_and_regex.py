"""Tests für die Scan-Pfad-Ausschlüsse und den Python-Regex-Scanner.

Hintergrund: der Pattern-Scan lief über die gesamte Projektwurzel, inklusive
``node_modules``. Beim Bug-Hunt in einem Node-Projekt kamen 41 von 41 Treffern
aus ``node_modules/@types/node`` — Fremdcode als Rauschen im Report. Die 19
Security-Patterns mit ``scan_type=code_security_scan`` lieferten gleichzeitig
gar nichts, weil sie auf ein code_intel-Tool zeigten, dessen Ausgabe ein
Rich-Panel ist. Beides ist hier abgesichert.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scout.shared.regex_scan import compile_flags, regex_batch
from scout.shared.scan_paths import (
    build_exclude_flags,
    file_patterns,
    is_excluded_dir,
    is_excluded_file,
    iter_source_files,
)

# ═══════════════════════════════════════════════════════════════════════
# scan_paths
# ═══════════════════════════════════════════════════════════════════════

class TestExcludes:
    def test_node_modules_ist_ausgeschlossen(self):
        assert is_excluded_dir("node_modules")
        assert is_excluded_dir("dist")
        assert is_excluded_dir(".git")
        assert is_excluded_dir(".venv")

    def test_quellverzeichnisse_bleiben_drin(self):
        # docs/ und examples/ enthalten echten Code und dürfen nicht verschwinden.
        assert not is_excluded_dir("src")
        assert not is_excluded_dir("docs")
        assert not is_excluded_dir("examples")

    def test_lockfiles_und_minifiziertes_ausgeschlossen(self):
        assert is_excluded_file("package-lock.json")
        assert is_excluded_file("app.min.js")
        assert not is_excluded_file("app.js")

    def test_grep_flags_enthalten_exclude_dir(self):
        flags = build_exclude_flags()
        assert "--exclude-dir" in flags
        assert "node_modules" in flags
        # Jedes Verzeichnis braucht sein eigenes Flag.
        assert flags.count("--exclude-dir") >= 10

    def test_env_var_erweitert_die_liste(self, monkeypatch):
        monkeypatch.setenv("SCOUT_SCAN_EXCLUDES", "generated, fixtures")
        assert is_excluded_dir("generated")
        assert is_excluded_dir("fixtures")
        assert "generated" in build_exclude_flags()

    def test_file_patterns_loest_braces_auf(self):
        assert file_patterns("**/*.{ts,tsx}") == ("*.ts", "*.tsx")
        assert file_patterns("**/*.py") == ("*.py",)
        assert file_patterns("") == ()


class TestIterSourceFiles:
    def test_fremdcode_wird_uebersprungen(self, tmp_path: Path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("x = 1\n")
        (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
        (tmp_path / "node_modules" / "pkg" / "index.js").write_text("var x = 1\n")
        (tmp_path / "dist").mkdir()
        (tmp_path / "dist" / "bundle.js").write_text("x\n")

        gefunden = [p.relative_to(tmp_path).as_posix() for p in iter_source_files(tmp_path)]
        assert gefunden == ["src/app.py"]

    def test_glob_filtert_endungen(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("x\n")
        (tmp_path / "b.ts").write_text("x\n")
        gefunden = sorted(p.name for p in iter_source_files(tmp_path, "**/*.ts"))
        assert gefunden == ["b.ts"]


# ═══════════════════════════════════════════════════════════════════════
# regex_scan
# ═══════════════════════════════════════════════════════════════════════

class TestRegexScan:
    def test_findet_treffer_mit_zeile(self, tmp_path: Path):
        (tmp_path / "app.py").write_text("import os\nos.system('ls')\n")
        result = regex_batch(
            [{"pattern_id": "P1", "scan_query": r"os\.system\(", "scan_file_glob": "**/*.py"}],
            str(tmp_path),
        )
        assert len(result["P1"]) == 1
        assert result["P1"][0]["line"] == 2
        assert "os.system" in result["P1"][0]["match"]

    def test_flags_steuern_gross_klein(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("HASHLIB.MD5(x)\n")
        ohne = regex_batch([{"pattern_id": "P", "scan_query": r"hashlib\.md5", "scan_file_glob": "**/*.py"}], str(tmp_path))
        mit = regex_batch([{"pattern_id": "P", "scan_query": r"hashlib\.md5", "scan_file_glob": "**/*.py", "scan_flags": "i"}], str(tmp_path))
        assert ohne["P"] == []
        assert len(mit["P"]) == 1

    def test_node_modules_wird_nicht_gescannt(self, tmp_path: Path):
        (tmp_path / "node_modules" / "x").mkdir(parents=True)
        (tmp_path / "node_modules" / "x" / "i.js").write_text("secret = 'abcdef123'\n")
        result = regex_batch(
            [{"pattern_id": "S", "scan_query": r"secret\s*=", "scan_file_glob": "**/*.js"}],
            str(tmp_path),
        )
        assert result["S"] == []

    def test_kaputtes_muster_reisst_andere_nicht_mit(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("eval(x)\n")
        result = regex_batch(
            [
                {"pattern_id": "BAD", "scan_query": "([", "scan_file_glob": "**/*.py"},
                {"pattern_id": "GOOD", "scan_query": r"eval\(", "scan_file_glob": "**/*.py"},
            ],
            str(tmp_path),
        )
        assert result["BAD"] == []
        assert len(result["GOOD"]) == 1

    def test_binaerdatei_wird_uebersprungen(self, tmp_path: Path):
        (tmp_path / "blob.py").write_bytes(b"\x00\x01eval(x)\x00")
        result = regex_batch([{"pattern_id": "E", "scan_query": r"eval\(", "scan_file_glob": "**/*.py"}], str(tmp_path))
        assert result["E"] == []

    def test_obergrenze_pro_pattern(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("eval(x)\n" * 50)
        result = regex_batch([{"pattern_id": "E", "scan_query": r"eval\(", "scan_file_glob": "**/*.py"}], str(tmp_path), max_matches=10)
        assert len(result["E"]) == 10

    def test_compile_flags(self):
        assert compile_flags("i") & 2  # re.IGNORECASE
        assert compile_flags(None)
        assert compile_flags("xs") & 16  # re.DOTALL


# ═══════════════════════════════════════════════════════════════════════
# Pattern-Bibliothek: die Security-Patterns müssen laufen, ohne code_intel
# ═══════════════════════════════════════════════════════════════════════

VULN_FIXTURES = {
    "app.py": (
        'API_KEY = "sk-live-9f8e7d6c5b4a3210"\n'
        "import os, hashlib, sqlite3\n"
        "from flask import request\n"
        "def q(n):\n"
        "    c = sqlite3.connect('x').cursor()\n"
        "    c.execute(f\"SELECT * FROM t WHERE n = '{n}'\")\n"
        "    open(os.path.join('/d', request.args['f'])).read()\n"
        "    os.system('convert ' + n)\n"
        "    return hashlib.md5(n.encode()).hexdigest()\n"
    ),
    "App.java": (
        "class A {\n"
        '  String password = "geheim123";\n'
        "  void h(Request request) {\n"
        '    log.info("x" + request.getParameter("u"));\n'
        "    stmt.executeQuery(\"SELECT * FROM t WHERE n = '\" + n + \"'\");\n"
        "    ObjectInputStream in = new ObjectInputStream(request.getInputStream());\n"
        "  }\n"
        "}\n"
    ),
    "crash.c": (
        "#include <string.h>\n"
        "void f(char *e) {\n"
        "  char p[8];\n"
        "  strcpy(p, e);\n"
        "  printf(e);\n"
        "  char *q = malloc(n * 4);\n"
        "  free(q);\n"
        "  q->x = 1;\n"
        "}\n"
    ),
    "users.rb": (
        "class C\n"
        "  def create\n"
        "    User.new(params[:user])\n"
        '    system("x #{params[:f]}")\n'
        "    User.where(\"n = '#{params[:n]}'\")\n"
        "  end\n"
        "end\n"
    ),
}


@pytest.fixture(scope="module")
def scan_engine():
    """Pattern-Bibliothek laden und über die Fixtures laufen lassen."""
    from scout.bughunt.bughunt_scanrunner import batch_grep_scans
    from scout.bughunt.core.patterns import init_patterns, list_all_patterns

    init_patterns()
    return batch_grep_scans, list_all_patterns()


@pytest.fixture(scope="module")
def fixture_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("vuln")
    for name, content in VULN_FIXTURES.items():
        (root / name).write_text(content)
    return root


class TestSecurityPatternsOhneCodeIntel:
    def test_keine_uebersprungenen_security_patterns_mehr(self):
        from scout.bughunt.core.patterns import init_patterns, list_all_patterns

        init_patterns()
        patterns = list_all_patterns()
        # code_security_scan ist raus: seine Ausgabe ist ein Rich-Panel und damit
        # nicht automatisch auswertbar — die Regeln laufen jetzt als scan_type=regex.
        assert not [p for p in patterns if p.get("scan_type") == "code_security_scan"]
        # Und jedes Security-Pattern muss einen ausführbaren Ausdruck mitbringen,
        # sonst landet es wieder als "manueller Scan" im Report.
        ohne_query = [
            p["pattern_id"] for p in patterns
            if p.get("category") == "security" and not p.get("scan_query")
        ]
        assert ohne_query == []

    def test_jedes_security_pattern_findet_sein_fixture(self, scan_engine, fixture_root):
        batch_grep_scans, patterns = scan_engine
        erwartet = [
            "S020", "S021", "S022", "S023", "S024",
            "J001", "J003", "J004", "J005",
            "CPP001", "CPP002", "CPP003", "CPP004", "CPP005",
            "RB001", "RB002", "RB003",
        ]
        result = batch_grep_scans(patterns, str(fixture_root))
        getroffen = {f["pattern_id"] for f in result["auto_findings"]}
        fehlend = [pid for pid in erwartet if pid not in getroffen]
        assert fehlend == [], f"ohne Treffer: {fehlend}"

    def test_treffer_tragen_datei_und_zeile(self, scan_engine, fixture_root):
        batch_grep_scans, patterns = scan_engine
        result = batch_grep_scans(patterns, str(fixture_root))
        for finding in result["auto_findings"]:
            assert finding["file"], finding
            assert finding["line"] >= 1, finding

    def test_regeln_sind_kompilierbar(self):
        from scout.bughunt.core.patterns import init_patterns, list_all_patterns

        init_patterns()
        kaputt = []
        for pattern in list_all_patterns():
            if pattern.get("scan_type") != "regex":
                continue
            try:
                __import__("re").compile(pattern["scan_query"], compile_flags(pattern.get("scan_flags")))
            except Exception as exc:  # noqa: BLE001
                kaputt.append((pattern["pattern_id"], str(exc)))
        assert kaputt == []


# ═══════════════════════════════════════════════════════════════════════
# code_intel-Dispatch: Namespace-first, Legacy-Fallback
# ═══════════════════════════════════════════════════════════════════════

class _FakeEntry:
    def __init__(self, result: str):
        self.handler = lambda args=None, **kw: result


class _FakeRegistry:
    def __init__(self, entries: dict[str, str]):
        self.entries = {name: _FakeEntry(result) for name, result in entries.items()}
        self.seen: list[str] = []

    def get_entry(self, name: str):
        self.seen.append(name)
        return self.entries.get(name)


def _with_registry(monkeypatch, registry):
    import sys
    import types

    module = types.ModuleType("scout.shared.registry")
    module.registry = registry  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "scout.shared.registry", module)


class TestCodeIntelDispatch:
    def test_mapping_zeigt_auf_namespace(self):
        from scout.bughunt.bughunt_scanrunner import _CODE_INTEL_SCAN_MAP

        cfg = _CODE_INTEL_SCAN_MAP["code_security_scan"]
        assert cfg["tool"] == "code_review"
        assert cfg["op"] == "security_scan"
        assert cfg["legacy"] == "code_security_scan"

    def test_namespace_wird_bevorzugt(self, monkeypatch):
        from scout.bughunt.bughunt_scanrunner import _run_code_intel_scan

        registry = _FakeRegistry({
            "code_review": json.dumps({"findings": [], "summary": {"total": 0}}),
            "code_security_scan": json.dumps({"findings": [], "summary": {"total": 0}}),
        })
        _with_registry(monkeypatch, registry)
        _run_code_intel_scan("code_security_scan", "/tmp")
        assert registry.seen[0] == "code_review"

    def test_legacy_fallback_wenn_namespace_fehlt(self, monkeypatch):
        from scout.bughunt.bughunt_scanrunner import _run_code_intel_scan

        registry = _FakeRegistry({"code_security_scan": json.dumps({"findings": []})})
        _with_registry(monkeypatch, registry)
        result = _run_code_intel_scan("code_security_scan", "/tmp")
        assert result["tool_status"] == "ok"
        assert registry.seen == ["code_review", "code_security_scan"]

    def test_hinweis_nennt_namespace_aufruf(self, monkeypatch):
        from scout.bughunt.bughunt_scanrunner import _run_code_intel_scan

        _with_registry(monkeypatch, _FakeRegistry({}))
        result = _run_code_intel_scan("code_security_scan", "/tmp")
        assert "code_review" in result["tool_status"]
        assert "security_scan" in result["tool_status"]

    def test_rich_ausgabe_ohne_funde_gilt_als_sauber(self, monkeypatch):
        from scout.bughunt.bughunt_scanrunner import _run_code_intel_scan

        panel = "\x1b[32m╭─ ✅ Security Scan — No Vulnerabilities Found ─╮\x1b[0m"
        _with_registry(monkeypatch, _FakeRegistry({"code_review": panel}))
        result = _run_code_intel_scan("code_security_scan", "/tmp")
        assert result["tool_status"] == "ok"
        assert result["findings"] == []
