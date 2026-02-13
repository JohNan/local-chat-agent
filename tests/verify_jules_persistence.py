import os
import json
import uuid
import time
import threading
import asyncio
import uvicorn
from unittest.mock import MagicMock
from playwright.sync_api import sync_playwright

# Set dummy env vars
os.environ["GOOGLE_API_KEY"] = "dummy"
os.environ["JULES_API_KEY"] = "dummy"

# Import app components
from app.main import app
from app.services import jules_api, git_ops, rag_manager

# Mock git_ops
git_ops.get_repo_info = MagicMock(return_value={"source_id": "dummy", "branch": "main"})

# Mock rag_manager
rag_manager.index_codebase_task = MagicMock()


# Mock jules_api.deploy_to_jules
async def mock_deploy(prompt, repo_info):
    print(f"Mock deploy called with prompt: {prompt[:20]}...", flush=True)
    return {"name": "sessions/mock-session-123"}


jules_api.deploy_to_jules = mock_deploy

BASE_URL = "http://localhost:5000"
CHAT_HISTORY_FILE = "chat_history.json"


def run_server():
    try:
        config = uvicorn.Config(app, host="0.0.0.0", port=5000, log_level="critical")
        server = uvicorn.Server(config)
        server.run()
    except Exception as e:
        print(f"Server error: {e}", flush=True)


def verify_jules_persistence():
    fake_msg = {
        "id": str(uuid.uuid4()),
        "role": "model",
        "parts": [{"text": "## Jules Prompt\nList all files in the repository."}],
    }

    print(f"Injecting fake message into {CHAT_HISTORY_FILE}...", flush=True)
    try:
        if os.path.exists(CHAT_HISTORY_FILE):
            os.remove(CHAT_HISTORY_FILE)
        history = [fake_msg]
        with open(CHAT_HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"Error injecting message: {e}", flush=True)
        exit(1)

    print("Starting backend server...", flush=True)
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(5)

    print("Starting Playwright...", flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.on("console", lambda msg: print(f"BROWSER: {msg.text}", flush=True))
        page.on("pageerror", lambda err: print(f"BROWSER ERROR: {err}", flush=True))

        print(f"Navigating to {BASE_URL}...", flush=True)
        try:
            page.goto(BASE_URL)
        except Exception as e:
            print(f"Failed to load page: {e}", flush=True)
            exit(1)

        print("Waiting for chat interface...", flush=True)
        try:
            page.wait_for_selector(".chat-container", timeout=10000)
        except Exception:
            print("Timeout waiting for .chat-container", flush=True)
            exit(1)

        print("Inspecting buttons...", flush=True)
        try:
            page.wait_for_selector("button.deploy-btn", timeout=5000)
        except:
            print("No deploy buttons found initially.", flush=True)

        btns = page.locator("button.deploy-btn").all()
        print(f"Found {len(btns)} deploy buttons.", flush=True)
        target_btn = None
        for i, b in enumerate(btns):
            text = b.inner_text()
            print(f"Btn {i}: '{text}'", flush=True)
            if "Start Jules Task" in text:
                target_btn = b

        if not target_btn:
            print("Could not find 'Start Jules Task' button.", flush=True)
            exit(1)

        deploy_btn = target_btn
        print("Clicking Deploy button...", flush=True)
        try:
            deploy_btn.click()
        except Exception as e:
            print(f"Click failed: {e}", flush=True)
            deploy_btn.click(force=True)

        print("Waiting for Started status (local update)...", flush=True)
        try:
            started_btn = page.locator("button.deploy-btn", has_text="Started!").last
            started_btn.wait_for(timeout=15000)
            print("Found Started! button.", flush=True)
        except Exception:
            print("Button did not change to Started!.", flush=True)
            exit(1)

        # NOTE: We skip checking confirmation message here because frontend doesn't auto-refresh history.

        print("Reloading page to verify persistence...", flush=True)
        page.reload()
        page.wait_for_selector(".chat-container")

        print("Verifying persistence...", flush=True)

        # Check confirmation message exists
        if (
            page.locator("div.message-bubble:has-text('Started Jules task:')").count()
            > 0
        ):
            print("Confirmation message found after reload.", flush=True)
        else:
            print("Confirmation message NOT found after reload.", flush=True)
            exit(1)

        # Check button state
        try:
            persisted_btn = page.locator("button.deploy-btn", has_text="Started!").last
            persisted_btn.wait_for(timeout=10000)
            if persisted_btn.is_visible():
                print("SUCCESS: Persistence verified.", flush=True)
            else:
                print("FAILURE: Button found but not visible?", flush=True)
                exit(1)
        except Exception:
            print("Could not find Started! button after reload.", flush=True)
            exit(1)

        browser.close()


if __name__ == "__main__":
    verify_jules_persistence()
