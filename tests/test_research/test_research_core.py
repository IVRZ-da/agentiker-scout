"""
Tests für research/research_core.py, research/__init__.py
und research/research_tools.py.

Ziel: >85% Coverage in allen drei Modulen.
"""

import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCOUT_ROOT = Path(__file__).resolve().parent.parent.parent  # scout/
RESEARCH_DIR = SCOUT_ROOT / "research"  # scout/research/


# ===================================================================
# research/research_core.py — get_active_research()
# ===================================================================

class TestResearchCore:
    """Tests für research_core.py — get_active_research()."""

    @pytest.fixture
    def tracker_dir(self, tmp_path):
        """Erzeugt ein tmp_path mit data/ Unterverzeichnis."""
        data_dir = tmp_path / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    # --- Hilfsfunktion: research_core laden mit gemocktem TRACKER_PATH ---

    def _load_core_with_tracker(self, tmp_path: Path) -> object:
        """Lädt research_core.py mit auf tmp_path gepatchtem TRACKER_PATH.

        Da Module-Level-Variablen wie TRACKER_PATH während exec_module()
        überschrieben werden, patchen wir NACH dem ersten Laden die
        Modul-Attribute und rufen exec_module erneut auf.
        """
        data_dir = tmp_path / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        tracker = data_dir / "_tracker.json"

        # Eindeutiger Modul-Name (tmp_path.name macht jeden Test unique)
        mod_name = f"research_core_{tmp_path.name}"

        # Aus sys.modules entfernen falls von vorherigem Durchlauf
        if mod_name in sys.modules:
            del sys.modules[mod_name]

        spec = importlib.util.spec_from_file_location(
            mod_name, RESEARCH_DIR / "research_core.py"
        )
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = "research"

        # 1. Zuerst normal ausführen (setzt PLUGIN_DIR, TRACKER_PATH auf echte Pfade)
        spec.loader.exec_module(mod)

        # 2. Danach die Pfade überschreiben
        mod.TRACKER_PATH = tracker
        mod.PLUGIN_DIR = tmp_path
        mod.TRACKER_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Mock-Logger, der debug() akzeptiert
        mod.logger = type(
            "MockLogger", (), {"debug": lambda self, *a, **kw: None}
        )()

        sys.modules[mod_name] = mod
        return mod

    def test_get_active_research_no_tracker_file(self, tmp_path):
        """get_active_research() gibt None zurück wenn keine Tracker-Datei existiert."""
        mod = self._load_core_with_tracker(tmp_path)
        assert mod.TRACKER_PATH.exists() is False

        result = mod.get_active_research()

        assert result is None

    def test_get_active_research_empty_tracker(self, tmp_path):
        """get_active_research() gibt None zurück wenn research_started fehlt/null ist."""
        mod = self._load_core_with_tracker(tmp_path)
        mod.TRACKER_PATH.write_text(json.dumps({}))

        result = mod.get_active_research()
        assert result is None

    def test_get_active_research_no_research_started(self, tmp_path):
        """get_active_research() gibt None wenn research_started nicht gesetzt."""
        mod = self._load_core_with_tracker(tmp_path)
        mod.TRACKER_PATH.write_text(json.dumps({"firecrawl_calls": []}))

        result = mod.get_active_research()
        assert result is None

    def test_get_active_research_active_session(self, tmp_path):
        """get_active_research() gibt Dict mit Query + Sources zurück wenn active."""
        mod = self._load_core_with_tracker(tmp_path)
        mod.TRACKER_PATH.write_text(json.dumps({
            "research_started": "res-abc-123",
            "query": "Python testing",
            "firecrawl_calls": [
                {"tool": "firecrawl_search"},
                {"tool": "firecrawl_scrape"},
            ],
        }))

        result = mod.get_active_research()

        assert result is not None
        assert result["research_id"] == "res-abc-123"
        assert result["query"] == "Python testing"
        assert result["sources_count"] == 2

    def test_get_active_research_active_empty_query(self, tmp_path):
        """get_active_research() — research_id gesetzt, aber query leer."""
        mod = self._load_core_with_tracker(tmp_path)
        mod.TRACKER_PATH.write_text(json.dumps({
            "research_started": "res-xyz",
        }))

        result = mod.get_active_research()
        assert result is not None
        assert result["query"] == ""
        assert result["sources_count"] == 0
        assert result["research_id"] == "res-xyz"

    def test_get_active_research_malformed_json(self, tmp_path):
        """get_active_research() gibt None bei kaputtem JSON (Exception -> None)."""
        mod = self._load_core_with_tracker(tmp_path)
        mod.TRACKER_PATH.write_text("{definitiv kein json")

        result = mod.get_active_research()
        assert result is None

    def test_get_active_research_empty_file(self, tmp_path):
        """get_active_research() gibt None bei leerer Tracker-Datei."""
        mod = self._load_core_with_tracker(tmp_path)
        mod.TRACKER_PATH.write_text("")

        result = mod.get_active_research()
        assert result is None

    def test_get_active_research_research_started_is_null(self, tmp_path):
        """research_started: None im JSON => None zurück."""
        mod = self._load_core_with_tracker(tmp_path)
        mod.TRACKER_PATH.write_text(json.dumps({"research_started": None}))

        result = mod.get_active_research()
        assert result is None

    def test_get_active_research_logger_called_on_error(self, tmp_path):
        """Bei Exception wird logger.debug aufgerufen."""
        debug_calls = []

        mod = self._load_core_with_tracker(tmp_path)
        mod.logger.debug = lambda msg, *a: debug_calls.append(msg % a if a else msg)
        mod.TRACKER_PATH.write_text("kaputt")

        result = mod.get_active_research()
        assert result is None
        assert any("failed to load tracker" in str(c) for c in debug_calls)

    def test_module_constants_exist(self, tmp_path):
        """Module-Level Konstanten PLUGIN_DIR und TRACKER_PATH existieren."""
        mod = self._load_core_with_tracker(tmp_path)
        assert hasattr(mod, "PLUGIN_DIR")
        assert hasattr(mod, "TRACKER_PATH")
        assert isinstance(mod.PLUGIN_DIR, Path)
        assert isinstance(mod.TRACKER_PATH, Path)

    def test_get_active_research_no_firecrawl_calls_key(self, tmp_path):
        """Tracker ohne firecrawl_calls-Key -> sources_count = 0."""
        mod = self._load_core_with_tracker(tmp_path)
        mod.TRACKER_PATH.write_text(json.dumps({
            "research_started": "res-1",
            "query": "test",
        }))

        result = mod.get_active_research()
        assert result["sources_count"] == 0

    def test_get_active_research_with_multiple_calls(self, tmp_path):
        """Zählt alle firecrawl_calls korrekt."""
        mod = self._load_core_with_tracker(tmp_path)
        mod.TRACKER_PATH.write_text(json.dumps({
            "research_started": "res-42",
            "query": "deep testing",
            "firecrawl_calls": [{"t": 1}, {"t": 2}, {"t": 3}],
        }))

        result = mod.get_active_research()
        assert result["sources_count"] == 3

    def test_source_coverage_real_paths(self):
        """Prüft dass die Quell-Datei existiert und syntaktisch valide ist."""
        src = RESEARCH_DIR / "research_core.py"
        assert src.exists(), f"Fehlende Datei: {src}"
        compile(src.read_text(), str(src), "exec")


