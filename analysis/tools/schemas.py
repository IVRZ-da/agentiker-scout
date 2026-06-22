"""tools/schemas.py — Tool-Schemas für Analyse-Tools.

Alle OpenAPI-ähnlichen Schemas für analysis_* Tools.
"""



ANALYSIS_INSPECT_SCHEMA = {
    "name": "analysis_inspect",
    "description": (
        "Multi-step code analysis: symbol extraction → definition → "
        "references → call hierarchy → cycle detection → dependency graph "
        "in one call. Depth 1-5. Persists results in Honcho."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to file or directory to analyze.",
            },
            "symbol": {
                "type": "string",
                "description": "Optional specific symbol (function/class) to focus analysis on.",
            },
            "depth": {
                "type": "integer",
                "description": (
                    "Analysis depth:\n"
                    "  1: symbols + overview + diagnostics\n"
                    "  2: + capsule + callers + callees\n"
                    "  3: + call_hierarchy + type_hierarchy + highlight\n"
                    "  4: + cycle_detector + dependency_graph + hot_paths\n"
                    "  5: + blast_radius + unused_finder + complexity"
                ),
                "default": 2,
                "minimum": 1,
                "maximum": 5,
            },
            "persist": {
                "type": "boolean",
                "description": "Persist results in Honcho (default: true).",
                "default": True,
            },
        },
        "required": ["path"],
    },
}

ANALYSIS_REPORT_SCHEMA = {
    "name": "analysis_report",
    "description": (
        "Generate a structured analysis report from findings and "
        "persist it in Honcho for future reference."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "description": "Analysis scope (e.g. 'module:user-service', 'architecture:checkout').",
            },
            "findings": {
                "type": "object",
                "description": "Key findings from the analysis.",
            },
            "recommendations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional recommendations based on findings.",
            },
            "persist": {
                "type": "boolean",
                "description": "Persist in Honcho (default: true).",
                "default": True,
            },
        },
        "required": ["scope", "findings"],
    },
}

ANALYSIS_ARCHITECTURE_SCHEMA = {
    "name": "analysis_architecture",
    "description": (
        "Full architecture analysis: workspace structure → dependency graph → "
        "hot paths → cycle detection → complexity hotspots. "
        "Persists in Honcho."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to project root directory.",
            },
            "format": {
                "type": "string",
                "enum": ["text", "mermaid", "json"],
                "description": "Output format (default: text).",
                "default": "text",
            },
            "depth": {
                "type": "integer",
                "description": "Analysis depth (1-3).",
                "default": 2,
                "minimum": 1,
                "maximum": 3,
            },
        },
        "required": ["path"],
    },
}

ANALYSIS_DEADCODE_SCHEMA = {
    "name": "analysis_deadcode",
    "description": (
        "Dead code analysis: finds unused imports, unused functions, "
        "orphaned error handlers, and impact analysis for removal."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to file or directory to scan.",
            },
            "kinds": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["imports", "functions", "errors", "all"],
                },
                "description": "What kinds of dead code to find (default: ['all']).",
                "default": ["all"],
            },
            "persist": {
                "type": "boolean",
                "description": "Persist results in Honcho (default: true).",
                "default": True,
            },
        },
        "required": ["path"],
    },
}

ANALYSIS_PERFORMANCE_SCHEMA = {
    "name": "analysis_performance",
    "description": (
        "Performance analysis: finds bottlenecks, complexity hotspots, "
        "and slow paths in a file or project. Combines code_complexity, "
        "code_hot_paths, and code_inlay_hints in one call."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to file or directory to analyze.",
            },
            "persist": {
                "type": "boolean",
                "description": "Persist results in Honcho (default: true).",
                "default": True,
            },
        },
        "required": ["path"],
    },
}

