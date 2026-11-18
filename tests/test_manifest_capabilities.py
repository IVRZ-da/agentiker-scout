"""Manifest-Capabilities spiegeln die echte Registrierung.

``plugin.yaml`` fuehrt ``provides_tools``/``provides_hooks``. Handgepflegt driften sie
still (bisher: 42 Namen in falscher Reihenfolge, ``manifest_version: 2`` fehlte) —
``hermes plugins validate`` meldet jede registrierte Faehigkeit, die im Manifest fehlt.
``scripts/gen_manifest_capabilities.py`` leitet die Listen aus ``register()`` ab;
diese Tests erzwingen, dass das Manifest zum Code passt.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
import yaml  # noqa: E402

PLUGIN = Path(__file__).resolve().parent.parent
MANIFEST = PLUGIN / "plugin.yaml"
SCRIPT = PLUGIN / "scripts" / "gen_manifest_capabilities.py"


@pytest.fixture(scope="module")
def manifest():
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def registered_tools():
    import scout

    class Stub:
        def __init__(self):
            self.tools = {}

        def register_tool(self, name, toolset, schema, handler, description=""):
            self.tools[name] = schema

        def register_hook(self, *a, **k):
            pass

        def __getattr__(self, item):
            return lambda *a, **k: None

    ctx = Stub()
    scout.register(ctx)
    return sorted(ctx.tools)


def test_manifest_version_declared(manifest):
    assert manifest.get("manifest_version") == 2


def test_requires_hermes_declared(manifest):
    assert manifest.get("requires_hermes"), "requires_hermes fehlt (SemVer-Untergrenze)"


def test_provides_tools_match_registration(manifest, registered_tools):
    declared = sorted(manifest.get("provides_tools") or [])
    assert declared == registered_tools, (
        f"Manifest {declared} != Registrierung {registered_tools} — "
        "scripts/gen_manifest_capabilities.py ausfuehren"
    )


def test_provides_hooks_are_declared(manifest):
    hooks = manifest.get("provides_hooks") or []
    assert hooks, "keine Hooks deklariert"
    assert all(isinstance(h, str) and h for h in hooks)


def test_generator_check_passes():
    """Der Pre-Commit-Gate-Aufruf muss gruen sein."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        capture_output=True, text=True, cwd=PLUGIN, timeout=120,
        env={k: v for k, v in __import__("os").environ.items() if k != "PYTHONPATH"},
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[:500]
    assert "OK" in result.stdout


def test_manifest_lists_three_dispatchers(manifest):
    """Nach der Fusion: 3 Dispatcher, nicht 42 Einzel-Tools."""
    assert len(manifest.get("provides_tools") or []) == 3
