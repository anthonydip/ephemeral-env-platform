"""
Shared pytest fixtures for all test files.
"""

import pytest


@pytest.fixture
def template_dir():
    """Path to template fixtures directory."""
    return "tests/fixtures/template_renderer"