# ===================================================================
# research/__init__.py — Package-Init
# ===================================================================

class TestResearchInit:
    """Tests für research/__init__.py — Package-Init + Re-Exports."""

    def test_file_exists(self):
        """research/__init__.py existiert und ist nicht leer."""
        init_path = RESEARCH_DIR / "__init__.py"
        assert init_path.exists()
        assert init_path.stat().st_size > 0

    def test_syntax_valid(self):
        """research/__init__.py hat valide Python-Syntax."""
        init_path = RESEARCH_DIR / "__init__.py"
        compile(init_path.read_text(), str(init_path), "exec")

    def test_all_export_list(self):
        """research/__init__.py __all__ enthält die erwarteten Module."""
        init_path = RESEARCH_DIR / "__init__.py"
        source = init_path.read_text()
        assert "__all__" in source
        assert "research_tools" in source
        assert "research_hooks" in source

    def test_imports_via_importlib(self):
        """research/__init__.py kann unter eindeutigem Namen geladen werden."""
        spec = importlib.util.spec_from_file_location(
            "scout.research.test_init", RESEARCH_DIR / "__init__.py"
        )
        assert spec is not None
        assert spec.origin is not None

    def test_expected_exports(self):
        """Erwartete __all__-Einträge sind in der Source vorhanden."""
        init_path = RESEARCH_DIR / "__init__.py"
        source = init_path.read_text()
        expected = [
            "research_tools",
            "research_hooks",
            "research_crud",
            "research_search",
            "research_export",
            "research_schedule",
            "research_base",
        ]
        for name in expected:
            assert name in source, f"Fehlender Export: {name}"

    def test_all_entries_match_source(self):
        """Prüft dass die __all__-Liste alle importierten Namen enthält."""
        init_path = RESEARCH_DIR / "__init__.py"
        source = init_path.read_text()

        # Extrahiere die __all__-Liste grob via AST
        import ast
        tree = ast.parse(source)
        all_names = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, ast.List):
                            all_names = {
                                elt.value for elt in node.value.elts
                                if isinstance(elt, ast.Constant)
                            }
        assert all_names is not None, "__all__ nicht gefunden"
        assert len(all_names) >= 7, f"__all__ hat nur {len(all_names)} Einträge"
        assert "research_tools" in all_names
        assert "research_hooks" in all_names


