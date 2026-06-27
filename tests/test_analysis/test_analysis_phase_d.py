"""Tests für Phase D: Tool-Profile System + Subagent-Steering.

Importiert sys.modules Mocks aus conftest.py (hermes_cli.plugins, tools.registry, tools.delegate_tool).
"""

from __future__ import annotations

import os
import sys

# tools.delegate_tool Mock — scouts eigene tools.registry erhalten
import types as _types

import pytest

# sys.modules Mocks werden von conftest.py gesetzt (vor diesem Import)
from scout.analysis import analysis_core as core

_tools_mock = _types.ModuleType("tools")
# Vorhandene tools.registry aus sys.modules übernehmen (für Kompatibilität)
_tools_mock.registry = sys.modules.get("tools.registry", _types.ModuleType("tools.registry"))
sys.modules["tools"] = _tools_mock
_delegate_mock = _types.ModuleType("tools.delegate_tool")
_delegate_mock.DEFAULT_TOOLSETS = ["terminal", "file"]
_delegate_mock._build_child_system_prompt = lambda *a, **kw: "base prompt"
sys.modules["tools.delegate_tool"] = _delegate_mock
from tools import delegate_tool as delegate_mock  # noqa: E402


class MockEntry:
    """Mock für einen Registry-Eintrag."""

    def __init__(self, schema=None):
        self.schema = schema or {"description": ""}


# ---------------------------------------------------------------------------
# Tests: Tool-Profile System
# ---------------------------------------------------------------------------

class TestAnalysisProfiles:

    def test_default_profile_is_all(self):
        assert core.get_active_analysis_profile() == "all"

    def test_env_var_overrides_profile(self):
        os.environ["ANALYSIS_PROFILE"] = "architecture"
        try:
            assert core.get_active_analysis_profile() == "architecture"
        finally:
            del os.environ["ANALYSIS_PROFILE"]

    def test_unknown_profile_falls_back_to_all(self):
        os.environ["ANALYSIS_PROFILE"] = "nonexistent"
        try:
            assert core.get_active_analysis_profile() == "all"
        finally:
            del os.environ["ANALYSIS_PROFILE"]

    def test_all_profile_has_all_tools(self):
        profile = core.ANALYSIS_PROFILES["all"]
        assert "analysis_inspect" in profile["tools"]
        assert "analysis_architecture" in profile["tools"]
        assert "analysis_deadcode" in profile["tools"]
        assert "analysis_report" in profile["tools"]

    def test_code_profile_has_inspect_and_report(self):
        profile = core.ANALYSIS_PROFILES["code"]
        assert "analysis_inspect" in profile["tools"]
        assert "analysis_report" in profile["tools"]
        assert "analysis_architecture" not in profile["tools"]

    def test_architecture_profile_has_architecture_tool(self):
        profile = core.ANALYSIS_PROFILES["architecture"]
        assert "analysis_architecture" in profile["tools"]

    def test_deadcode_profile_has_deadcode_tool(self):
        profile = core.ANALYSIS_PROFILES["deadcode"]
        assert "analysis_deadcode" in profile["tools"]

    def test_each_profile_has_code_intel_profile(self):
        for name, profile in core.ANALYSIS_PROFILES.items():
            assert "code_intel_profile" in profile, f"{name} missing code_intel_profile"

    def test_each_profile_has_recommended_intents(self):
        for name, profile in core.ANALYSIS_PROFILES.items():
            assert "recommended_intents" in profile, f"{name} missing recommended_intents"
            assert len(profile["recommended_intents"]) > 0


class TestGetProfileTools:

    def test_get_profile_tools_all(self):
        tools = core.get_profile_tools("all")
        assert "analysis_inspect" in tools
        assert "analysis_deadcode" in tools

    def test_get_profile_tools_code(self):
        tools = core.get_profile_tools("code")
        assert "analysis_inspect" in tools
        assert "analysis_architecture" not in tools

    def test_get_profile_tools_none_uses_default(self):
        tools = core.get_profile_tools()
        assert len(tools) > 0

    def test_get_profile_tools_unknown_falls_back(self):
        tools = core.get_profile_tools("bad_profile")
        assert len(tools) == len(core.ANALYSIS_PROFILES["all"]["tools"])


# ---------------------------------------------------------------------------
# Tests: Subagent Steering
# ---------------------------------------------------------------------------

