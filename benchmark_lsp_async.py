import asyncio
import time
import socket
from unittest.mock import MagicMock, patch
from app.services.lsp_manager import LSPManager
from app.services.lsp_registry import LSPRegistry


async def benchmark_blocking():
    # 1. Setup Mock Registry
    mock_config = {
        "lang1": {
            "connection": "tcp",
            "host": "localhost",
            "port": 12345,  # No server listening here
            "timeout": 10.0,
        },
        "lang2": {
            "connection": "tcp",
            "host": "localhost",
            "port": 12346,  # No server listening here
            "timeout": 10.0,
        },
    }

    manager = LSPManager()
    # Reset singleton state for clean test
    LSPManager._servers = {}

    with patch.object(LSPRegistry, "_config", mock_config):

        async def start_lang(lang, results):
            start_time = time.time()
            print(f"[{lang}] Starting at {start_time}")
            server = await manager.start_server(lang, "/tmp/root")
            end_time = time.time()
            duration = end_time - start_time
            print(f"[{lang}] Finished at {end_time}, duration: {duration}")
            results[lang] = duration

        results = {}

        total_start = time.time()
        # Start both in parallel
        await asyncio.gather(start_lang("lang1", results), start_lang("lang2", results))
        total_end = time.time()

        print(f"\nResults:")
        print(f"Lang 1 duration: {results.get('lang1')}s")
        print(f"Lang 2 duration: {results.get('lang2')}s")
        print(f"Total time: {total_end - total_start}s")


if __name__ == "__main__":
    asyncio.run(benchmark_blocking())
