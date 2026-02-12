import pytest
import os
import json
from fastapi.testclient import TestClient
from app.main import app
from app.services import prompt_manager

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_prompts():
    """Setup and teardown prompts file."""
    # Backup existing
    if os.path.exists(prompt_manager.PROMPTS_FILE):
        os.rename(prompt_manager.PROMPTS_FILE, prompt_manager.PROMPTS_FILE + ".bak")

    # Ensure fresh start
    with open(prompt_manager.PROMPTS_FILE, "w") as f:
        json.dump([], f)

    yield

    # Restore
    if os.path.exists(prompt_manager.PROMPTS_FILE + ".bak"):
        os.replace(prompt_manager.PROMPTS_FILE + ".bak", prompt_manager.PROMPTS_FILE)
    elif os.path.exists(prompt_manager.PROMPTS_FILE):
        os.remove(prompt_manager.PROMPTS_FILE)


def test_get_prompts_empty():
    response = client.get("/prompts")
    assert response.status_code == 200
    assert response.json() == {"prompts": []}


def test_save_prompt():
    prompt = "## Jules Prompt: Test Prompt"
    response = client.post("/prompts", json={"content": prompt})
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verify it's saved
    response = client.get("/prompts")
    assert response.json()["prompts"] == [prompt]


def test_save_duplicate_prompt():
    prompt = "## Jules Prompt: Test Prompt"
    client.post("/prompts", json={"content": prompt})

    response = client.post("/prompts", json={"content": prompt})
    assert response.status_code == 200
    assert response.json()["status"] == "error"

    # Verify still only one
    response = client.get("/prompts")
    assert len(response.json()["prompts"]) == 1


def test_delete_prompt():
    prompts = ["p1", "p2", "p3"]
    for p in prompts:
        client.post("/prompts", json={"content": p})

    # Delete "p2" (index 1)
    response = client.delete("/prompts/1")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    response = client.get("/prompts")
    current_prompts = response.json()["prompts"]
    assert len(current_prompts) == 2
    assert current_prompts == ["p1", "p3"]


def test_delete_invalid_index():
    response = client.delete("/prompts/0")
    assert response.status_code == 404
