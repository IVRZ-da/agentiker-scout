"""Framework Detection Engine — Re-Export Facade.

Aufgeteilt in shared/detectors/ Subpackage für bessere Maintainability.
Dieser Import-Pfad bleibt aus Rückwärtskompatibilität erhalten.
"""
from __future__ import annotations

# ruff: noqa: F401 — alle Imports sind Re-Exports für externe Module
from .detectors.base import (
    _GLOB_REGEX_CACHE,
    _YAML_DETECTOR_INSTANCE_CACHE,
    DetectedFramework,
    FrameworkEvidence,
    FrameworkProfile,
    _compile_glob,
    _FileIndex,
    _TechDetector,
)
from .detectors.catalog import (
    ALL_DETECTORS,
    CPP_DETECTOR,
    FORGEJO_ACTIONS_DETECTOR,
    JAVA_DETECTOR,
    MEDUSA_V2_DETECTOR,
    NEXTJS_DETECTOR,
    RUBY_DETECTOR,
)
from .detectors.dependency_data import (
    _DOCKER_IMAGE_MAP,
    _KNOWN_PREFIXES,
    _TOP_NPM,
    _lookup_category,
)
from .detectors.generic import GenericDependencyDetector
from .detectors.loader import FrameworkDetector
from .detectors.public import detect_frameworks, format_profile_summary

__all__ = [
    "FrameworkEvidence",
    "DetectedFramework",
    "FrameworkProfile",
    "_FileIndex",
    "_GLOB_REGEX_CACHE",
    "_TechDetector",
    "_YAML_DETECTOR_INSTANCE_CACHE",
    "_compile_glob",
    "FrameworkDetector",
    "GenericDependencyDetector",
    "detect_frameworks",
    "format_profile_summary",
    "ALL_DETECTORS",
    "MEDUSA_V2_DETECTOR",
    "NEXTJS_DETECTOR",
    "FORGEJO_ACTIONS_DETECTOR",
    "_DOCKER_IMAGE_MAP",
    "_KNOWN_PREFIXES",
    "_TOP_NPM",
    "_lookup_category",
]
