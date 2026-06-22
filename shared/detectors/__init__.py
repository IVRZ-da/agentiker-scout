"""Shared detectors subpackage — aufgeteilt aus framework_detector.py.

Submodule:
  - base:            Datentypen, _FileIndex, _compile_glob, _TechDetector
  - catalog:         37 Detector-Instanzen + ALL_DETECTERS
  - dependency_data: Lookup-Tabellen für Dependencies
  - loader:          FrameworkDetector Hauptklasse
  - generic:         GenericDependencyDetector
  - public:          detect_frameworks(), format_profile_summary()
"""

# base
from .base import (
    _GLOB_REGEX_CACHE,
    _YAML_DETECTOR_INSTANCE_CACHE,
    DEFAULT_YAML_RULES_DIR,
    DetectedFramework,
    FrameworkEvidence,
    FrameworkProfile,
    _compile_glob,
    _FileIndex,
    _TechDetector,
)

# catalog
from .catalog import (
    ALL_DETECTORS,
    DJANGO_DETECTOR,
    DOCKER_DETECTOR,
    EXPRESS_DETECTOR,
    FASTAPI_DETECTOR,
    FASTIFY_DETECTOR,
    FORGEJO_ACTIONS_DETECTOR,
    GITHUB_ACTIONS_DETECTOR,
    GO_CHI_DETECTOR,
    GO_DETECTOR,
    GO_FIBER_DETECTOR,
    JAVASCRIPT_DETECTOR,
    JEST_DETECTOR,
    MEDUSA_V2_DETECTOR,
    MEDUSAJ_UI_DETECTOR,
    MONOREPO_NPM_DETECTOR,
    MONOREPO_TURBO_DETECTOR,
    NEXTJS_DETECTOR,
    NGINX_DETECTOR,
    NPM_DETECTOR,
    PLAYWRIGHT_DETECTOR,
    PNPM_DETECTOR,
    POSTGRESQL_DETECTOR,
    PYTHON_DETECTOR,
    REACT_DETECTOR,
    REDIS_DETECTOR,
    RUST_DETECTOR,
    SHADCN_DETECTOR,
    SVELTE_DETECTOR,
    SYSTEMD_DETECTOR,
    TAILWIND_DETECTOR,
    TF_DETECTOR,
    TYPESCRIPT_DETECTOR,
    VITE_DETECTOR,
    VITEST_DETECTOR,
    VUE_DETECTOR,
    YARN_DETECTOR,
)

# dependency_data
from .dependency_data import (
    _DOCKER_IMAGE_MAP,
    _DOTENV_PREFIXES,
    _GO_PREFIXES,
    _KNOWN_PREFIXES,
    _TOP_CARGO,
    _TOP_GO,
    _TOP_NPM,
    _TOP_PYPI,
    _lookup_category,
)

# generic
from .generic import GenericDependencyDetector

# loader
from .loader import FrameworkDetector

# public
from .public import detect_frameworks, format_profile_summary

__all__ = [
    # base
    "FrameworkEvidence",
    "DetectedFramework",
    "FrameworkProfile",
    "_TechDetector",
    "_FileIndex",
    "_compile_glob",
    "_GLOB_REGEX_CACHE",
    "_YAML_DETECTOR_INSTANCE_CACHE",
    "DEFAULT_YAML_RULES_DIR",
    # catalog
    "ALL_DETECTORS",
    "MEDUSA_V2_DETECTOR",
    "NEXTJS_DETECTOR",
    "EXPRESS_DETECTOR",
    "FASTIFY_DETECTOR",
    "GO_DETECTOR",
    "GO_CHI_DETECTOR",
    "GO_FIBER_DETECTOR",
    "FASTAPI_DETECTOR",
    "DJANGO_DETECTOR",
    "REACT_DETECTOR",
    "VUE_DETECTOR",
    "SVELTE_DETECTOR",
    "VITE_DETECTOR",
    "TAILWIND_DETECTOR",
    "SHADCN_DETECTOR",
    "MEDUSAJ_UI_DETECTOR",
    "POSTGRESQL_DETECTOR",
    "REDIS_DETECTOR",
    "TYPESCRIPT_DETECTOR",
    "JAVASCRIPT_DETECTOR",
    "PYTHON_DETECTOR",
    "RUST_DETECTOR",
    "JEST_DETECTOR",
    "VITEST_DETECTOR",
    "PLAYWRIGHT_DETECTOR",
    "DOCKER_DETECTOR",
    "SYSTEMD_DETECTOR",
    "NGINX_DETECTOR",
    "GITHUB_ACTIONS_DETECTOR",
    "FORGEJO_ACTIONS_DETECTOR",
    "NPM_DETECTOR",
    "YARN_DETECTOR",
    "PNPM_DETECTOR",
    "MONOREPO_NPM_DETECTOR",
    "MONOREPO_TURBO_DETECTOR",
    "TF_DETECTOR",
    # dependency_data
    "_DOTENV_PREFIXES",
    "_DOCKER_IMAGE_MAP",
    "_lookup_category",
    "_TOP_NPM",
    "_TOP_PYPI",
    "_TOP_GO",
    "_TOP_CARGO",
    "_KNOWN_PREFIXES",
    "_GO_PREFIXES",
    # loader
    "FrameworkDetector",
    # generic
    "GenericDependencyDetector",
    # public
    "detect_frameworks",
    "format_profile_summary",
]