class TestSubagentSteering:

    def test_inject_subagent_steering_returns_string(self):
        steering = core.inject_subagent_steering()
        assert isinstance(steering, str)
        assert len(steering) > 100
        assert "analysis_inspect" in steering
        assert "code_cycle_detector" in steering

    def test_subagent_steering_includes_profile_info(self):
        steering = core.inject_subagent_steering()
        assert "Active profile" in steering
        assert "Automated Analysis Tools" in steering

    def test_subagent_steering_includes_manual_tools(self):
        steering = core.inject_subagent_steering()
        assert "code_symbols" in steering
        assert "code_diagnostics" in steering

    def test_subagent_steering_respects_env_profile(self):
        os.environ["ANALYSIS_PROFILE"] = "architecture"
        try:
            steering = core.inject_subagent_steering()
            assert "architecture" in steering.lower()
        finally:
            del os.environ["ANALYSIS_PROFILE"]


class TestPatchDelegateTask:

    def setup_method(self):
        # Reset mock for each test
        delegate_mock.DEFAULT_TOOLSETS = ["terminal", "file"]
        delegate_mock._build_child_system_prompt = lambda *a, **kw: "base prompt"

    def test_patch_adds_analysis_to_default_toolsets(self):
        core.patch_delegate_task()
        assert "analysis" in delegate_mock.DEFAULT_TOOLSETS

    def test_patch_does_not_duplicate(self):
        core.patch_delegate_task()
        count_before = delegate_mock.DEFAULT_TOOLSETS.count("analysis")
        core.patch_delegate_task()
        count_after = delegate_mock.DEFAULT_TOOLSETS.count("analysis")
        assert count_after == count_before
        assert count_after == 1

    def test_patched_prompt_includes_steering(self):
        core.patch_delegate_task()
        result = delegate_mock._build_child_system_prompt()
        assert "analysis_inspect" in result


# ---------------------------------------------------------------------------
# Tests: Steering Hints Injection
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="testet Steering-Hints — benötigt alte __init__.py Struktur")
class TestSteeringHints:

    def test_handles_missing_tool_gracefully(self):
        """Sollte nicht crashen wenn kein Tool im Registry ist."""
        core.inject_steering_hints()

    def test_handles_tool_without_description(self):
        """Sollte nicht crashen wenn ein Tool keine description hat."""
        entry = MockEntry({})
        import sys
        sys.modules["tools"].registry.registry.entries["code_symbols"] = entry
        core.inject_steering_hints()

    def test_steering_hints_in_plugin_init(self):
        """_register_steering aus __init__ sollte nicht crashen.

        Ruft direkt die steering-Funktionen auf statt __init__ zu verwenden,
        da __init__ Module-level Imports hat die in Tests nicht verfügbar sind.
        """
        # Die Funktionen sind bereits in analysis_core getestet
        # Hier testen wir nur dass sie aufrufbar sind
        core.inject_steering_hints()
        core.patch_delegate_task()


# ---------------------------------------------------------------------------
# Tests: Integration — Vollständiger Analyse-Workflow mit Profilen
# ---------------------------------------------------------------------------

class TestAnalysisIntegration:

    def test_workflow_with_code_profile(self):
        """Kompletter Durchlauf: Profile → Analyse-Detection → Tools → Persist."""
        core._analysis_session.reset()

        # Profile setzen
        os.environ["ANALYSIS_PROFILE"] = "code"
        try:
            # Detection
            ctx = core.inject_analysis_context(messages=[
                {"role": "user", "content": "Analysiere die main.py Datei"}
            ])
            assert ctx is not None
            assert core._analysis_session.active is True

            # Tool-Call
            core.track_tool_call(
                tool_name="code_symbols",
                args={"path": "main.py"},
                result="[{'name': 'Main', 'line': 1}]",
                duration_ms=100,
                status="ok",
            )

            # Persist
            core.persist_analysis_session()
            assert core._analysis_session.active is False
        finally:
            del os.environ["ANALYSIS_PROFILE"]

    def test_db_profile_only_has_report(self):
        """DB-Profil hat nur analysis_report."""
        tools = core.get_profile_tools("db")
        assert len(tools) == 1
        assert tools[0] == "analysis_report"

    def test_web_profile_only_has_report(self):
        """Web-Profil hat nur analysis_report."""
        tools = core.get_profile_tools("web")
        assert len(tools) == 1
        assert tools[0] == "analysis_report"
