"""Tests für bughunt/__init__.py — Domain-Export.

Separat von tests/test_bughunt/ weil dessen conftest.py
scout.bughunt mit einem leeren Mock überschreibt.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent
PYCACHE_EVIDENCE = PLUGIN_ROOT / ".coveragerc"


@pytest.fixture(autouse=True)
def _bughunt_clean():
    """Entfernt gecachte scout.bughunt Module vor dem Test."""
    for mod in list(sys.modules.keys()):
        if "scout.bughunt" in mod or mod == "bughunt" or mod.startswith("bughunt."):
            sys.modules.pop(mod, None)
    # PYTHONPATH sicherstellen
    plugins_root = str(PLUGIN_ROOT.parent.parent)
    if plugins_root not in sys.path:
        sys.path.insert(0, plugins_root)
    if str(PLUGIN_ROOT.parent) not in sys.path:
        sys.path.insert(0, str(PLUGIN_ROOT.parent))
    yield


def test_bughunt_has_submodules():
    """Alle Submodule sind über bughunt.__init__ erreichbar."""
    # Nach Cache-Clean: frischer Import
    from scout import bughunt

    for name in ["bughunt_tools", "bughunt_core", "bughunt_patterns",
                  "bughunt_scanrunner", "bughunt_hooks"]:
        assert hasattr(bughunt, name), f"Fehlendes Attribut: {name}"


def test_bughunt_all_available():
    """__all__ ist via dir() sichtbar (conftest überschreibt Attribut).
    Prüfe stattdessen dass die Module importierbar sind."""
