"""Scout Shared Domain — Gemeinsame Infrastruktur.

Enthält Registry, Cache, Intent-Erkennung, Pattern-Pipeline und Framework-Detection.
"""

from scout.shared import cache as cache
from scout.shared import dependency_scanner as dependency_scanner
from scout.shared import framework_detector as framework_detector
from scout.shared import intent as intent
from scout.shared import pattern_loader as pattern_loader
from scout.shared import patterns as patterns
from scout.shared import registry as registry

__all__ = [
    "registry",
    "intent",
    "cache",
    "patterns",
    "framework_detector",
    "dependency_scanner",
    "pattern_loader",
]
