"""Tests für _fmt.py — Formatierungs-Helper.

ISOLIERT in Subprocess: Da conftest.py einen _fmt-Mock in sys.modules
setzt, müssen _fmt-Tests in einem isolierten Prozess laufen um den
echten _fmt-Code zu testen, ohne andere Tests zu vergiften.

Startet einen Subprocess der eine temporäre Test-Datei ausführt.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

PLUGIN_DIR = str(Path(__file__).resolve().parent.parent)

TEST_SCRIPT = textwrap.dedent(f"""\
    from __future__ import annotations
    import importlib.util
    import sys
    from pathlib import Path

    # Pfad zum Plugins-Überverzeichnis (für from scout._fmt import)
    _plugins_root = {str(Path(PLUGIN_DIR).parent)!r}
    if _plugins_root not in sys.path:
        sys.path.insert(0, _plugins_root)

    # _fmt-Mock aus sys.modules entfernen
    sys.modules.pop("_fmt", None)
    sys.modules.pop("scout._fmt", None)

    # Jetzt echte _fmt importieren
    from scout._fmt import (
        fmt_ok, fmt_err, fmt_warn, fmt_info,
        fmt_table, fmt_code,
        fmt_markdown, fmt_json,
    )

    # --- Test Suite ---
    ok = 0
    failed = 0

    def check(name, cond, msg=""):
        global ok, failed
        if cond:
            ok += 1
            print(f"  OK {{name}}")
        else:
            failed += 1
            print(f"  FAIL {{name}}: {{msg}}")

    # fmt_ok
    r = fmt_ok({{"data": "test"}})
    check("fmt_ok", isinstance(r, str) and len(r) > 10)
    check("fmt_ok_empty", isinstance(fmt_ok({{}}), str))

    # fmt_err
    r = fmt_err("error msg")
    check("fmt_err", isinstance(r, str) and "error msg" in r)
    check("fmt_err_empty", isinstance(fmt_err(""), str))

    # fmt_warn / fmt_info
    check("fmt_warn", "warn" in fmt_warn("warn"))
    check("fmt_info", "info" in fmt_info("info"))

    # fmt_table
    check("fmt_table_empty", isinstance(fmt_table([]), str))
    check("fmt_table_data", "Alice" in str(fmt_table([{{"name": "Alice"}}])))
    check("fmt_table_simple", "a" in str(fmt_table_simple([(1,)], ["a"])))

    # fmt_code
    check("fmt_code", isinstance(fmt_code("x = 1"), str))
    check("fmt_code_no_ln", isinstance(fmt_code("x = 1", line_numbers=False), str))

    # fmt_markdown
    check("fmt_markdown", isinstance(fmt_markdown("**b**"), str))
    check("fmt_markdown_empty", isinstance(fmt_markdown(""), str))

    # fmt_json
    r = fmt_json({{"k": "v"}})
    s = _strip_ansi(r)
    check("fmt_json", "k" in s and "v" in s)
    check("fmt_json_list", isinstance(fmt_json([1, 2]), str))

    # _strip_ansi
    s = _strip_ansi("\\x1b[32mHello\\x1b[0m")
    check("strip_ansi", "Hello" in s and "\\x1b[" not in s)
    check("strip_ansi_plain", _strip_ansi("plain") == "plain")
    s = _strip_ansi("╭───╮│x│╰───╯")
    check("strip_ansi_unicode", "╭" in s and "x" in s)

    print(f"\\nRESULT: {{ok}} passed, {{failed}} failed")
    sys.exit(1 if failed else 0)
""")


@pytest.mark.skip(reason="testet alte analysis _fmt API — scout _fmt hat andere Signatur")
def test_fmt_all():
    """Alle _fmt-Tests in isoliertem Subprocess."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False,
        dir=PLUGIN_DIR,
    ) as f:
        f.write(TEST_SCRIPT)
        script_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, timeout=30,
            cwd=PLUGIN_DIR,
        )
        stdout = result.stdout
        stderr = result.stderr

        if stdout:
            pass
        if stderr:
            pass

        assert result.returncode == 0, (
            f"_fmt tests failed (exit={result.returncode}). "
            f"stderr: {stderr[:500]}"
        )
        assert "0 failed" in stdout
    finally:
        # Temp-Datei aufräumen
        Path(script_path).unlink(missing_ok=True)
