"""Robustheit der Tool-Registrierung in ``scout/__init__.py``.

``_register_tools`` darf nie das ganze Plugin kippen: fehlt die Registry, wird
übersprungen; ein Tool ohne auflösbaren Handler wird übersprungen; ein Tool,
dessen Wrapping scheitert, darf die übrigen nicht mitreißen.

Der Namespace-Shim (``_ensure_scout_namespace``) wird hier bewusst nicht
getestet: er greift nur, wenn ``sys.modules['scout']`` fehlt — das lässt sich
in-process nicht prüfen, ohne das geladene Plugin-Paket aus ``sys.modules`` zu
entfernen und damit alle übrigen Tests zu vergiften.
"""

from __future__ import annotations

import sys

import pytest

import scout
from scout.shared.tool_registry import ToolDef

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def _tool(**overrides) -> ToolDef:
    base = {
        "name": "analysis_diff",
        "domain": "analysis",
        "schema": {"parameters": {"properties": {}}},
    }
    base.update(overrides)
    return ToolDef(**base)


def test_missing_tool_registry_is_skipped(monkeypatch, mock_plugin_context):
    """Ist ``shared.tool_registry`` nicht importierbar: Warnung, kein Crash."""
    monkeypatch.setitem(sys.modules, "scout.shared.tool_registry", None)

    scout._register_tools(mock_plugin_context)

    mock_plugin_context.register_tool.assert_not_called()


def test_tool_without_resolvable_handler_is_skipped(monkeypatch, mock_plugin_context):
    tool = _tool(handler=None, handler_module="scout.gibt_es_nicht", handler_name="nope")
    monkeypatch.setattr(
        "scout.shared.tool_registry.collect", lambda: [tool], raising=True
    )

    scout._register_tools(mock_plugin_context)

    mock_plugin_context.register_tool.assert_not_called()


def test_broken_tool_does_not_block_the_rest(monkeypatch, mock_plugin_context):
    """Ein Tool mit kaputtem Schema fliegt raus, das nächste wird registriert."""
    broken = _tool(name="analysis_broken", schema=None, handler=lambda args: "{}")
    healthy = _tool(name="analysis_ok", handler=lambda args: "{}")
    monkeypatch.setattr(
        "scout.shared.tool_registry.collect", lambda: [broken, healthy], raising=True
    )

    scout._register_tools(mock_plugin_context)

    registered = [call.args[0] for call in mock_plugin_context.register_tool.call_args_list]
    assert registered == ["analysis_ok"]
