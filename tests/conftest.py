"""Shared fixtures for tests."""

import sys
import os
import pytest
from fastapi.testclient import TestClient

# Ensure app is importable
sys.path.append(os.getcwd())

# Import app directly from main
# pylint: disable=wrong-import-position
from app.main import app


@pytest.fixture(name="client")
def fixture_client():
    """Fixture to provide a TestClient instance."""
    return TestClient(app)
