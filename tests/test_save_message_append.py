import json
import os
import sys
import shutil

TEST_HISTORY_FILE = "test_history_append.json"
os.environ["CHAT_HISTORY_FILE"] = TEST_HISTORY_FILE

# Ensure we can import app
sys.path.append(os.getcwd())

from app.services import chat_manager


def setup_file(content):
    with open(TEST_HISTORY_FILE, "w") as f:
        f.write(content)


def cleanup():
    if os.path.exists(TEST_HISTORY_FILE):
        os.remove(TEST_HISTORY_FILE)


def test_append_to_empty_list():
    print("Running test_append_to_empty_list")
    setup_file("[]")
    chat_manager.CHAT_HISTORY_FILE = TEST_HISTORY_FILE  # Force update just in case
    chat_manager.save_message("user", "test")

    with open(TEST_HISTORY_FILE, "r") as f:
        content = f.read()
        print(f"File content: {content}")
        data = json.loads(content)

    assert len(data) == 1
    assert data[0]["role"] == "user"
    assert data[0]["parts"][0]["text"] == "test"


def test_append_to_non_empty_list():
    print("Running test_append_to_non_empty_list")
    setup_file('[{"role": "model", "parts": [{"text": "hi"}]}]')
    chat_manager.CHAT_HISTORY_FILE = TEST_HISTORY_FILE
    chat_manager.save_message("user", "hello")

    with open(TEST_HISTORY_FILE, "r") as f:
        data = json.load(f)

    assert len(data) == 2
    assert data[0]["parts"][0]["text"] == "hi"
    assert data[1]["parts"][0]["text"] == "hello"


def test_append_creates_file_if_missing():
    print("Running test_append_creates_file_if_missing")
    cleanup()
    chat_manager.CHAT_HISTORY_FILE = TEST_HISTORY_FILE
    chat_manager.save_message("user", "first")

    with open(TEST_HISTORY_FILE, "r") as f:
        data = json.load(f)

    assert len(data) == 1
    assert data[0]["parts"][0]["text"] == "first"


def test_append_with_newline_before_bracket():
    print("Running test_append_with_newline_before_bracket")
    setup_file('[\n  {"role": "user", "parts": [{"text": "one"}]}\n]')
    chat_manager.CHAT_HISTORY_FILE = TEST_HISTORY_FILE
    chat_manager.save_message("model", "two")

    with open(TEST_HISTORY_FILE, "r") as f:
        data = json.load(f)

    assert len(data) == 2
    assert data[1]["parts"][0]["text"] == "two"


def test_fallback_invalid_json():
    print("Running test_fallback_invalid_json")
    # If file is invalid, it should fall back to rewrite (which will likely error or overwrite)
    setup_file("INVALID JSON")
    chat_manager.CHAT_HISTORY_FILE = TEST_HISTORY_FILE
    chat_manager.save_message("user", "rescue")

    with open(TEST_HISTORY_FILE, "r") as f:
        data = json.load(f)

    assert len(data) == 1
    assert data[0]["parts"][0]["text"] == "rescue"


def run_tests():
    try:
        test_append_to_empty_list()
        print("test_append_to_empty_list PASS")

        test_append_to_non_empty_list()
        print("test_append_to_non_empty_list PASS")

        test_append_creates_file_if_missing()
        print("test_append_creates_file_if_missing PASS")

        test_append_with_newline_before_bracket()
        print("test_append_with_newline_before_bracket PASS")

        test_fallback_invalid_json()
        print("test_fallback_invalid_json PASS")

    finally:
        cleanup()


if __name__ == "__main__":
    run_tests()
