
import time
import threading
import socket
from unittest.mock import MagicMock, patch
from app.services.lsp_manager import LSPManager
from app.services.lsp_registry import LSPRegistry

def benchmark_blocking():
    # 1. Setup Mock Registry
    mock_config = {
        "lang1": {
            "connection": "tcp",
            "host": "localhost",
            "port": 12345, # No server listening here
            "timeout": 10.0
        },
        "lang2": {
            "connection": "tcp",
            "host": "localhost",
            "port": 12346, # No server listening here
            "timeout": 10.0
        }
    }

    manager = LSPManager()
    # Reset singleton state for clean test
    LSPManager._servers = {}

    with patch.object(LSPRegistry, "_config", mock_config):
        def start_lang(lang, results):
            start_time = time.time()
            print(f"[{lang}] Starting at {start_time}")
            server = manager.start_server(lang, "/tmp/root")
            end_time = time.time()
            duration = end_time - start_time
            print(f"[{lang}] Finished at {end_time}, duration: {duration}")
            results[lang] = duration

        results = {}
        t1 = threading.Thread(target=start_lang, args=("lang1", results))
        t2 = threading.Thread(target=start_lang, args=("lang2", results))

        total_start = time.time()
        t1.start()
        time.sleep(0.1) # Ensure t1 starts first
        t2.start()

        t1.join()
        t2.join()
        total_end = time.time()

        print(f"\nResults:")
        print(f"Lang 1 duration: {results.get('lang1')}s")
        print(f"Lang 2 duration: {results.get('lang2')}s")
        print(f"Total time: {total_end - total_start}s")

        # If it's blocking, Lang 2 should take roughly (Lang 1 duration - 0.1)
        # and Total time should be Lang 1 duration + Lang 2 duration (roughly)
        # If it's non-blocking, Lang 2 should take roughly 5s (retry loop)
        # and Total time should be roughly 5s.

if __name__ == "__main__":
    benchmark_blocking()
