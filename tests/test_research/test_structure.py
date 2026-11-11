"""
Struktur- und Dispatch-Signatur-Tests für das scout.research Modul.

Prüft:
- Alle Research-Modul-Dateien existieren
- Alle Tool-Handler haben korrekte Signatur (args, **kwargs)
- Scout plugin.yaml ist valide YAML
- imports in research_hooks.py sind lazy
"""

import inspect
import os
import sys
from pathlib import Path

SCOUT_ROOT = Path(__file__).resolve().parent.parent.parent  # scout/
RESEARCH_DIR = SCOUT_ROOT / "research"  # scout/research/


def test_research_directory_exists():
    """Research-Verzeichnis muss existieren."""
    assert RESEARCH_DIR.exists(), f"Research-Verzeichnis nicht gefunden: {RESEARCH_DIR}"
    assert RESEARCH_DIR.is_dir()


def test_required_files_exist():
    """Alle erforderlichen Research-Modul-Dateien müssen existieren."""
    # Scout-Root-Ebene
    root_required = [
        "plugin.yaml",
        "__init__.py",
    ]
    for filename in root_required:
        path = SCOUT_ROOT / filename
        assert path.exists(), f"Fehlende Datei: {path}"
        assert path.stat().st_size > 0, f"Leere Datei: {path}"

    # Research-Ebene
    research_required = [
        "__init__.py",
        "research_tools.py",
        "research_hooks.py",
    ]
    for filename in research_required:
        path = RESEARCH_DIR / filename
        assert path.exists(), f"Fehlende Datei: {path}"
        assert path.stat().st_size > 0, f"Leere Datei: {path}"


def test_plugin_yaml_is_valid():
    """plugin.yaml muss valides YAML sein und alle Pflichtfelder haben."""
    import yaml

    path = SCOUT_ROOT / "plugin.yaml"
    with open(path) as f:
        data = yaml.safe_load(f)

    assert isinstance(data, dict), "plugin.yaml muss ein Mapping sein"
    assert "name" in data, "plugin.yaml braucht 'name'"
    assert data["name"] == "agentiker-scout", "plugin name muss 'agentiker-scout' sein"
    assert "version" in data, "plugin.yaml braucht 'version'"
    assert "description" in data, "plugin.yaml braucht 'description'"
    assert "provides_hooks" in data, "plugin.yaml braucht 'provides_hooks' (Manifest v2)"
    hook_names = data["provides_hooks"]
    assert "pre_llm_call" in hook_names, "provides_hooks muss 'pre_llm_call' enthalten"
    assert "post_tool_call" in hook_names, "provides_hooks muss 'post_tool_call' enthalten"
    assert "on_session_end" in hook_names, "provides_hooks muss 'on_session_end' enthalten"
    assert "provides_tools" in data and len(data["provides_tools"]) >= 40


def test_research_init_importable():
    """research/__init__.py muss als Modul spezifizierbar sein."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("scout.research", RESEARCH_DIR / "__init__.py")
    assert spec is not None, "Kann research/__init__.py nicht spezifizieren"
    assert spec.origin is not None


def test_research_tools_shim_exists():
    """research_tools.py (Legacy-Shim) muss existieren und nicht-leer sein."""
    shim_path = RESEARCH_DIR / "research_tools.py"
    assert shim_path.exists(), "research_tools.py fehlt"
    content = shim_path.read_text()
    assert len(content) > 50, "research_tools.py ist zu kurz"
    assert "from scout.research.tools" in content, "research_tools.py muss Re-Export enthalten"


def test_research_tools_imports():
    """research_tools (tools/ Package) muss importierbar sein (ausserhalb Hermes)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "research_tools", RESEARCH_DIR / "tools" / "__init__.py"
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "scout.research.tools"
    # sys.modules-Eintrag nur temporaer: ohne Restore sehen spaetere Tests eine
    # zweite Modulinstanz mit eigenen (alten) Pfad-Konstanten.
    _previous = sys.modules.get("scout.research.tools")
    sys.modules["scout.research.tools"] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        if _previous is not None:
            sys.modules["scout.research.tools"] = _previous
        else:
            sys.modules.pop("scout.research.tools", None)

    # Prüfe dass alle Tool-Funktionen existieren
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
        assert hasattr(mod, name), f"research_tools fehlt Funktion: {name}"


