"""
Benchmark script for history operations.
"""

import time
import json
import os
import sys

# Add root to path
sys.path.append(os.getcwd())

# pylint: disable=wrong-import-position
from app.services import chat_manager

# Setup
HISTORY_FILE = "benchmark_history.json"
os.environ["CHAT_HISTORY_FILE"] = HISTORY_FILE


def setup_history(n=1000):
    """Setup initial history file."""
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)

    history = []
    for i in range(n):
        history.append({"role": "user", "parts": [{"text": f"Message {i}"}]})

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f)


def benchmark_save_message(iterations=100):
    """Benchmark the save_message function."""
    start_time = time.time()
    for i in range(iterations):
        chat_manager.save_message("user", f"New Message {i}")
    end_time = time.time()
    return end_time - start_time


def main():
    """Main function."""
    print("Preparing benchmark...")
    # Start with a decent size history
    setup_history(n=50000)
    initial_size = os.path.getsize(HISTORY_FILE)
    print(f"Initial file size: {initial_size / 1024:.2f} KB")

    print("Running benchmark...")
    iterations = 20
    duration = benchmark_save_message(iterations=iterations)
    print(f"Time taken for {iterations} saves: {duration:.4f} seconds")
    print(f"Average time per save: {duration/iterations:.4f} seconds")

    # Cleanup
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)


if __name__ == "__main__":
    main()
