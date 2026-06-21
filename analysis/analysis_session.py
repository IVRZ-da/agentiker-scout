"""analysis_session — Analyse-Session-State für das Analyse-Plugin.

Bietet:
  - AnalysisSession: Session-State mit Active-Flag, Intent, Tools, Files, Findings
  - Globaler Session-State (_analysis_session)
  - Honcho-Cache (_honcho_cache)
"""


import logging
import time
from typing import Any, Dict, List, Set

logger = logging.getLogger("analysis")


# ---------------------------------------------------------------------------
# Analyse-Session-State (pro Prozess)
# ---------------------------------------------------------------------------

class AnalysisSession:
    """Tracks the current analysis session state."""

    def __init__(self):
        self.active: bool = False
        self.intent: str = ""          # "code", "architecture", "deadcode", "db", "web", "bug", "performance"
        self.tools_used: List[Dict[str, Any]] = []
        self.files_analyzed: Set[str] = set()
        self.findings: Dict[str, Any] = {}
        self.started_at: float = 0.0
        self.original_query: str = ""

    def start(self, intent: str, query: str) -> None:
        self.active = True
        self.intent = intent
        self.original_query = query
        self.tools_used = []
        self.files_analyzed = set()
        self.findings = {}
        self.started_at = time.monotonic()
        logger.debug("analysis session started: intent=%s", intent)

    def reset(self) -> None:
        self.active = False
        self.intent = ""
        self.tools_used = []
        self.files_analyzed = set()
        self.findings = {}
        self.started_at = 0.0
        self.original_query = ""

    def add_tool_call(self, name: str, args_summary: str, duration_ms: int, status: str) -> None:
        self.tools_used.append({
            "name": name,
            "args": args_summary,
            "duration_ms": duration_ms,
            "status": status,
        })

    def add_file(self, path: str) -> None:
        if path:
            self.files_analyzed.add(path)


# Globaler Session-State (Singleton — pro Prozess)
_analysis_session = AnalysisSession()
_honcho_cache: Dict[str, tuple[str, float]] = {}
