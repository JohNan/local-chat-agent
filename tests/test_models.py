
import sys
import os
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

# Ensure we can import app from the root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

@pytest.fixture(name="client")
def fixture_client():
    """Fixture to provide a TestClient instance."""
    from app.main import app  # pylint: disable=import-outside-toplevel
    return TestClient(app)

def test_api_models(client, mocker):
    """Test the /api/models endpoint."""
    # Mock the CLIENT in app.main
    mock_client = MagicMock()

    # Mock models
    model1 = MagicMock()
    model1.name = "models/gemini-pro"
    model1.supported_actions = ["generateContent"]

    model2 = MagicMock()
    model2.name = "models/gemini-vision"
    model2.supported_actions = ["generateContent", "otherAction"]

    model3 = MagicMock()
    model3.name = "models/other-model"
    model3.supported_actions = ["generateContent"]

    model4 = MagicMock()
    model4.name = "models/gemini-embedding"
    model4.supported_actions = ["embedContent"]

    mock_client.models.list.return_value = [model1, model2, model3, model4]

    mocker.patch("app.main.CLIENT", mock_client)

    response = client.get("/api/models")
    assert response.status_code == 200
    data = response.json()

    # Should include gemini-pro and gemini-vision, stripped of "models/"
    # Should exclude other-model (doesn't start with gemini-)
    # Should exclude gemini-embedding (no generateContent)

    assert "models" in data
    models = data["models"]
    assert "gemini-pro" in models
    assert "gemini-vision" in models
    assert "other-model" not in models
    assert "gemini-embedding" not in models

def test_api_models_error(client, mocker):
    """Test the /api/models endpoint when an error occurs."""
    mock_client = MagicMock()
    mock_client.models.list.side_effect = Exception("API Error")
    mocker.patch("app.main.CLIENT", mock_client)

    response = client.get("/api/models")
    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert "API Error" in data["error"]
