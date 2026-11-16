"""Tests für den code_intel-Namespace-Alias (shared/tool_alias.py)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scout.shared.tool_alias import TOOL_ALIASES, registry_is_available, resolve_tool_call


class TestResolveToolCall:
    def test_ohne_alias_unveraendert(self):
        name, args = resolve_tool_call("terminal", {"command": "ls"}, lambda _n: True)
        assert name == "terminal"
        assert args == {"command": "ls"}

    def test_namespace_aktiv_schreibt_um(self):
        # Nur der Dispatcher ist registriert, der Einzelname nicht (Default ab 0.6.25).
        name, args = resolve_tool_call(
            "code_security_scan",
            {"path": "/tmp"},
            lambda tool: tool == "code_review",
        )
        assert name == "code_review"
        assert args == {"path": "/tmp", "op": "security_scan"}

    def test_legacy_aktiv_bleibt_beim_einzelnamen(self):
        name, args = resolve_tool_call(
            "code_security_scan",
            {"path": "/tmp"},
            lambda tool: tool in ("code_review", "code_security_scan"),
        )
        assert name == "code_security_scan"
        assert "op" not in args

    def test_nichts_registriert_bleibt_beim_namen(self):
        name, args = resolve_tool_call("code_symbols", {}, lambda _t: False)
        assert name == "code_symbols"
        assert "op" not in args

    def test_passendes_op_bleibt(self):
        name, args = resolve_tool_call(
            "code_security_scan",
            {"op": "security_scan", "path": "/tmp"},
            lambda tool: tool == "code_review",
        )
        assert name == "code_review"
        assert args["op"] == "security_scan"

    def test_abweichendes_op_wird_nicht_ueberschrieben(self):
        name, args = resolve_tool_call(
            "code_security_scan",
            {"op": "review_assistant"},
            lambda tool: tool == "code_review",
        )
        assert name == "code_security_scan"
        assert args["op"] == "review_assistant"

    def test_dispatcher_name_bleibt(self):
        for name in ("code_search", "code_lsp", "code_graph", "code_edit", "code_review", "code_git", "code_meta"):
            assert resolve_tool_call(name, {}, lambda _t: True)[0] == name

    def test_kwargs_werden_nicht_mutiert(self):
        original = {"path": "/tmp"}
        resolve_tool_call("code_symbols", original, lambda tool: tool == "code_search")
        assert original == {"path": "/tmp"}

    def test_registry_is_available_wirft_nicht(self):
        praedikat = registry_is_available()
        assert praedikat("gibt-es-nicht-12345") is False


class TestAliasTabelle:
    def test_ziele_sind_bekannte_dispatcher(self):
        dispatcher = {"code_search", "code_lsp", "code_graph", "code_edit", "code_review", "code_git", "code_meta"}
        for alt, (gruppe, op) in TOOL_ALIASES.items():
            assert gruppe in dispatcher, f"{alt} → unbekannte Gruppe {gruppe}"
            assert op and " " not in op, f"{alt} → kaputtes op {op!r}"

    def test_tabelle_passt_zum_code_intel_katalog(self):
        """Gegenprobe gegen die echte Namespace-Definition, wenn sie daneben liegt."""
        katalog = Path(__file__).resolve().parents[2] / "code_intel" / "namespaces.py"
        if not katalog.exists():
            pytest.skip("code_intel nicht installiert")

        quelle = katalog.read_text(encoding="utf-8")
        erwartet: dict[str, tuple[str, str]] = {}
        for gruppe, body in re.findall(r'"(code_[a-z_]+)": \{(.*?)\n    \},', quelle, re.S):
            ops = re.search(r'"ops": \[(.*?)\]', body, re.S)
            for op in re.findall(r'"([a-z_]+)"', ops.group(1) if ops else ""):
                name = f"code_{op}"
                if name != gruppe:
                    erwartet[name] = (gruppe, op)

        assert TOOL_ALIASES == erwartet, (
            "Alias-Tabelle weicht vom code_intel-Katalog ab: "
            f"fehlt={sorted(set(erwartet) - set(TOOL_ALIASES))} "
            f"zuviel={sorted(set(TOOL_ALIASES) - set(erwartet))}"
        )
