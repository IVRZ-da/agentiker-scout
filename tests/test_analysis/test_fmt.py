"""Tests für _fmt.py — Formatierungs-Helfer.

ISOLIERT: Da conftest.py einen _fmt-Mock in sys.modules setzt, müssen
_fmt-Tests das Mock-Modul temporär entfernen und nach dem Test
wiederherstellen.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _fmt_isolation():
    """Entfernt _fmt-Mock vor dem Test, stellt ihn danach wieder her."""
    old_fmt = sys.modules.pop("_fmt", None)
    old_scout_fmt = sys.modules.pop("scout._fmt", None)
    plugins_root = str(PLUGIN_ROOT.parent)
    if plugins_root not in sys.path:
        sys.path.insert(0, plugins_root)
    yield
    if old_fmt is not None:
        sys.modules["_fmt"] = old_fmt
    if old_scout_fmt is not None:
        sys.modules["scout._fmt"] = old_scout_fmt


def _import_fmt():
    """Importiert _fmt nach Mock-Isolation."""
    from scout._fmt import (
        fmt_code,
        fmt_err,
        fmt_info,
        fmt_json,
        fmt_markdown,
        fmt_ok,
        fmt_table,
        fmt_warn,
    )
    return fmt_ok, fmt_err, fmt_warn, fmt_info, fmt_table, fmt_code, fmt_markdown, fmt_json


# ── Basic Smoke Tests ─────────────────────────────────────────────────


def test_fmt_ok():
    import_all = _import_fmt()
    r = import_all[0]({"data": "test"})
    assert isinstance(r, str) and len(r) > 10


def test_fmt_ok_empty():
    assert isinstance(_import_fmt()[0]({}), str)


def test_fmt_err():
    assert isinstance(_import_fmt()[1]("error msg"), str)


def test_fmt_warn():
    assert isinstance(_import_fmt()[2]("warn test"), str)


def test_fmt_info():
    assert isinstance(_import_fmt()[3]("info test"), str)


def test_fmt_table():
    ft = _import_fmt()[4]
    assert isinstance(ft(["h"], [["a"]]), str)
    assert isinstance(ft(["Name"], [["Alice"]]), str)


def test_fmt_code():
    assert isinstance(_import_fmt()[5]("x = 1"), str)


def test_fmt_markdown():
    assert isinstance(_import_fmt()[6]("**b**"), str)
    assert isinstance(_import_fmt()[6](""), str)


def test_fmt_json():
    fj = _import_fmt()[7]
    assert isinstance(fj({"k": "v"}), str)
    assert isinstance(fj([1, 2]), str)


# ── Edge Cases ────────────────────────────────────────────────────────


def test_fmt_ok_with_string():
    """fmt_ok akzeptiert String als data."""
    f, _, _, _, _, _, _, _ = _import_fmt()
    r = f("einfacher string")
    parsed = json.loads(r)
    assert parsed["status"] == "ok"
    assert parsed["message"] == "einfacher string"


def test_fmt_ok_with_message_param():
    """fmt_ok mit message Parameter."""
    f, _, _, _, _, _, _, _ = _import_fmt()
    r = f({"data": "test"}, message="zusatzinfo")
    parsed = json.loads(r)
    assert parsed["status"] == "ok"
    assert parsed["message"] == "zusatzinfo"
    assert parsed["data"] == "test"


def test_fmt_err_with_details():
    """fmt_err mit details dict."""
    _, f, _, _, _, _, _, _ = _import_fmt()
    r = f("error", details={"code": 42})
    parsed = json.loads(r)
    assert parsed["status"] == "error"
    assert parsed["details"]["code"] == 42


def test_fmt_warn_with_details():
    """fmt_warn mit details dict."""
    _, _, f, _, _, _, _, _ = _import_fmt()
    r = f("warnung", details={"source": "test"})
    parsed = json.loads(r)
    assert parsed["status"] == "warning"
    assert parsed["details"]["source"] == "test"


def test_fmt_info_with_data():
    """fmt_info mit data dict."""
    _, _, _, f, _, _, _, _ = _import_fmt()
    r = f("info msg", data={"count": 5})
    parsed = json.loads(r)
    assert parsed["status"] == "info"
    assert parsed["data"]["count"] == 5


def test_fmt_table_with_title():
    """fmt_table mit title."""
    _, _, _, _, ft, _, _, _ = _import_fmt()
    r = ft(["A"], [["1"]], title="Tabelle 1")
    assert "Tabelle 1" in r


def test_fmt_research_status():
    """fmt_research_status als dict-Wrapper."""
    from scout._fmt import fmt_research_status
    r = fmt_research_status({"query": "test"})
    parsed = json.loads(r)
    assert parsed["status"] == "ok"
    assert parsed["query"] == "test"


def test_fmt_research_status_with_title():
    """fmt_research_status mit optionalem title."""
    from scout._fmt import fmt_research_status
    r = fmt_research_status({"query": "x"}, title="Forschung")
    parsed = json.loads(r)
    assert parsed["status"] == "ok"
    assert parsed["title"] == "Forschung"
    assert parsed["query"] == "x"
