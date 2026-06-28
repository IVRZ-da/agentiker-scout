"""Bug-Hunt Tool Handler — Facade that re-exports from bughunt/tools/ subpackage.

Each handler follows the Hermes Dispatch Contract:
    (args: dict, **kwargs) -> str
"""

from .tools.history import bug_hunt_history  # noqa: F401
from .tools.patterns import bug_hunt_pattern  # noqa: F401
from .tools.scan import (  # noqa: F401
    bug_hunt_fix,
    bug_hunt_scan,
    bug_hunt_verify,
)
from .tools.session import (  # noqa: F401
    bug_hunt_close,
    bug_hunt_export,
    bug_hunt_finding,
    bug_hunt_list,
    bug_hunt_report,
    bug_hunt_start,
    bug_hunt_stats,
    bug_hunt_triage,
)