ANALYSIS_SECURITY_SCHEMA = {
    "name": "analysis_security",
    "description": (
        "Security analysis: scans for orphaned error handlers, "
        "vulnerability patterns, and security anti-patterns in source code."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to file or directory to scan.",
            },
            "kinds": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["errors", "vulnerabilities", "all"],
                },
                "description": "What kinds of issues to scan for (default: ['all']).",
                "default": ["all"],
            },
            "persist": {
                "type": "boolean",
                "description": "Persist results in Honcho (default: true).",
                "default": True,
            },
        },
        "required": ["path"],
    },
}

ANALYSIS_ASK_SCHEMA = {
    "name": "analysis_ask",
    "description": (
        "Ask a natural language question about a codebase. Uses "
        "code analysis and Honcho context to answer questions about "
        "code structure, dependencies, and behavior."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "A natural language question about the code.",
            },
            "path": {
                "type": "string",
                "description": "Optional path to file or directory to analyze as context.",
            },
        },
        "required": ["question"],
    },
}

ANALYSIS_DIFF_SCHEMA = {
    "name": "analysis_diff",
    "description": (
        "Compare two analysis results and show what changed. "
        "Accepts report dicts from analysis_inspect, analysis_architecture, or analysis_deadcode. "
        "Returns a structured diff with added/removed/changed findings."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "report_a": {
                "type": "object",
                "description": "First analysis result (dict from analysis_inspect/architecture/deadcode).",
            },
            "report_b": {
                "type": "object",
                "description": "Second analysis result (dict from analysis_inspect/architecture/deadcode).",
            },
            "scope": {
                "type": "string",
                "description": "Optional scope label (e.g. 'module:user-service before/after').",
                "default": "",
            },
            "format": {
                "type": "string",
                "enum": ["text", "json"],
                "description": "Output format (default: text).",
                "default": "text",
            },
        },
        "required": ["report_a", "report_b"],
    },
}

ANALYSIS_TREND_SCHEMA = {
    "name": "analysis_trend",
    "description": (
        "Trend analysis over time: queries Honcho for past analysis results "
        "and shows how metrics (symbol count, unused code, complexity hotspots, "
        "cycles) have changed over days/weeks."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "description": "Scope to analyze (e.g. 'path=src/', 'module:user-service'). Empty = all scopes.",
                "default": "",
            },
            "intent": {
                "type": "string",
                "enum": ["code", "architecture", "deadcode", "report", ""],
                "description": "Filter by analysis intent. Empty = all intents.",
                "default": "",
            },
            "days": {
                "type": "integer",
                "description": "Number of days to look back (default: 30).",
                "default": 30,
                "minimum": 1,
                "maximum": 365,
            },
        },
        "required": [],
    },
}

ANALYSIS_WATCH_SCHEMA = {
    "name": "analysis_watch",
    "description": (
        "Set up or manage an analysis watch (cron job). "
        "Creates a recurring cron job that periodically runs analysis_inspect or "
        "analysis_deadcode on a specified path and reports changes via Hermes cron."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file or directory to watch.",
            },
            "frequency": {
                "type": "string",
                "description": "Cron frequency: 'daily', 'hourly', or a cron expression (default: 'daily').",
                "default": "daily",
            },
            "depth": {
                "type": "integer",
                "description": "Analysis depth for inspect (1-5, default: 2).",
                "default": 2,
                "minimum": 1,
                "maximum": 5,
            },
            "action": {
                "type": "string",
                "enum": ["create", "list", "remove"],
                "description": "Action: create a watch, list active watches, or remove one.",
                "default": "create",
            },
            "name": {
                "type": "string",
                "description": "Watch name (required for remove). Auto-generated for create.",
            },
        },
        "required": ["path"],
    },
}

ANALYSIS_GRAPH_SCHEMA = {
    "name": "analysis_graph",
    "description": (
        "Generate a Mermaid diagram from analysis results. "
        "Takes a report from analysis_inspect, analysis_architecture, or analysis_deadcode "
        "and produces a Mermaid flowchart or graph showing dependencies, cycles, "
        "and hot paths."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "report": {
                "type": "object",
                "description": "Analysis report (from analysis_inspect/architecture/deadcode).",
            },
            "type": {
                "type": "string",
                "enum": ["dependency", "cycles", "summary"],
                "description": "Type of graph to generate (default: dependency).",
                "default": "dependency",
            },
        },
        "required": ["report"],
    },
}


