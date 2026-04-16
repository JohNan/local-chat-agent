import asyncio
import os
import time
from unittest.mock import MagicMock, patch
from app.services.lsp_manager import LSPManager


async def benchmark_walk():
    manager = LSPManager()

    # Mock registry
    with patch("app.services.lsp_manager.LSPRegistry") as mock_registry_cls:
        mock_registry = mock_registry_cls.return_value
        mock_registry._config = {
            f"lang_{i}": {"extensions": [f".ext_{i}"]} for i in range(10)
        }

        # Mock start_server to avoid actually starting processes
        with patch.object(LSPManager, "start_server", return_value=None):

            # We want to measure how much it blocks the event loop.
            # We can run a background task that increments a counter.

            counter = 0
            stop_counter = False

            async def increment_counter():
                nonlocal counter
                while not stop_counter:
                    counter += 1
                    await asyncio.sleep(0)

            # Mock os.walk to simulate a large directory structure
            num_dirs = 1000
            num_files_per_dir = 100

            mock_walk_data = []
            for i in range(num_dirs):
                files = [f"file_{j}.noext" for j in range(num_files_per_dir)]
                mock_walk_data.append((f"dir_{i}", [], files))

            with patch("os.walk", return_value=mock_walk_data):
                print("Starting benchmark...")

                counter_task = asyncio.create_task(increment_counter())

                start_time = time.perf_counter()
                await manager.start_supported_servers(".")
                end_time = time.perf_counter()

                stop_counter = True
                await counter_task

                duration = end_time - start_time
                print(f"Time taken: {duration:.4f} seconds")
                print(f"Event loop yield count (counter): {counter}")

                # If it's blocking, counter will be low.
                # If it's non-blocking (e.g. using to_thread), counter should be higher
                # because it yields back to the event loop while waiting for the thread.
                # Actually, os.walk itself is blocking, so if we just call it in the loop,
                # the counter won't increment at all during the walk.


if __name__ == "__main__":
    asyncio.run(benchmark_walk())