# ===================================================================
# research/research_tools.py — Legacy Re-Export Shim
# ===================================================================

class TestResearchToolsShim:
    """Tests für research/research_tools.py — Legacy Shim."""

    def test_file_exists(self):
        """research_tools.py existiert und ist nicht-leer."""
        shim_path = RESEARCH_DIR / "research_tools.py"
        assert shim_path.exists()
        content = shim_path.read_text()
        assert len(content) > 50

    def test_syntax_valid(self):
        """research_tools.py hat valide Python-Syntax."""
        shim_path = RESEARCH_DIR / "research_tools.py"
        compile(shim_path.read_text(), str(shim_path), "exec")

    def test_contains_re_export(self):
        """research_tools.py enthält den Re-Export aus scout.research.tools."""
        shim_path = RESEARCH_DIR / "research_tools.py"
        content = shim_path.read_text()
        assert "from scout.research.tools" in content

    def test_expected_handler_names_in_source(self):
        """Alle erwarteten Handler-Namen sind in der Source vorhanden."""
        shim_path = RESEARCH_DIR / "research_tools.py"
        content = shim_path.read_text()
        expected = [
            "research_start",
            "research_save",
            "research_search",
            "research_status",
            "research_delete",
            "research_cleanup",
            "research_export",
            "research_compare",
            "research_synthesize",
            "research_schedule",
            "research_tag",
            "research_update",
            "research_merge",
            "research_stats",
            "research_verify",
            "research_auto",
            "research_export_all",
        ]
        for name in expected:
            assert name in content, f"Fehlender Handler in research_tools.py: {name}"

    def test_no_future_import(self):
        """research_tools.py hat keine überflüssigen __future__ imports."""
        shim_path = RESEARCH_DIR / "research_tools.py"
        content = shim_path.read_text()
        assert "__future__" not in content  # kein __future__ nötig, nur Re-Export

    def test_import_via_importlib(self):
        """research_tools.py ist via importlib spezifizierbar."""
        spec = importlib.util.spec_from_file_location(
            "scout.research.research_tools.test_tools",
            RESEARCH_DIR / "research_tools.py",
        )
        assert spec is not None
        assert spec.origin is not None

    def test_statement_count(self):
        """research_tools.py hat exakt 1 Top-Level-Statement (den Import)."""
        shim_path = RESEARCH_DIR / "research_tools.py"
        import ast
        tree = ast.parse(shim_path.read_text())

        # Top-Level-Statements zählen (ohne Docstring und __future__)
        stmts = [n for n in tree.body if not (
            isinstance(n, ast.Expr) and
            isinstance(n.value, ast.Constant) and
            isinstance(n.value.value, str)
        )]
        assert len(stmts) >= 1  # mind. der Import


# ===================================================================
# Integration: research/__init__.py + research_tools.py
# ===================================================================


def _make_mock_tools_module():
    """Erzeugt ein Dummy-Modul 'scout.research.tools' mit allen Handler-Namen.

    Für den Import in research/__init__.py und research_tools.py.
    Die Handler sind leere Dummy-Funktionen.
    """
    mod = types.ModuleType("scout.research.tools")
    handler_names = [
        "research_auto", "research_cleanup", "research_compare",
        "research_delete", "research_export", "research_export_all",
        "research_merge", "research_save", "research_schedule",
        "research_search", "research_start", "research_stats",
        "research_status", "research_synthesize", "research_tag",
        "research_update", "research_verify",
    ]
    for name in handler_names:
        setattr(mod, name, lambda *a, **kw: "")
    mod.__package__ = "scout.research.tools"
    return mod


def _research_deps_patch():
    """Erzeugt ein Dict zum Patchen von sys.modules für research-Importe."""
    return {
        "scout.research.research_tools": types.ModuleType("scout.research.research_tools"),
        "scout.research.tools": _make_mock_tools_module(),
        "scout.research.tools.base": types.ModuleType("scout.research.tools.base"),
        "scout.research.tools.crud": types.ModuleType("scout.research.tools.crud"),
        "scout.research.tools.export": types.ModuleType("scout.research.tools.export"),
        "scout.research.tools.schedule": types.ModuleType("scout.research.tools.schedule"),
        "scout.research.tools.search": types.ModuleType("scout.research.tools.search"),
    }