ANALYSIS_UI_GAP_SCHEMA = {
    "name": "analysis_ui_gap",
    "description": (
        "UI Gap Analysis: discovers all UI layers in a project (Next.js storefront, "
        "Medusa admin, API routes, Go handlers), extracts routes and backend modules, "
        "then compares them to identify coverage gaps. "
        "Shows which backend modules lack admin/storefront pages, "
        "which admin pages have no backend module (orphans), "
        "and which CRUD entities are missing detail views."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to project root.",
            },
            "format": {
                "type": "string",
                "enum": ["text", "json", "mermaid"],
                "description": "Output format (default: text).",
                "default": "text",
            },
            "include_storefront": {
                "type": "boolean",
                "description": "Include storefront routes in analysis (default: true).",
                "default": True,
            },
            "include_admin": {
                "type": "boolean",
                "description": "Include admin routes in analysis (default: true).",
                "default": True,
            },
        },
        "required": ["path"],
    },
}

# ======================================================================
# analysis_pattern_discover Schema (P4)
# ======================================================================

ANALYSIS_PATTERN_DISCOVER_SCHEMA = {
    "name": "analysis_pattern_discover",
    "description": (
        "Discover code patterns that look like bugs but aren't covered by "
        "any existing shared pattern. Scans a project for structural anomalies "
        "and compares them against the shared pattern repository. "
        "Returns candidate patterns for registration via bug_hunt_pattern(save)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the project or directory to scan.",
            },
            "scan_language": {
                "type": "string",
                "description": "Optional language filter (e.g. 'python', 'typescript', 'go').",
                "default": "",
            },
            "min_frequency": {
                "type": "integer",
                "description": "Minimum occurrences to consider a pattern meaningful (default: 3).",
                "default": 3,
            },
        },
        "required": ["path"],
    },
}

ANALYSIS_CODE_QUERY_SCHEMA = {
    "name": "analysis_code_query",
    "description": "Smart Query Router für Code-Intelligence. Stellt eine Frage über Code und wählt automatisch das beste Tool.",
    "parameters": {
        "type": "object",
        "properties": {
            "intent": {"type": "string", "description": "What you want: find_usage, definition, understand, overview, tests, diagnostics, callers, callees, structure, search_pattern"},
            "path": {"type": "string", "description": "Absolute file or directory path"},
            "line": {"type": "integer", "description": "Optional 1-based line number"},
            "language": {"type": "string", "description": "Optional language override"},
        },
        "required": ["intent"],
    },
}

ANALYSIS_FRAMEWORK_SCHEMA = {
    "name": "analysis_framework",
    "description": "Zeigt das Framework-Profil eines Projekts an. Erkennt automatisch Technologie-Stack (Medusa, Next.js, React, Go, Docker, etc.) mit Confidence-Scoring und Evidence-Tracking.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absoluter Pfad zum Projekt-Root."},
            "fast": {"type": "boolean", "description": "Wenn True, nur High-Confidence-Marker scannen (schneller).", "default": False}
        },
        "required": ["path"]
    }
}

ANALYSIS_CODE_MOVE_SCHEMA = {
    "name": "analysis_code_move",
    "description": "Verschiebt ein Symbol (Funktion/Klasse) zwischen Dateien via AST-Extraktion.",
    "parameters": {
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Source file path"},
            "symbol": {"type": "string", "description": "Symbol name to move"},
            "target": {"type": "string", "description": "Target file path"},
            "dry_run": {"type": "boolean", "description": "Preview changes without writing (default: True)"},
        },
        "required": ["source", "symbol", "target"],
    },
}
