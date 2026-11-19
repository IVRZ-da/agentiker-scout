"""Uebersetzt alte code_intel-Toolnamen auf die Namespace-Dispatcher.

code_intel 0.6.25 hat seine 70 Einzeltools zu 7 Dispatchern gefaltet
(``code_search``, ``code_lsp``, ``code_graph``, ``code_edit``, ``code_review``,
``code_git``, ``code_meta``) und waehlt die Einzelfunktion ueber ``op``. Die alten
Namen existieren nur noch mit ``CODE_INTEL_NAMESPACES=0``.

Scout ruft an vielen Stellen den alten Namen auf (``code_security_scan``,
``code_symbols``, ...). Mit aktivierten Namespaces liefen diese Aufrufe in ein
"tool not registered" — je nach Aufrufer sichtbar als Fehler oder, schlimmer,
still verschluckt (``except Exception: logger.debug(...)``): der Security-Scan in
``analysis_performance`` fehlte dann einfach im Report.

Deshalb: erst den Namen direkt versuchen, dann den Alias. Kein Treffer → der
Aufruf geht unveraendert raus und der Fehler bleibt sichtbar.
"""

from __future__ import annotations

from typing import Any, Callable

#: Alter Einzelname → (Dispatcher, op). Erzeugt aus code_intel/namespaces.py;
#: ``tests/test_tool_alias.py`` prueft die Tabelle gegen den echten Katalog,
#: wenn das Plugin daneben liegt.
TOOL_ALIASES: dict[str, tuple[str, str]] = {
    # code_search
    "code_symbols": ("code_search", "symbols"),
    "code_overview": ("code_search", "overview"),
    "code_query": ("code_search", "query"),
    "code_search_by_error": ("code_search", "search_by_error"),
    "code_todo_finder": ("code_search", "todo_finder"),
    "code_capsule": ("code_search", "capsule"),
    "code_explain": ("code_search", "explain"),
    # code_lsp
    "code_definition": ("code_lsp", "definition"),
    "code_references": ("code_lsp", "references"),
    "code_hover": ("code_lsp", "hover"),
    "code_implementations": ("code_lsp", "implementations"),
    "code_type_definition": ("code_lsp", "type_definition"),
    "code_type_hierarchy": ("code_lsp", "type_hierarchy"),
    "code_diagnostics": ("code_lsp", "diagnostics"),
    "code_document_symbols": ("code_lsp", "document_symbols"),
    "code_document_links": ("code_lsp", "document_links"),
    "code_completion": ("code_lsp", "completion"),
    "code_signatures": ("code_lsp", "signatures"),
    "code_highlight": ("code_lsp", "highlight"),
    "code_inlay_hints": ("code_lsp", "inlay_hints"),
    "code_inline_values": ("code_lsp", "inline_values"),
    "code_selection_range": ("code_lsp", "selection_range"),
    "code_folding_range": ("code_lsp", "folding_range"),
    "code_semantic_tokens": ("code_lsp", "semantic_tokens"),
    "code_code_lens": ("code_lsp", "code_lens"),
    "code_linked_editing": ("code_lsp", "linked_editing"),
    "code_prepare_rename": ("code_lsp", "prepare_rename"),
    # code_graph
    "code_callers": ("code_graph", "callers"),
    "code_callees": ("code_graph", "callees"),
    "code_call_hierarchy": ("code_graph", "call_hierarchy"),
    "code_blast_radius": ("code_graph", "blast_radius"),
    "code_impact": ("code_graph", "impact"),
    "code_dependency_graph": ("code_graph", "dependency_graph"),
    "code_graph_query": ("code_graph", "graph_query"),
    "code_cycle_detector": ("code_graph", "cycle_detector"),
    "code_hot_paths": ("code_graph", "hot_paths"),
    "code_metrics": ("code_graph", "metrics"),
    "code_complexity": ("code_graph", "complexity"),
    "code_diagram_symbol": ("code_graph", "diagram_symbol"),
    # code_edit
    "code_refactor": ("code_edit", "refactor"),
    "code_batch_refactor": ("code_edit", "batch_refactor"),
    "code_rename": ("code_edit", "rename"),
    "code_replace_body": ("code_edit", "replace_body"),
    "code_insert_before": ("code_edit", "insert_before"),
    "code_insert_after": ("code_edit", "insert_after"),
    "code_move": ("code_edit", "move"),
    "code_safe_delete": ("code_edit", "safe_delete"),
    "code_format": ("code_edit", "format"),
    "code_action": ("code_edit", "action"),
    "code_migration": ("code_edit", "migration"),
    # code_review
    "code_review_assistant": ("code_review", "review_assistant"),
    "code_diff_analysis": ("code_review", "diff_analysis"),
    "code_pr_impact": ("code_review", "pr_impact"),
    "code_security_scan": ("code_review", "security_scan"),
    "code_unused_finder": ("code_review", "unused_finder"),
    "code_duplicates": ("code_review", "duplicates"),
    "code_tests_for_symbol": ("code_review", "tests_for_symbol"),
    # code_git
    "code_git_blame": ("code_git", "git_blame"),
    "code_git_diff_file": ("code_git", "git_diff_file"),
    "code_git_log_symbol": ("code_git", "git_log_symbol"),
    "code_merge_conflict_finder": ("code_git", "merge_conflict_finder"),
    "code_timeline": ("code_git", "timeline"),
    # code_meta
    "code_index": ("code_meta", "index"),
    "code_export": ("code_meta", "export"),
    "code_dependency_risk": ("code_meta", "dependency_risk"),
    "code_workspace_symbols": ("code_meta", "workspace_symbols"),
    "code_workspace_summary": ("code_meta", "workspace_summary"),
    "code_docstring_generate": ("code_meta", "docstring_generate"),
    "code_generate_tests": ("code_meta", "generate_tests"),
}


