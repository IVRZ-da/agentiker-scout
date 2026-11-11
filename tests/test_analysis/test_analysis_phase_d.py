"""Tests für Phase D: Tool-Profile System + Subagent-Steering.

Importiert sys.modules Mocks aus conftest.py (hermes_cli.plugins, tools.registry, tools.delegate_tool).
"""

from __future__ import annotations

import os
import sys

# tools.delegate_tool Mock — scouts eigene tools.registry erhalten
import types as _types

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

# ---------------------------------------------------------------------------
# Tests: Steering Hints Injection
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Tests: Integration — Vollständiger Analyse-Workflow mit Profilen
# ---------------------------------------------------------------------------

class TestAnalysisIntegration:


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
