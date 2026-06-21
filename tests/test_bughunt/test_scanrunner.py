"""Tests for bughunt_scanrunner — grep-basierte automatische Scans."""



# ═══════════════════════════════════════════════════════════════════════
# _parse_grep_line
# ═══════════════════════════════════════════════════════════════════════

class TestParseGrepLine:
    """_parse_grep_line — einzelne grep-Zeile parsen."""

    def test_normal_line(self):
        from scout.bughunt.bughunt_scanrunner import _parse_grep_line
        result = _parse_grep_line("src/file.ts:42:const x = 1")
        assert result is not None
        assert result["file"] == "src/file.ts"
        assert result["line"] == 42
        assert result["match"] == "const x = 1"

    def test_line_with_colon_in_path(self):
        from scout.bughunt.bughunt_scanrunner import _parse_grep_line
        # Windows-Pfad mit Doppelpunkt
        result = _parse_grep_line("C:\\\\src\\\\file.ts:10:hello world")
        assert result is not None
        assert result["file"] in ("C:\\\\src\\\\file.ts", "C:\\src\\file.ts")
        assert result["line"] == 10

    def test_empty_line(self):
        from scout.bughunt.bughunt_scanrunner import _parse_grep_line
        assert _parse_grep_line("") is None

    def test_binary_file_warning(self):
        from scout.bughunt.bughunt_scanrunner import _parse_grep_line
        assert _parse_grep_line("Binary file matches") is None

    def test_no_match_pattern(self):
        from scout.bughunt.bughunt_scanrunner import _parse_grep_line
        assert _parse_grep_line("just some text without line number") is None

    def test_long_match_truncated(self):
        from scout.bughunt.bughunt_scanrunner import _parse_grep_line
        long = "f.ts:1:" + "x" * 500
        result = _parse_grep_line(long)
        assert result is not None
        assert len(result["match"]) <= 200


# ═══════════════════════════════════════════════════════════════════════
# run_grep_scan
# ═══════════════════════════════════════════════════════════════════════

class TestRunGrepScan:
    """run_grep_scan — grep-Scans auf echten Dateien."""

    def test_finds_matches(self, tmp_path):
        from scout.bughunt.bughunt_scanrunner import run_grep_scan

        # Testdatei anlegen
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.ts").write_text(
            "const x = 1\nconst secret = 'abc'\nconst y = 2\n"
        )

        results = run_grep_scan("secret", "*.ts", str(tmp_path))
        assert len(results) == 1
        assert results[0]["file"].endswith("app.ts")
        assert results[0]["line"] == 2
        assert "secret" in results[0]["match"]

    def test_no_matches(self, tmp_path):
        from scout.bughunt.bughunt_scanrunner import run_grep_scan

        (tmp_path / "test.txt").write_text("hello world")
        results = run_grep_scan("nonexistent", "*.txt", str(tmp_path))
        assert results == []

    def test_invalid_path(self):
        from scout.bughunt.bughunt_scanrunner import run_grep_scan
        results = run_grep_scan("test", "*.py", "/nonexistent/path/xyz789")
        assert results == []  # Graceful degradation

    def test_multiple_files(self, tmp_path):
        from scout.bughunt.bughunt_scanrunner import run_grep_scan

        (tmp_path / "a.ts").write_text("const key = '123'\n")
        (tmp_path / "b.ts").write_text("const key = '456'\n")

        results = run_grep_scan("key", "*.ts", str(tmp_path))
        assert len(results) == 2

    def test_glob_with_braces(self, tmp_path):
        """Glob-Patterns wie **/*.{ts,tsx} werden korrekt aufgelöst."""
        from scout.bughunt.bughunt_scanrunner import run_grep_scan

        (tmp_path / "a.ts").write_text("const x = 1\n")
        (tmp_path / "a.tsx").write_text("const x = 2\n")

        results = run_grep_scan("const x", "**/*.{ts,tsx}", str(tmp_path))
        assert len(results) == 2

    def test_glob_simple(self, tmp_path):
        from scout.bughunt.bughunt_scanrunner import run_grep_scan

        (tmp_path / "data.py").write_text("import os\n")
        (tmp_path / "data.js").write_text("import os\n")

        results = run_grep_scan("import", "*.py", str(tmp_path))
        assert len(results) == 1