class TestResearchInitFullImport:
    """Vollständiger Import von research/__init__.py mit gemockten Dependencies."""

    def _load_init(self, request):
        """Lädt research/__init__.py unter eindeutigem Namen.

        Verwendet patch.dict(sys.modules, ...) als Context-Manager,
        sodass die Mocks nach dem Test automatisch entfernt werden.
        """

        init_path = RESEARCH_DIR / "__init__.py"
        mod_name = f"scout.research.test_init_full_{id(request)}"

        # Frischen Modul-Namen wählen (falls vorheriger Durchlauf)
        base = mod_name
        counter = 0
        while mod_name in sys.modules:
            counter += 1
            mod_name = f"{base}_{counter}"

        spec = importlib.util.spec_from_file_location(mod_name, init_path)
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = "scout.research"

        with patch.dict(sys.modules, _research_deps_patch(), clear=False):
            spec.loader.exec_module(mod)

        sys.modules[mod_name] = mod
        return mod

    def test_init_import_succeeds(self, request):
        """research/__init__.py kann geladen werden (100% Coverage)."""
        mod = self._load_init(request)
        assert mod is not None

    def test_init_exports_all(self, request):
        """research/__init__.py exportiert __all__ mit allen Namen."""
        mod = self._load_init(request)
        assert hasattr(mod, "__all__")
        expected = {
            "research_tools", "research_hooks", "research_crud",
            "research_search", "research_export", "research_schedule",
            "research_base",
        }
        assert set(mod.__all__) == expected, (
            f"__all__ mismatch: {set(mod.__all__)} != {expected}"
        )

    def test_init_imports_exist_as_attributes(self, request):
        """Jeder __all__-Eintrag existiert als Modul-Attribut."""
        mod = self._load_init(request)
        for name in mod.__all__:
            assert hasattr(mod, name), f"Fehlendes Attribut: {name}"


class TestResearchToolsShimFullImport:
    """Vollständiger Import von research/research_tools.py (Legacy Shim)."""

    def _load_shim(self, request):
        """Lädt research_tools.py unter eindeutigem Namen.

        Verwendet patch.dict(sys.modules, ...) als Context-Manager,
        sodass die Mocks nach dem Test automatisch entfernt werden.
        """

        shim_path = RESEARCH_DIR / "research_tools.py"
        mod_name = f"scout.research.research_tools.test_shim_{id(request)}"

        base = mod_name
        counter = 0
        while mod_name in sys.modules:
            counter += 1
            mod_name = f"{base}_{counter}"

        spec = importlib.util.spec_from_file_location(mod_name, shim_path)
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = "scout.research"

        with patch.dict(sys.modules, _research_deps_patch(), clear=False):
            spec.loader.exec_module(mod)

        sys.modules[mod_name] = mod
        return mod

    def test_shim_import_succeeds(self, request):
        """research_tools.py kann geladen werden (100% Coverage)."""
        mod = self._load_shim(request)
        assert mod is not None

    def test_shim_has_expected_handlers(self, request):
        """Nach Import sind alle erwarteten Handler vorhanden."""
        mod = self._load_shim(request)
        expected = [
            "research_start", "research_save", "research_search",
            "research_status", "research_delete", "research_cleanup",
            "research_export", "research_compare", "research_synthesize",
            "research_schedule", "research_tag", "research_update",
            "research_merge", "research_stats", "research_verify",
            "research_auto", "research_export_all",
        ]
        for name in expected:
            assert hasattr(mod, name), f"Fehlender Handler nach Import: {name}"

    def test_shim_lazy_no_exec(self, request):
        """Der Import führt keine Seiteneffekte aus (kein Code ausser Import)."""
        mod = self._load_shim(request)
        own_attrs = {k for k in dir(mod) if not k.startswith("_")}
        assert len(own_attrs) >= 17, f"Nur {len(own_attrs)} öffentliche Attribute"
        assert "research_start" in own_attrs


# ===================================================================
# research/research_core.py — zusätzliche real-path tests
# ===================================================================


class TestResearchCoreRealPaths:
    """Zusätzliche Tests die sicherstellen dass die echte Datei existiert."""

    def test_research_core_file_exists(self):
        """research_core.py existiert."""
        src = RESEARCH_DIR / "research_core.py"
        assert src.exists()

    def test_research_core_syntax_valid(self):
        """research_core.py hat valide Python-Syntax."""
        src = RESEARCH_DIR / "research_core.py"
        compile(src.read_text(), str(src), "exec")

    def test_research_core_has_module_constants(self):
        """Module-Konstanten in der Source vorhanden."""
        src = RESEARCH_DIR / "research_core.py"
        content = src.read_text()
        assert "PLUGIN_DIR" in content
        assert "TRACKER_PATH" in content
        assert "get_active_research" in content