def resolve_tool_call(
    name: str,
    kwargs: dict[str, Any] | None = None,
    is_available: Callable[[str], bool] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Name + Argumente fuer den Dispatch — ggf. auf den Namespace umgeschrieben.

    Args:
        name: angefordertes Tool (alt oder neu).
        kwargs: Argumente; ``op`` wird bei Bedarf ergaenzt.
        is_available: Praedikat, ob ein Tool registriert ist. Ohne Praedikat
            bleibt der Aufruf unveraendert (reiner Alias-Lookup).

    Returns:
        ``(tool_name, kwargs)``. Ist schon der Namespace-Name angefordert oder
        gibt es keinen Alias, kommen die Eingaben unveraendert zurueck.
    """
    args = dict(kwargs or {})
    alias = TOOL_ALIASES.get(name)
    if alias is None:
        return name, args

    group, op = alias
    if is_available is not None:
        # Namespace aktiv? Dann umschreiben. Ist der Einzelname noch da
        # (CODE_INTEL_NAMESPACES=0), bleibt alles beim Alten.
        if not is_available(group) or is_available(name):
            return name, args

    existing = args.get("op")
    if existing not in (None, "", op):
        # Mischbetrieb: das Argument nennt schon eine andere Operation.
        return name, args
    args["op"] = op
    return group, args


def registry_is_available() -> Callable[[str], bool]:
    """Praedikat gegen lokale **und** Hermes-Registry — wirft nie, meldet nur False.

    Der frueher hier benutzte ``registry.get_entry()`` kennt nur plugin-interne
    Handler. Fuer ein Host-Tool wie ``code_search`` lieferte er deshalb immer
    ``False`` — und ``resolve_tool_call`` schrieb nie auf den Namespace um.
    """

    def _available(tool_name: str) -> bool:
        try:
            from scout.shared.registry import hermes_has_tool, registry

            if registry.get_entry(tool_name) is not None:
                return True
            return hermes_has_tool(tool_name)
        except Exception:  # noqa: BLE001 — Import/Attributfehler = nicht verfuegbar
            return False

    return _available
