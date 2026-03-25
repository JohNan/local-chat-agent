import time
import os
import sys
from pathlib import Path

# Add the root directory to sys.path to import app
sys.path.append(str(Path(__file__).parent.parent))

from app.services.prompt_router import (
    load_active_persona,
    save_active_persona,
    clear_active_persona,
)


def benchmark():
    if len(sys.argv) > 1:
        iterations = int(sys.argv[1])
    else:
        iterations = 1000

    print("Setting up baseline...")
    save_active_persona("ARCHITECT")

    # Warm up
    _ = load_active_persona()

    print(f"Running benchmark with {iterations} iterations...")
    start_time = time.time()
    for _ in range(iterations):
        _ = load_active_persona()
    end_time = time.time()

    duration = end_time - start_time
    print(f"Total time: {duration:.6f} seconds")
    print(f"Average time per call: {duration/iterations:.9f} seconds")

    clear_active_persona()
    return duration


if __name__ == "__main__":
    benchmark()
