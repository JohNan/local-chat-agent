"""
Tests for API settings endpoints.
"""
import os
import sys
from fastapi.testclient import TestClient

# Ensure we can import app from the root
sys.path.append(os.getcwd())
# pylint: disable=wrong-import-position
from app.main import app

client = TestClient(app)

def test_api_settings_persistence(clean_db):  # pylint: disable=unused-argument
    """
    Test that the API can save and retrieve settings.
    """
    # 1. Get initial settings
    response = client.get("/api/settings")
    assert response.status_code == 200
    initial_data = response.json()
    assert "model" in initial_data

    # 2. Set new model
    new_model = "gemini-2.0-flash-exp"
    # Ensure we are changing the model
    if initial_data["model"] == new_model:
        new_model = "gemini-3-pro-preview"

    response = client.post("/api/settings", json={"model": new_model})
    assert response.status_code == 200
    assert response.json()["model"] == new_model

    # 3. Verify persistence via GET
    response = client.get("/api/settings")
    assert response.status_code == 200
    assert response.json()["model"] == new_model
