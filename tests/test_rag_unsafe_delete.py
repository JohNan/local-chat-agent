"""
Tests for verifying safe delete operations in RAG manager.
"""

import os
import sys
from unittest.mock import MagicMock, patch, call
import pytest

# Ensure we can import app
sys.path.append(os.getcwd())

from app.services.rag_manager import RAGManager


@pytest.fixture
def mock_chroma():
    """Mock chroma client."""
    with patch("app.services.rag_manager.chromadb.PersistentClient") as mock:
        yield mock


@pytest.fixture
def mock_genai():
    """Mock genai client."""
    with patch("app.services.rag_manager.genai.Client") as mock:
        yield mock


def test_rag_manager_safe_delete(mock_chroma, mock_genai):
    """
    Test that RAG manager performs upsert BEFORE delete, and only deletes orphaned chunks.
    Scenario:
    - Existing file 'test.py' has 2 chunks: test.py:0, test.py:1
    - New content generates only 1 chunk: test.py:0 (updated content)
    - Expectation:
      - upsert test.py:0
      - delete test.py:1 (orphan)
      - Order: upsert then delete
    """
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"}):
        manager = RAGManager()

        # Mock collection
        mock_collection = MagicMock()
        manager.collection = mock_collection

        # Mock genai response (1 chunk -> 1 embedding)
        mock_embedding = MagicMock()
        mock_embedding.embeddings = [MagicMock(values=[0.1])]
        manager.genai_client.models.embed_content.return_value = mock_embedding

        # Mock existing file in DB (2 chunks)
        # First call: check hash (returns metadata)
        # Second call (impl detail): get all IDs for orphan check
        mock_collection.get.side_effect = [
            # 1. Initial check (limit=1 or just metadatas)
            {
                "ids": ["test.py:0"],
                "metadatas": [{"file_hash": "old_hash", "filepath": "test.py"}]
            },
            # 2. Fetch all IDs for orphan check (if implemented)
            {
                "ids": ["test.py:0", "test.py:1"],
                "metadatas": [{"file_hash": "old_hash"}, {"file_hash": "old_hash"}]
            }
        ]

        # Mock os.walk to find 1 file
        with patch("os.walk") as mock_walk:
            mock_walk.return_value = [(".", [], ["test.py"])]
            with patch("builtins.open", new_callable=MagicMock) as mock_open:
                mock_file = MagicMock()
                mock_file.read.return_value = "new_content" # small content -> 1 chunk
                mock_open.return_value.__enter__.return_value = mock_file

                # Force _chunk_text to return 1 chunk
                with patch.object(manager, "_chunk_text", return_value=["new_chunk"]):
                    manager.index_codebase()

        # Check calls
        upsert_calls = [c for c in mock_collection.mock_calls if c[0] == 'upsert']
        delete_calls = [c for c in mock_collection.mock_calls if c[0] == 'delete']

        # Assert upsert happened
        assert len(upsert_calls) > 0, "Upsert should be called"

        # Assert delete happened
        assert len(delete_calls) > 0, "Delete should be called for orphan"

        # Assert order: All upserts should be before any delete
        # We can check the index of the first delete call relative to the last upsert call
        all_calls = mock_collection.mock_calls
        first_delete_idx = next((i for i, c in enumerate(all_calls) if c[0] == 'delete'), -1)
        last_upsert_idx = next((i for i, c in enumerate(reversed(all_calls)) if c[0] == 'upsert'), -1)
        # reversed index needs conversion
        last_upsert_idx = len(all_calls) - 1 - last_upsert_idx

        assert first_delete_idx > last_upsert_idx, \
            f"Delete (idx {first_delete_idx}) happened before Upsert (idx {last_upsert_idx})! Unsafe!"

        # Assert arguments: delete should be called with ids=['test.py:1'], not where={...}
        # The orphan is test.py:1 because test.py:0 is in new chunks.
        # Wait, if test.py:0 is in new chunks, it is NOT an orphan.
        # So test.py:1 is the only orphan.

        # Check arguments of the delete call
        # mock_calls are (name, args, kwargs)
        _, _, kwargs = delete_calls[0]
        assert "ids" in kwargs, "Delete should be called with 'ids'"
        assert "where" not in kwargs, "Delete should NOT be called with 'where'"
        assert kwargs["ids"] == ["test.py:1"], f"Expected to delete orphan 'test.py:1', got {kwargs['ids']}"
