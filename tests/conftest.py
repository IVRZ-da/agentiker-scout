"""Shared conftest for scout plugin tests.

Vereinheitlicht die Mock-Infrastruktur aus 3 Quell-Plugins.
Bietet MockPluginContext, MockRegistry und _fmt Mock.

Coverage wird vor sys.modules Shim gestartet, damit
auch ueber Shims geladene Module getrackt werden.

Verwendet tests/fakes/ fuer wiederverwendbare Mock-Factorys.
"""

from __future__ import annotations

import json
import sys
import types
import warnings
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# Coverage manuell starten (bevor sys.modules Shims injected werden)
try:
    import coverage
    _cov = coverage.Coverage(source_pkg=["scout"])
    _cov.start()
except Exception:
    pass

from tests.fakes import (
    MockEntry,
    MockPluginContext,
    MockRegistry,
    create_fmt_mock,
    create_registry,
)

# ─── DeprecationWarning-Filter (importlib __package__ != __spec__.parent) ─
warnings.filterwarnings("ignore", message=".*__package__.*")

# ─── sys.modules Injection (Rueckwaertskompatibilitaet fuer ~50 Test-Dateien)
# Wird schrittweise durch pytest Fixtures + fakes/ ersetzt.
# ─────────────────────────────────────────────────────────────────────

def _install_fmt_mock() -> None:
    """Install _fmt mock using tests/fakes/ factory.

    Ueberschreibt sys.modules["scout._fmt"] falls bereits geladen.
    """
    fm = create_fmt_mock()
    fmt_mod = types.ModuleType("scout._fmt")
    fmt_mod.fmt_ok = fm["fmt_ok"]
    fmt_mod.fmt_err = fm["fmt_err"]
    fmt_mod.fmt_markdown = fm["fmt_markdown"]
    fmt_mod.fmt_warn = fm["fmt_warn"]
    fmt_mod.fmt_info = lambda msg, data=None: json.dumps(
        {"status": "info", "message": msg, **(data or {})}, ensure_ascii=False
    )
    fmt_mod.fmt_json = lambda data: json.dumps(
        data, ensure_ascii=False, indent=2, default=str
    )
    fmt_mod.fmt_table = lambda *a, **kw: ""
    fmt_mod.fmt_code = lambda code, lang="", **kw: f"```{lang}\n{code}\n```"
    fmt_mod.fmt_research_status = lambda d, title=None: json.dumps(
        {"status": "ok", **(d or {})}, ensure_ascii=False
    )
    sys.modules["_fmt"] = fmt_mod
    sys.modules["scout._fmt"] = fmt_mod


_install_fmt_mock()

# ─── Hermes Module Mocks (fuer registry.dispatch, PluginContext etc.) ─────

_hermes = types.ModuleType("hermes_cli")
_hermes.plugins = types.ModuleType("hermes_cli.plugins")
_hermes.plugins.PluginContext = MockPluginContext
sys.modules["hermes_cli"] = _hermes
sys.modules["hermes_cli.plugins"] = _hermes.plugins

# tools.registry Shim — nutzt MockRegistry aus fakes/
_tools = types.ModuleType("tools")
_tools.registry = types.ModuleType("tools.registry")
_tools.registry.registry = create_registry()
sys.modules["tools"] = _tools
sys.modules["tools.registry"] = _tools.registry

# Eintraege mit statischen Handlern (kein self!)
_dispatch_registry = _tools.registry.registry
_dispatch_registry._entries = {}


# ─── _KEEP: Module die von mock nicht ueberschrieben werden duerfen ─────
_KEEP = frozenset({
    "scout",
    "scout.shared",
    "scout.shared.detectors",
    "scout.shared.registry",
    "scout.analysis",
    "scout.analysis.tools",
    "scout.bughunt",
    "scout.bughunt.core",
    "scout.bughunt.core.model",
    "scout.research",
    "scout.research.tools",
    "scout._fmt",
})


# =====================================================================
# pytest Fixtures (statt sys.modules Shims)
# =====================================================================


@pytest.fixture
def mock_registry() -> MockRegistry:
    """Erzeugt eine frische MockRegistry fuer Tests.

    Nutze parametrisiert: mock_registry mit with_devtools=True
    """
    return create_registry()


@pytest.fixture
def mock_registry_with_devtools() -> MockRegistry:
    """MockRegistry mit verfuegbaren Chrome DevTools MCP Tools."""
    return create_registry(with_devtools=True)


@pytest.fixture
def mock_fmt() -> dict[str, Any]:
    """Liefert _fmt Mock-Funktionen (fmt_ok, fmt_err, ...)."""
    return create_fmt_mock()


@pytest.fixture
def mock_plugin_context() -> MockPluginContext:
    """Erzeugt einen MockPluginContext fuer register()-Tests."""
    return MockPluginContext()
