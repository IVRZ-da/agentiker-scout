"""Import-Fallbacks in ``bughunt/tools/base.py`` (Ergänzung, keine Duplikate).

``tests/test_bughunt/test_lazy_loader_fallbacks.py`` deckt den Happy Path und
die ``spec is None``-Zweige ab. Hier fehlen die beiden anderen Wege:

* der Import-Fallback ``_call_tool`` (Modul-Ebene, greift nur wenn
  ``scout.analysis.tools.base`` nicht importierbar ist) — im bestehenden Test
  läuft das in einem Subprozess und wird von Coverage deshalb nicht gesehen;
* der importlib-Zweig in ``_get_core`` (Zeilen 64-76), also laden über
  ``spec_from_file_location`` wenn weder relativer Import noch
  ``sys.modules['bughunt_core']`` greifen.

Beide Tests stellen ``sys.modules`` und die Modul-Caches im ``finally``
wieder her — es bleibt keine zweite Core-Instanz zurück.
"""

from __future__ import annotations

import builtins
import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def _block_import(monkeypatch, predicate) -> None:
    """Lässt ``__import__`` für Namen fehlschlagen, die ``predicate`` erfüllen."""
    real_import = builtins.__import__

    def blocker(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: A002
        if predicate(name, fromlist):
            raise ImportError("blockiert (Test)")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocker)


def test_call_tool_fallback_defined_when_analysis_unavailable(monkeypatch):
    """Ohne ``scout.analysis`` definiert das Modul einen eigenen ``_call_tool``.

    Das Modul wird in-process unter einem anderen Modulnamen aus derselben Datei
    ausgeführt, damit die ``except ImportError``-Zeilen tatsächlich laufen.
    """
    from scout.bughunt.tools import base as real_base

    _block_import(monkeypatch, lambda name, fromlist: name.startswith("scout.analysis"))

    spec = importlib.util.spec_from_file_location(
        "bh_base_import_fallback_probe", Path(real_base.__file__).resolve()
    )
    assert spec is not None and spec.loader is not None
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)

    result = probe._call_tool("code_search")
    assert isinstance(result, dict)
    assert "nicht verfügbar" in result["error"]
    assert "code_search" in result["error"]
    # Kein Delegieren an das echte _call_tool: der Fallback antwortet selbst.
    assert result is not real_base._call_tool("code_search")


class TestGetCoreImportlibBranch:
    """Zweiter Fallback-Weg: kein relativer Import, kein sys.modules-Eintrag."""

    @pytest.fixture
    def patched_env(self, monkeypatch):
        from scout.bughunt.tools import base

        saved_core_module = base._CORE_MODULE
        saved_fix_module = base._FIX_MODULE
        saved_scout_sub = sys.modules.get("scout.bughunt.bughunt_core")
        saved_bare = sys.modules.get("bughunt_core")

        base._CORE_MODULE = None
        base._FIX_MODULE = None
        monkeypatch.delitem(sys.modules, "bughunt_core", raising=False)
        _block_import(
            monkeypatch,
            lambda name, fromlist: name == "scout.bughunt" and "bughunt_core" in fromlist,
        )
        try:
            yield base
        finally:
            base._CORE_MODULE = saved_core_module
            base._FIX_MODULE = saved_fix_module
            for key, value in (
                ("scout.bughunt.bughunt_core", saved_scout_sub),
                ("bughunt_core", saved_bare),
            ):
                if value is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = value

    def test_loads_module_via_importlib_and_registers_both_names(self, patched_env):
        base = patched_env

        core = base._get_core()

        assert hasattr(core, "PATTERNS_BY_ID")
        assert base._CORE_MODULE is core
        # Beide Namen werden registriert, damit monkeypatch auf den
        # bare-name dieselbe Instanz trifft wie die Handler.
        assert sys.modules["scout.bughunt.bughunt_core"] is core
        assert sys.modules["bughunt_core"] is core

    def test_second_call_uses_cache_without_reloading(self, patched_env):
        base = patched_env

        first = base._get_core()
        second = base._get_core()

        assert first is second