# ═══════════════════════════════════════════════════════════════════════
# get_scan_summary
# ═══════════════════════════════════════════════════════════════════════

class TestGetScanSummary:
    """get_scan_summary — menschenlesbare Zusammenfassung."""

    def test_auto_findings_summary(self):
        from scout.bughunt.bughunt_scanrunner import get_scan_summary
        result = get_scan_summary({
            "auto_findings": [
                {"severity": "P0", "file": "a.ts"},
                {"severity": "P0", "file": "b.ts"},
                {"severity": "P1", "file": "c.ts"},
            ],
            "manual_instructions": [],
            "auto_count": 3,
            "manual_count": 0,
        })
        assert isinstance(result, str)
        assert "3" in result
        assert "P0" in result
        assert "P1" in result

    def test_no_auto_findings(self):
        from scout.bughunt.bughunt_scanrunner import get_scan_summary
        result = get_scan_summary({
            "auto_findings": [],
            "manual_instructions": ["🔧 S001: Bitte manuell scannen"],
            "auto_count": 0,
            "manual_count": 1,
        })
        assert "Keine automatischen Treffer" in result
        assert "S001" in result

    def test_empty(self):
        from scout.bughunt.bughunt_scanrunner import get_scan_summary
        result = get_scan_summary({
            "auto_findings": [],
            "manual_instructions": [],
            "auto_count": 0,
            "manual_count": 0,
        })
        assert isinstance(result, str)
        assert len(result) > 0


# ═══════════════════════════════════════════════════════════════════════
# batch_grep_scans
# ═══════════════════════════════════════════════════════════════════════

class TestBatchGrepScans:
    """batch_grep_scans — mehrere Patterns parallel."""

    def test_mixed_patterns(self, tmp_path):
        from scout.bughunt.bughunt_scanrunner import batch_grep_scans

        (tmp_path / "app.ts").write_text(
            "const api_key = '12345';\nconsole.log('test');\n" * 3
        )

        patterns = [
            {"pattern_id": "S002", "name": "Secrets", "severity": "P0",
             "category": "security", "scan_type": "grep",
             "scan_query": "api_key", "scan_file_glob": "*.ts",
             "description": "Test", "fix_description": "Fix"},
            {"pattern_id": "S001", "name": "execSync", "severity": "P0",
             "category": "security", "scan_type": "code_search",
             "scan_query": "execSync", "scan_file_glob": "*.ts",
             "description": "Test", "fix_description": "Fix"},
        ]
        result = batch_grep_scans(patterns, str(tmp_path))
        assert result["auto_count"] > 0  # Secrets als Treffer
        assert result["manual_count"] == 2  # 1 auto-scan Msg + 1 manual
        assert len(result["manual_instructions"]) == 2  # 1 auto-scan Msg + 1 manual

    def test_all_grep_patterns(self, tmp_path):
        from scout.bughunt.bughunt_scanrunner import batch_grep_scans

        (tmp_path / "test.py").write_text("eval('print(1)')\n")

        patterns = [
            {"pattern_id": "S009", "name": "Python eval", "severity": "P0",
             "category": "security", "scan_type": "grep",
             "scan_query": "eval(", "scan_file_glob": "*.py",
             "description": "Test", "fix_description": "Fix"},
        ]
        result = batch_grep_scans(patterns, str(tmp_path))
        assert result["auto_count"] == 1
        assert result["auto_findings"][0]["file"].endswith("test.py")
        assert result["auto_findings"][0]["pattern_id"] == "S009"

    def test_no_patterns(self, tmp_path):
        from scout.bughunt.bughunt_scanrunner import batch_grep_scans
        result = batch_grep_scans([], str(tmp_path))
        assert result["auto_count"] == 0
        assert result["manual_count"] == 0

    def test_unknown_scan_type(self, tmp_path):
        from scout.bughunt.bughunt_scanrunner import batch_grep_scans
        patterns = [{"pattern_id": "X001", "name": "Custom",
                     "scan_type": "invalid_type", "scan_query": ""}]
        result = batch_grep_scans(patterns, str(tmp_path))
        assert "Unbekannter Scan-Typ" in result["manual_instructions"][0]
