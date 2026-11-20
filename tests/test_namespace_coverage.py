"""Jedes Tool hat genau einen Namespace-Platz — und jeder op ein echtes Tool.

Der Fusion-Test (``test_namespaces.py``) prueft die Registrierung; dieser Test prueft
die **Bijektion** in beide Richtungen:

* kein echtes Tool faellt aus dem Katalog (Waise),
* kein op im Enum zeigt ins Leere (Phantom),
* kein Tool ist in zwei Namespaces (Doppelung).

Ein Waisen-Tool waere nach der Fusion unerreichbar, ein Phantom-op kostet Tokens im
Prompt und scheitert erst zur Laufzeit.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scout import namespaces  # noqa: E402
from scout.shared.tool_registry import collect  # noqa: E402


def _catalog():
    return namespaces.build_catalog(collect())


def _specs():
    return namespaces.build_tool_specs(_catalog(), lambda tool: None)


def test_no_orphan_tools():
    """Jedes registrierte Tool steht in genau einer Domain."""
    catalog = _catalog()
    seen = [tool.name for members in catalog.values() for tool in members]
    assert len(seen) == len(set(seen)), "Tool doppelt im Katalog"
    assert len(seen) == len(list(collect())), "Tool ohne Domain — wird nach der Fusion unerreichbar"


def test_no_phantom_ops():
    """Jeder op im Enum loest auf ein echtes Tool auf."""
    real = {namespaces.short_name(t.name): t.name for t in collect()}
    for spec in _specs():
        for op in spec["schema"]["parameters"]["properties"]["op"]["enum"]:
            assert op in real, f"{spec['name']}: op {op!r} ohne echtes Tool"


def test_no_op_duplicated_within_a_namespace():
    """Ops sind namespace-lokal eindeutig.

    ``start`` existiert bewusst in ``bughunt`` (Session) und ``research`` (Recherche) —
    die Adressierung ist ``<namespace>(op=...)``, also kollisionsfrei.
    """
    total = 0
    for spec in _specs():
        ops = spec["schema"]["parameters"]["properties"]["op"]["enum"]
        assert len(ops) == len(set(ops)), f"{spec['name']}: doppelter op"
        total += len(ops)
    assert total == 50


def test_each_domain_maps_to_its_own_prefix():
    """analysis_* landet in 'analysis', bug_hunt_* in 'bughunt' — keine Kreuzverschiebung."""
    for spec in _specs():
        domain = spec["name"]
        prefixes = namespaces.DOMAIN_PREFIXES[domain]
        for tool in _catalog()[domain]:
            assert tool.name.startswith(prefixes), f"{tool.name} in Domain {domain}"


def test_full_tool_names_also_resolve():
    """Der Dispatcher akzeptiert auch den vollen Namen (Rueckwaertskompatibilitaet)."""
    for spec in _specs():
        domain = spec["name"]
        for tool in _catalog()[domain]:
            handler = spec["handler"]
            result = handler({"op": tool.name})
            # Pflichtparameter fehlen meist -> Fehler, aber NIE 'unbekannter op'
            assert "Unbekannter op" not in str(result), f"{tool.name} ueber {domain} nicht adressierbar"


def test_legacy_coverage_is_empty():
    assert namespaces.legacy_coverage(_catalog(), _specs()) == []
