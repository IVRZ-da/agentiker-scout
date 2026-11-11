"""Sync-Test: plugin.yaml muss die echte Registrierung widerspiegeln.

Ohne diesen Test driften provides_tools/provides_hooks wieder auseinander und
`hermes plugins validate` meldet "undeclared tools" (Katalog-Admission scheitert).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

PLUGIN_DIR = Path(__file__).resolve().parent.parent
MANIFEST = PLUGIN_DIR / "plugin.yaml"


def _load_generator():
    """Laedt scripts/gen_manifest_capabilities.py als Modul."""
    path = PLUGIN_DIR / "scripts" / "gen_manifest_capabilities.py"
    spec = importlib.util.spec_from_file_location("gen_manifest_capabilities", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def manifest() -> dict:
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def registration() -> tuple[list[str], list[str]]:
    return _load_generator().collect()


def test_manifest_version_is_2(manifest):
    assert manifest.get("manifest_version") == 2


def test_provides_tools_matches_registration(manifest, registration):
    tools, _ = registration
    declared = manifest.get("provides_tools") or []
    assert sorted(declared) == tools
    assert len(declared) == len(set(declared)), "Duplikate in provides_tools"


def test_provides_hooks_matches_registration(manifest, registration):
    _, hooks = registration
    declared = manifest.get("provides_hooks") or []
    assert sorted(declared) == hooks


def test_python_dependencies_have_upper_bounds(manifest):
    deps = manifest.get("python_dependencies") or []
    assert deps, "python_dependencies fehlen (Hermes kann fehlende Pakete sonst nicht melden)"
    for dep in deps:
        assert "<" in dep, f"{dep!r} hat keine Obergrenze"


def test_generator_is_idempotent():
    """--check darf nach dem Schreiben keinen Drift mehr melden."""
    gen = _load_generator()
    tools, hooks = gen.collect()
    assert gen.render_manifest(tools, hooks) == MANIFEST.read_text(encoding="utf-8")


def test_declared_tool_count_is_plausible(manifest):
    """Sicherung gegen versehentlich geleerte Manifest-Listen."""
    assert len(manifest.get("provides_tools") or []) >= 40
    assert len(manifest.get("provides_hooks") or []) == 3
