"""
Benchmark for RAG indexing performance.
"""

import time
import os
import sys
from unittest.mock import MagicMock, patch

# Add root to path
sys.path.append(os.getcwd())

# pylint: disable=wrong-import-position
from app.services.rag_manager import RAGManager


def benchmark_indexing(num_files=1000):
    """Benchmark the indexing process."""

    # Mock dependencies
    with patch("app.services.rag_manager.chromadb.PersistentClient"), \
            patch("app.services.rag_manager.genai.Client"), \
            patch("os.walk") as mock_walk, \
            patch("builtins.open", new_callable=MagicMock) as mock_open:

        # Setup RAG Manager
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"}):
            manager = RAGManager()

        # Mock collection
        mock_collection = MagicMock()
        manager.collection = mock_collection

        # Simulate DB latency for get()
        def delayed_get(*args, **kwargs):  # pylint: disable=unused-argument
            time.sleep(0.001)  # 1ms latency per query
            # Return empty to simulate new files, or valid structure for existing
            # For this benchmark, let's assume files exist to trigger the check logic
            return {
                "ids": ["file:0"],
                "metadatas": [{"file_hash": "old_hash", "filepath": "test.py"}]
            }

        mock_collection.get.side_effect = delayed_get

        # Mock embeddings to be fast
        # pylint: disable=unused-argument
        def get_embeddings(model, contents):
            resp = MagicMock()
            # Return one embedding per content item
            resp.embeddings = [MagicMock(values=[0.1] * 768) for _ in contents]
            return resp

        manager.genai_client.models.embed_content.side_effect = get_embeddings

        # generate file list
        files = [f"file_{i}.py" for i in range(num_files)]
        mock_walk.return_value = [(".", [], files)]

        # Mock file read
        mock_file = MagicMock()
        mock_file.read.return_value = "print('hello')"
        mock_open.return_value.__enter__.return_value = mock_file

        print(f"Starting benchmark with {num_files} files...")
        start_time = time.time()

        manager.index_codebase()

        end_time = time.time()
        duration = end_time - start_time

        print(f"Time taken: {duration:.4f} seconds")
        print(f"Collection.get call count: {mock_collection.get.call_count}")

        return duration, mock_collection.get.call_count


if __name__ == "__main__":
    benchmark_indexing()
