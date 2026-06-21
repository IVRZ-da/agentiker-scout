"""E2E Test Infrastructure for Scout Plugin.

Gate: E2E_TEST=1 environment variable must be set.
Usage: E2E_TEST=1 python3 -m pytest tests/test_e2e/ -v
"""

import os
import sys
import pytest


def pytest_configure(config):
    """Register run_e2e marker and check E2E_TEST gate."""
    config.addinivalue_line("markers", "run_e2e: E2E test requiring real tool dispatch")

    if not os.environ.get("E2E_TEST"):
        pytest.exit("E2E-Tests nur mit E2E_TEST=1 Umgebungsvariable")


@pytest.fixture
def scout_plugin_dir() -> str:
    """Return the scout plugin root directory."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def tmp_test_project(tmp_path):
    """Create a temporary test project with sample files for E2E testing."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "test.py").write_text("""
def hello():
    return "world"

class Calculator:
    def add(self, a, b):
        return a + b
""")
    (tmp_path / "src" / "test.ts").write_text("""
export function greet(name: string): string {
    return `Hello ${name}`;
}
""")
    return tmp_path
