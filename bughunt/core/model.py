"""Bug-Hunt Datenmodell — Finding und BugHuntSession.

Finding: Ein einzelnes Bug-Finding (title, severity, file, line, ...)
BugHuntSession: Ein Scan-Durchlauf (findings, status, project)
"""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ======================================================================
# Pfade
# ======================================================================

PLUGIN_DIR = Path(__file__).parent.parent
DATA_DIR = PLUGIN_DIR / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
PATTERNS_DIR = DATA_DIR / "patterns"
CUSTOM_PATTERNS_FILE = PATTERNS_DIR / "custom_patterns.json"
CUSTOM_PREFIX = "CUSTOM_"
MAX_CUSTOM_PATTERNS = 500
MAX_SESSIONS = 100
SESSION_TTL_DAYS = 30

# ======================================================================
# Konstanten
# ======================================================================

SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "INFO": 4}
SEVERITY_VALUES = list(SEVERITY_ORDER.keys())

FINDING_STATUSES = [
    "open", "triaged", "in_progress", "fixed",
    "verified", "false_positive", "wont_fix",
]

FINDING_CATEGORIES = [
    "security", "code-quality", "typescript", "react-next",
    "admin-ui", "performance", "testing", "dependency",
    "database", "other",
]


# ======================================================================
# Datenmodell: Finding
# ======================================================================

class Finding:
    """Ein einzelnes Bug-Finding."""

    def __init__(self, title: str = "", severity: str = "P2",
                 category: str = "other", file: str = "", line: int = 0,
                 description: str = "", evidence: str = "",
                 pattern_id: str = "", suggested_fix: str = "",
                 status: str = "open"):
        self.id = str(uuid.uuid4())[:8]
        self.title = title
        self.severity = severity
        self.category = category
        self.file = file
        self.line = line
        self.description = description
        self.evidence = evidence
        self.pattern_id = pattern_id
        self.suggested_fix = suggested_fix
        self.status = status
        self.notes = ""
        now = datetime.now(timezone.utc).isoformat()
        self.created_at = now
        self.updated_at = now

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "Finding":
        f = cls()
        for k, v in d.items():
            setattr(f, k, v)
        return f

    @staticmethod
    def validate_severity(v: str) -> bool:
        return v.upper() in SEVERITY_VALUES

    @staticmethod
    def validate_status(v: str) -> bool:
        return v in FINDING_STATUSES


# ======================================================================
# Datenmodell: BugHuntSession
# ======================================================================

class BugHuntSession:
    """Eine Bug-Hunt Session (entspricht einem Scan-Durchlauf)."""

    def __init__(self, project: str = "", scope: str = "quick",
                 focus_areas: Optional[list[str]] = None):
        self.session_id = str(uuid.uuid4())[:12]
        self.project = project
        self.scope = scope  # quick, comprehensive, custom
        self.focus_areas = focus_areas or []
        self.findings: list[dict] = []
        self.status = "open"
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.closed_at: Optional[str] = None
        self.summary = ""
        self.scan_count = 0

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "BugHuntSession":
        s = cls()
        for k, v in d.items():
            setattr(s, k, v)
        return s

    def add_finding(self, finding: Finding) -> str:
        """Finding hinzufügen (mit Duplikat-Prüfung).

        Duplikat = gleicher file + line + pattern_id + Status nicht fixed/verified.
        Nur wenn mindestens file oder pattern_id gesetzt ist (sonst kein eindeutiges ID-Merkmal).
        Gibt finding_id zurück (neu oder existierend).
        """
        has_id_fields = bool(finding.file or finding.pattern_id)
        if has_id_fields:
            for existing in self.findings:
                if (existing.get("file") == finding.file
                        and existing.get("line") == finding.line
                        and existing.get("pattern_id") == finding.pattern_id
                        and existing.get("status") not in ("fixed", "verified", "false_positive")):
                    return existing["id"]
        d = finding.to_dict()
        self.findings.append(d)
        return d["id"]

    def update_finding(self, finding_id: str, updates: dict) -> bool:
        """Finding aktualisieren. Returns True bei Erfolg."""
        for existing in self.findings:
            if existing["id"] == finding_id:
                allowed = {"severity", "status", "notes", "suggested_fix", "title", "description"}
                for k, v in updates.items():
                    if k in allowed:
                        existing[k] = v
                existing["updated_at"] = datetime.now(timezone.utc).isoformat()
                return True
        return False

    def get_findings(self, severity: str = None, status: str = None,
                     category: str = None, file: str = None) -> list[dict]:
        """Gefilterte Findings, sortiert nach Severity (P0 zuerst)."""
        results = self.findings
        if severity:
            results = [f for f in results if f.get("severity", "").upper() == severity.upper()]
        if status:
            results = [f for f in results if f.get("status") == status]
        if category:
            results = [f for f in results if f.get("category") == category]
        if file:
            results = [f for f in results if file.lower() in f.get("file", "").lower()]
        return sorted(results, key=lambda x: SEVERITY_ORDER.get(x.get("severity", "P3"), 5))

    def findings_count(self) -> dict[str, int]:
        """Zählung pro Severity."""
        counts = {s: 0 for s in SEVERITY_VALUES}
        for f in self.findings:
            sev = f.get("severity", "P3")
            if sev in counts:
                counts[sev] += 1
        return counts

    def close(self, summary: str = "") -> None:
        """Session als abgeschlossen markieren."""
        self.status = "closed"
        self.closed_at = datetime.now(timezone.utc).isoformat()
        self.summary = summary
