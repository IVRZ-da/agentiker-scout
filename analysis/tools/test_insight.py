"""analysis_test_insight Tool — Testabdeckungs-Analyse.

Nutzt code_tests_for_symbol + code_generate_tests.
"""
from __future__ import annotations

import logging
from typing import Any

from scout._fmt import fmt_err, fmt_ok

from .base import _call_tool, _validate_and_resolve_path

logger = logging.getLogger("analysis")


def analysis_test_insight_tool(args: dict, **kwargs) -> str:
    """Analysiert Testabdeckung eines Symbols/Projekts."""
    path = args.get("path", "")
    symbol = args.get("symbol", "")
    generate = args.get("generate", False)

    path_error, resolved_path = _validate_and_resolve_path(path)
    if path_error:
        return fmt_err(f"{path_error} (path: {path})")
    path = resolved_path

    result: dict[str, Any] = {
        "path": path,
        "symbol": symbol or None,
        "tests_found": [],
        "generated_scaffolds": [],
    }

    if symbol:
        # Symbol-spezifische Analyse
        try:
            syms = _call_tool("code_symbols", path=path, pattern=symbol, max_results=50)
            line = 1
            if isinstance(syms, dict):
                for s in syms.get("symbols", []):
                    if s.get("name") == symbol:
                        line = s.get("line", 1)
                        break

            tests = _call_tool("code_tests_for_symbol", path=path, line=line)
            if tests:
                if isinstance(tests, dict):
                    files = tests.get("test_files", tests.get("files", []))
                    if isinstance(files, list):
                        result["tests_found"] = [
                            {"file": f.get("file", f.get("path", str(f)))[:80],
                             "type": f.get("type", "test")}
                            for f in files[:10]
                        ]
        except Exception as e:
            logger.debug("code_tests_for_symbol skipped: %s", e)

        if generate:
            try:
                scaffold = _call_tool("code_generate_tests", path=path, line=line)
                if scaffold:
                    result["generated_scaffolds"] = [str(scaffold)[:500]]
            except Exception as e:
                logger.debug("code_generate_tests skipped: %s", e)

    # Summary
    parts = [f"🧪 Test-Insight für {path}"]
    if symbol:
        parts.append(f"  Symbol: {symbol}")
    parts.append(f"  Tests gefunden: {len(result['tests_found'])}")
    if result["generated_scaffolds"]:
        parts.append(f"  Generierte Scaffolds: {len(result['generated_scaffolds'])}")
    result["summary"] = "\n".join(parts)

    return fmt_ok(result)
