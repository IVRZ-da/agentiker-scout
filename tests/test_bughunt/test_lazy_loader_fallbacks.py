"""Die Lazy-Loader in ``bughunt/tools/base.py``.

Die Handler laden `bughunt_core` und `bughunt_fix` erst beim ersten Aufruf und
haben dafuer drei Wege (Package-Import, sys.modules, importlib). Der Happy Path
war getestet, die Fallbacks nicht — genau dort brechen Plugins in Umgebungen, in
denen der relative Import nicht greift (Subagent-Dispatch, Skripte).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def loader():
    """Importiert das Modul und stellt die Modul-Caches danach wieder her."""
    from scout.bughunt.tools import base

    saved = (base._CORE_MODULE, base._FIX_MODULE)
    base._CORE_MODULE = None
    base._FIX_MODULE = None
    yield base
    base._CORE_MODULE, base._FIX_MODULE = saved


class TestGetCore:
    def test_caches_after_first_load(self, loader):
        first = loader._get_core()
        second = loader._get_core()
        assert first is second
        assert loader._CORE_MODULE is first

    def test_uses_sys_modules_when_relative_import_fails(self, loader, monkeypatch):
        """Liegt bughunt_core schon in sys.modules, wird diese Instanz genutzt."""
        import builtins

        real_import = builtins.__import__

        def blocker(name, *args, **kwargs):
            if name == "scout.bughunt" and args and args[2] and "bughunt_core" in args[2]:
                raise ImportError("blockiert")
            if name.endswith("bughunt_core"):
                raise ImportError("blockiert")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocker)
        # Testumgebung hat bughunt_core bereits geladen
        core = loader._get_core()
        assert core is not None
        assert hasattr(core, "PATTERNS_BY_ID")

    def test_raises_when_spec_unavailable(self, loader, monkeypatch):
        """Ohne relativen Import, ohne sys.modules und ohne Spec: klarer Fehler."""
        import builtins

        real_import = builtins.__import__

        def blocker(name, *args, **kwargs):
            if "bughunt_core" in name or name == "scout.bughunt":
                raise ImportError("blockiert")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocker)
        monkeypatch.delitem(sys.modules, "bughunt_core", raising=False)
        monkeypatch.setattr(
            "importlib.util.spec_from_file_location", lambda *a, **k: None
        )

        with pytest.raises(ImportError, match="Cannot load bughunt_core"):
            loader._get_core()


class TestGetFixMod:
    def test_caches_after_first_load(self, loader):
        first = loader._get_fix_mod()
        second = loader._get_fix_mod()
        assert first is second

    def test_raises_when_spec_unavailable(self, loader, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def blocker(name, *args, **kwargs):
            if "bughunt_fix" in name or name == "scout.bughunt":
                raise ImportError("blockiert")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocker)
        monkeypatch.delitem(sys.modules, "bughunt_fix", raising=False)
        monkeypatch.setattr(
            "importlib.util.spec_from_file_location", lambda *a, **k: None
        )

        with pytest.raises(ImportError, match="Cannot load bughunt_fix"):
            loader._get_fix_mod()


def test_call_tool_fallback_when_analysis_missing():
    """Ohne analysis-Domaene liefert _call_tool einen Fehler-Dict, keinen Crash.

    Der Fallback entsteht beim Import — deshalb in einem eigenen Prozess, in dem
    ein Meta-Path-Finder ``scout.analysis.tools.base`` blockiert.
    """
    script = f"""
import sys, types
sys.path.insert(0, "{PLUGIN_ROOT.parent}")

class Blocker:
    def find_spec(self, name, path=None, target=None):
        if name == "scout.analysis.tools.base":
            raise ImportError("blockiert")
        return None

sys.meta_path.insert(0, Blocker())

from scout.bughunt.tools.base import _call_tool
result = _call_tool("code_search")
assert isinstance(result, dict), result
assert "error" in result, result
assert "nicht verf\\u00fcgbar" in result["error"], result
print("FALLBACK_OK")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=120, cwd=str(PLUGIN_ROOT),
    )
    assert "FALLBACK_OK" in result.stdout, result.stderr or result.stdout


class TestTryCreateBughuntPlan:
    """Lose Kopplung an plan_follow: fehlt das Plugin, passiert nichts."""

    @pytest.fixture
    def base(self):
        from scout.bughunt.tools import base

        return base

    def test_returns_none_without_entry(self, base, monkeypatch):
        import types

        fake = types.ModuleType("scout.shared.registry")

        class Registry:
            def get_entry(self, name):
                return None

        fake.registry = Registry()
        monkeypatch.setitem(sys.modules, "scout.shared.registry", fake)

        assert base._try_create_bughunt_plan("p", "s") is None

    def test_returns_none_when_handler_not_callable(self, base, monkeypatch):
        import types

        fake = types.ModuleType("scout.shared.registry")

        class Entry:
            handler = "kein callable"

        class Registry:
            def get_entry(self, name):
                return Entry()

        fake.registry = Registry()
        monkeypatch.setitem(sys.modules, "scout.shared.registry", fake)

        assert base._try_create_bughunt_plan("p", "s") is None

    def test_parses_json_string_result(self, base, monkeypatch):
        import types

        fake = types.ModuleType("scout.shared.registry")

        class Entry:
            handler = staticmethod(lambda args: '{"plan_id": "x", "status": "ok"}')

        class Registry:
            def get_entry(self, name):
                return Entry()

        fake.registry = Registry()
        monkeypatch.setitem(sys.modules, "scout.shared.registry", fake)

        result = base._try_create_bughunt_plan("projekt", "sess-1", scope="deep", findings_count=3)
        assert result["plan_id"] == "x"

    def test_passes_dict_result_through(self, base, monkeypatch):
        import types

        fake = types.ModuleType("scout.shared.registry")

        class Entry:
            handler = staticmethod(lambda args: {"plan_id": "y"})

        class Registry:
            def get_entry(self, name):
                return Entry()

        fake.registry = Registry()
        monkeypatch.setitem(sys.modules, "scout.shared.registry", fake)

        assert base._try_create_bughunt_plan("p", "s")["plan_id"] == "y"

    def test_exception_returns_none(self, base, monkeypatch):
        import types

        fake = types.ModuleType("scout.shared.registry")

        class Entry:
            @staticmethod
            def handler(args):
                raise RuntimeError("plan_follow kaputt")

        class Registry:
            def get_entry(self, name):
                return Entry()

        fake.registry = Registry()
        monkeypatch.setitem(sys.modules, "scout.shared.registry", fake)

        assert base._try_create_bughunt_plan("p", "s") is None


class TestResponseHelpers:
    def test_ok_sets_status(self):
        import json

        from scout.bughunt.tools.base import _ok

        assert json.loads(_ok({"a": 1})) == {"a": 1, "status": "ok"}

    def test_ok_keeps_existing_status(self):
        import json

        from scout.bughunt.tools.base import _ok

        assert json.loads(_ok({"status": "completed"}))["status"] == "completed"

    def test_err_shape(self):
        import json

        from scout.bughunt.tools.base import _err

        assert json.loads(_err("kaputt")) == {"error": "kaputt", "status": "error"}
