"""Test _fmt direkt."""
from __future__ import annotations

import sys
from pathlib import Path

_plugins_root = Path(__file__).resolve().parent.parent.parent
if str(_plugins_root) not in sys.path:
    sys.path.insert(0, str(_plugins_root))

# _fmt-Mock aus sys.modules entfernen
sys.modules.pop("_fmt", None)
sys.modules.pop("scout._fmt", None)