def test_all_handlers_have_args_signature():
    """
    KRITISCH: Jeder Handler muss (args: dict, **kwargs) -> str Signatur haben.
    Das ist der häufigste Plugin-Bug (TypeError bei Dispatch).
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "research_tools", RESEARCH_DIR / "tools" / "__init__.py"
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "scout.research.tools"
    # sys.modules-Eintrag nur temporaer: ohne Restore sehen spaetere Tests eine
    # zweite Modulinstanz mit eigenen (alten) Pfad-Konstanten.
    _previous = sys.modules.get("scout.research.tools")
    sys.modules["scout.research.tools"] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        if _previous is not None:
            sys.modules["scout.research.tools"] = _previous
        else:
            sys.modules.pop("scout.research.tools", None)

    handler_names = [
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

    for name in handler_names:
        handler = getattr(mod, name, None)
        assert handler is not None, f"Handler {name} nicht gefunden"

        sig = inspect.signature(handler)
        params = list(sig.parameters.keys())
        assert len(params) >= 1, f"{name}: hat keine Parameter (braucht mindestens args)"

        first_param = params[0]
        assert first_param == "args", (
            f"{name}: erster Parameter ist '{first_param}', erwartet 'args'. "
            f"Komplette Signatur: {sig}"
        )

        # Prüfe auf **kwargs (zweiter Param) oder ob args dict-ähnlich sein kann
        has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        if len(params) >= 2:
            second = list(sig.parameters.values())[1]
            if second.kind == inspect.Parameter.VAR_KEYWORD:
                has_kwargs = True

        # **kwargs ist optional, aber args MUSS dict-artig sein
        assert has_kwargs or ("dict" in str(sig.parameters["args"].annotation).lower()), (
            f"{name}: args sollte als dict annotiert sein oder **kwargs haben"
        )


def test_handlers_return_string():
    """Jeder Handler muss einen String zurückgeben (JSON oder Fehler)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "research_tools", RESEARCH_DIR / "tools" / "__init__.py"
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "scout.research.tools"
    # sys.modules-Eintrag nur temporaer: ohne Restore sehen spaetere Tests eine
    # zweite Modulinstanz mit eigenen (alten) Pfad-Konstanten.
    _previous = sys.modules.get("scout.research.tools")
    sys.modules["scout.research.tools"] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        if _previous is not None:
            sys.modules["scout.research.tools"] = _previous
        else:
            sys.modules.pop("scout.research.tools", None)

    handler_names = [
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

    for name in handler_names:
        handler = getattr(mod, name, None)
        sig = inspect.signature(handler)
        ret = sig.return_annotation
        if ret is not inspect.Parameter.empty:
            assert "str" in str(ret), f"{name}: return annotation ist {ret}, erwartet str"


def test_data_directories_created_on_import():
    """shared/paths.ensure_dirs() legt alle Nutzdatenverzeichnisse an.

    Ersetzt den frueheren Code-Text-Check (``"mkdir(parents=True..." in code``),
    der nur pruefte, ob ein String in einer Datei steht — und beim Umbau auf
    shared/paths.py zwangslaeufig brach, ohne dass sich am Verhalten etwas
    geaendert haette.
    """
    from scout.shared import paths

    paths.ensure_dirs()

    for directory in (
        paths.SESSIONS_DIR,
        paths.PLANS_DIR,
        paths.RESULTS_DIR,
        paths.PATTERNS_DIR,
        paths.ANALYSIS_DIR,
    ):
        assert directory.is_dir(), f"{directory} wurde nicht angelegt"


def test_data_root_is_outside_the_plugin_directory():
    """Nutzdaten gehoeren NICHT ins Code-Repo (sonst Update-/Backup-Chaos)."""
    from scout.shared import paths

    assert paths.DATA_ROOT != paths.PLUGIN_DIR
    assert paths.PLUGIN_DIR not in paths.DATA_ROOT.parents, (
        f"DATA_ROOT {paths.DATA_ROOT} liegt im Plugin-Verzeichnis {paths.PLUGIN_DIR}"
    )


def test_data_root_honours_env_override():
    """SCOUT_DATA_DIR ist die dokumentierte Umschaltung (Tests, Evals)."""
    from scout.shared import paths

    env_value = os.environ.get(paths.ENV_DATA_DIR)
    assert env_value, f"{paths.ENV_DATA_DIR} muss in der Testsuite gesetzt sein"
    assert str(paths.DATA_ROOT) == str(Path(env_value).expanduser().resolve())


def test_reload_paths_moves_ensure_dirs_too():
    """Nach reload_paths() muss ensure_dirs() die NEUEN Verzeichnisse anlegen.

    Regression: ``_ALL_DIRS`` war eine Modul-Konstante und fror die Pfade beim
    Import ein. ``ensure_dirs()`` legte danach weiter die alten Verzeichnisse
    an, waehrend die Handler in die neuen schrieben -> FileNotFoundError in
    jedem Research-Task.

    Laeuft im Subprozess, weil reload_paths() globalen Modulzustand aendert.
    """
    import subprocess
    import sys

    probe = (
        "import os, sys, tempfile\n"
        "from pathlib import Path\n"
        f"sys.path.insert(0, {str(SCOUT_ROOT.parent)!r})\n"
        "from scout.shared import paths\n"
        "tmp = Path(tempfile.mkdtemp())\n"
        "os.environ[paths.ENV_DATA_DIR] = str(tmp)\n"
        "paths.reload_paths()\n"
        "paths.ensure_dirs()\n"
        "assert paths.SESSIONS_DIR == tmp / 'bughunt' / 'sessions', paths.SESSIONS_DIR\n"
        "assert (tmp / 'research' / 'plans').is_dir(), 'research/plans fehlt'\n"
        "assert (tmp / 'bughunt' / 'sessions').is_dir(), 'bughunt/sessions fehlt'\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(SCOUT_ROOT),
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert "OK" in result.stdout


def test_hook_imports_lazy():
    """
    research_hooks.py muss 'from tools.registry' LAZY importieren
    (innerhalb einer Funktion, nicht am Modul-Header).
    """
    hooks_path = RESEARCH_DIR / "research_hooks.py"
    content = hooks_path.read_text()
    lines = content.split("\n")

    # Finde die erste Funktion im File
    first_def_line = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("def "):
            first_def_line = i
            break

    assert first_def_line >= 0, "Keine Funktion in research_hooks.py gefunden"

    # Prüfe dass alle 'from tools.registry' imports NACH der ersten Funktion kommen
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "from tools.registry" in stripped and "import" in stripped:
            assert i > first_def_line, (
                f"'from tools.registry import' in Zeile {i + 1}, aber erste Funktion "
                f"ist in Zeile {first_def_line + 1}. Import muss IN einer Funktion sein."
            )
