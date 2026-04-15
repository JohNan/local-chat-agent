"""
Tests for system settings endpoints in app/routers/system.py.
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure we can import app from the root
sys.path.append(os.getcwd())

from app.main import app
from app.config import DEFAULT_MODEL

client = TestClient(app)


def test_get_settings_default(clean_db):
    """
    Test that GET /api/settings returns DEFAULT_MODEL when no setting is stored.
    """
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["model"] == DEFAULT_MODEL


def test_save_and_get_settings(clean_db):
    """
    Test that POST /api/settings saves the model and GET /api/settings retrieves it.
    """
    new_model = "gemini-2.0-flash"

    # 1. Save setting
    response = client.post("/api/settings", json={"model": new_model})
    assert response.status_code == 200
    assert response.json() == {"status": "updated", "model": new_model}

    # 2. Verify via GET
    response = client.get("/api/settings")
    assert response.status_code == 200
    assert response.json()["model"] == new_model


def test_save_settings_invalid_data(clean_db):
    """
    Test that POST /api/settings with invalid data returns 422.
    """
    # Missing 'model' field
    response = client.post("/api/settings", json={"not_a_model": "value"})
    assert response.status_code == 422


def test_save_settings_update(clean_db):
    """
    Test that updating an existing setting works correctly.
    """
    model1 = "model-v1"
    model2 = "model-v2"

    # Save first model
    client.post("/api/settings", json={"model": model1})

    # Update to second model
    response = client.post("/api/settings", json={"model": model2})
    assert response.status_code == 200
    assert response.json()["model"] == model2

    # Verify GET returns second model
    response = client.get("/api/settings")
    assert response.json()["model"] == model2
