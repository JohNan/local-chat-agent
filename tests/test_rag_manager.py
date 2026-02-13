"""
Tests for RAG manager.
"""

# pylint: disable=redefined-outer-name, unused-argument

import os
import sys
import json
from unittest.mock import MagicMock, patch
import pytest

# We need to ensure we can import app

sys.path.append(os.getcwd())

from app.services.rag_manager import RAGManager  # pylint: disable=wrong-import-position


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


def test_rag_manager_initialization(mock_chroma, mock_genai):
    """Test RAG Manager initialization."""
    # Ensure env var is set for test
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"}):
        manager = RAGManager()
        assert manager.chroma_client is not None
        assert manager.genai_client is not None


def test_index_codebase(mock_chroma, mock_genai):
    """Test indexing codebase."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"}):
        manager = RAGManager()

        # Mock collection
        mock_collection = MagicMock()
        manager.collection = mock_collection

        # Mock genai response
        mock_embedding = MagicMock()
        mock_embedding.embeddings = [MagicMock(values=[0.1, 0.2])]
        manager.genai_client.models.embed_content.return_value = mock_embedding

        # Mock os.walk
        with patch("os.walk") as mock_walk:
            mock_walk.return_value = [(".", [], ["test.py"])]

            with patch("os.path.exists") as mock_exists, \
                 patch("os.path.getmtime") as mock_mtime, \
                 patch("os.makedirs"), \
                 patch("builtins.open", new_callable=MagicMock) as mock_open:

                # Setup mocks
                mock_exists.return_value = False # Metadata doesn't exist
                mock_mtime.return_value = 1000.0

                # Mock file open
                # open() is called for:
                # 1. Metadata (skipped if not exists)
                # 2. test.py (read)
                # 3. Metadata (write)

                file_handle = MagicMock()
                file_handle.__enter__.return_value.read.return_value = "print('hello')"

                meta_handle = MagicMock()

                # side_effect for open
                def open_side_effect(filename, *args, **kwargs):
                    if filename.endswith("rag_metadata.json"):
                        return meta_handle
                    return file_handle

                mock_open.side_effect = open_side_effect

                # Mock collection.get returning empty (new file)
                mock_collection.get.return_value = {"metadatas": []}

                result = manager.index_codebase()

                assert result["status"] == "success"
                assert result["files_indexed"] == 1

                # Verify embed_content called with list
                manager.genai_client.models.embed_content.assert_called()
                call_args = manager.genai_client.models.embed_content.call_args
                assert isinstance(call_args.kwargs["contents"], list)
                assert call_args.kwargs["contents"] == ["print('hello')"]

                mock_collection.upsert.assert_called_once()


def test_retrieve_context(mock_chroma, mock_genai):
    """Test retrieving context."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"}):
        manager = RAGManager()

        # Mock collection
        mock_collection = MagicMock()
        manager.collection = mock_collection

        # Mock genai response for query embedding
        mock_embedding = MagicMock()
        mock_embedding.embeddings = [MagicMock(values=[0.1, 0.2])]
        manager.genai_client.models.embed_content.return_value = mock_embedding

        # Mock query result
        mock_collection.query.return_value = {
            "ids": [["id1"]],
            "documents": [["content"]],
            "metadatas": [[{"filepath": "test.py"}]],
        }

        context = manager.retrieve_context("query")

        # Verify embed_content called with list
        call_args = manager.genai_client.models.embed_content.call_args
        assert call_args.kwargs["contents"] == ["query"]

        assert "File: test.py" in context
        assert "content" in context


def test_index_codebase_optimization(mock_chroma, mock_genai):
    """Test indexing optimization (skipping unchanged files based on hash)."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"}):
        manager = RAGManager()

        mock_collection = MagicMock()
        manager.collection = mock_collection

        # Use simple hash for testing
        with patch.object(manager, "_calculate_hash", return_value="dummy_hash"):

            # Mock os.walk
            with patch("os.walk") as mock_walk:
                mock_walk.return_value = [(".", [], ["test.py"])]

                with patch("os.path.exists") as mock_exists, \
                     patch("os.path.getmtime") as mock_mtime, \
                     patch("os.makedirs"), \
                     patch("builtins.open", new_callable=MagicMock) as mock_open:

                    mock_exists.return_value = False # No metadata
                    mock_mtime.return_value = 1000.0

                    file_handle = MagicMock()
                    file_handle.__enter__.return_value.read.return_value = "content"

                    meta_handle = MagicMock()

                    def open_side_effect(filename, *args, **kwargs):
                        if filename.endswith("rag_metadata.json"):
                            return meta_handle
                        return file_handle

                    mock_open.side_effect = open_side_effect

                    # Case 1: File exists and hash matches
                    mock_collection.get.return_value = {
                        "metadatas": [{"file_hash": "dummy_hash"}]
                    }

                    result = manager.index_codebase()

                    # Should skip upsert and delete
                    mock_collection.upsert.assert_not_called()
                    mock_collection.delete.assert_not_called()
                    assert result["files_indexed"] == 0 # Files indexed count increments only if chunked

                    # Case 2: File exists but hash mismatch
                    mock_collection.get.return_value = {
                        "metadatas": [{"file_hash": "old_hash"}]
                    }

                    # Mock embedding for upsert
                    mock_embedding = MagicMock()
                    mock_embedding.embeddings = [MagicMock(values=[0.1])]
                    manager.genai_client.models.embed_content.return_value = (
                        mock_embedding
                    )

                    result = manager.index_codebase()

                    mock_collection.delete.assert_called_with(
                        where={"filepath": "test.py"}
                    )
                    mock_collection.upsert.assert_called_once()
                    assert result["files_indexed"] == 1


def test_index_codebase_batching(mock_chroma, mock_genai):
    """Test batch processing in index_codebase."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"}):
        manager = RAGManager()

        # Mock collection
        mock_collection = MagicMock()
        manager.collection = mock_collection

        # Mock genai response
        mock_embedding = MagicMock()
        mock_embedding.embeddings = [MagicMock(values=[0.1]), MagicMock(values=[0.2])]
        manager.genai_client.models.embed_content.return_value = mock_embedding

        # Mock os.walk returning 2 files
        with patch("os.walk") as mock_walk:
            mock_walk.return_value = [(".", [], ["test1.py", "test2.py"])]

            with patch("os.path.exists") as mock_exists, \
                 patch("os.path.getmtime") as mock_mtime, \
                 patch("os.makedirs"), \
                 patch("builtins.open", new_callable=MagicMock) as mock_open:

                mock_exists.return_value = False
                mock_mtime.return_value = 1000.0

                f1 = MagicMock()
                f1.__enter__.return_value.read.return_value = "content1"

                f2 = MagicMock()
                f2.__enter__.return_value.read.return_value = "content2"

                meta_handle = MagicMock()

                # side effect must handle multiple file opens
                # Calls: open(test1), open(test2), open(meta, w)

                def open_side_effect(filename, *args, **kwargs):
                    if filename.endswith("rag_metadata.json"):
                        return meta_handle
                    if "test1.py" in filename:
                        return f1
                    if "test2.py" in filename:
                        return f2
                    return MagicMock()

                mock_open.side_effect = open_side_effect

                mock_collection.get.return_value = {"metadatas": []}

                result = manager.index_codebase()

                assert result["files_indexed"] == 2

                # Verify embed_content called once with 2 contents (batch)
                manager.genai_client.models.embed_content.assert_called_once()
                call_args = manager.genai_client.models.embed_content.call_args
                assert call_args.kwargs["contents"] == ["content1", "content2"]


def test_index_codebase_incremental(mock_chroma, mock_genai):
    """Test incremental indexing (skipping based on timestamp)."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"}):
        manager = RAGManager()
        manager.collection = MagicMock()

        # Mock os.walk
        with patch("os.walk") as mock_walk:
            mock_walk.return_value = [(".", [], ["test.py"])]

            with patch("os.path.exists") as mock_exists, \
                 patch("os.path.getmtime") as mock_mtime, \
                 patch("os.makedirs"), \
                 patch("builtins.open", new_callable=MagicMock) as mock_open:

                # Setup: Metadata exists and matches
                mock_exists.return_value = True
                mock_mtime.return_value = 12345.0

                metadata = {"test.py": 12345.0}

                meta_handle_read = MagicMock()
                meta_handle_read.__enter__.return_value.read.return_value = json.dumps(metadata)

                meta_handle_write = MagicMock()

                def open_side_effect(filename, *args, **kwargs):
                    if filename.endswith("rag_metadata.json"):
                        mode = args[0] if args else kwargs.get("mode", "r")
                        if "w" in mode:
                            return meta_handle_write
                        return meta_handle_read
                    return MagicMock() # Should not be called for file read if skipped

                mock_open.side_effect = open_side_effect

                # Test Run 1: Timestamp matches
                result = manager.index_codebase()

                assert result["files_indexed"] == 0
                manager.collection.upsert.assert_not_called()

                # Test Run 2: Timestamp mismatch
                mock_mtime.return_value = 67890.0 # Changed

                file_handle = MagicMock()
                file_handle.__enter__.return_value.read.return_value = "content"

                def open_side_effect_2(filename, *args, **kwargs):
                    if filename.endswith("rag_metadata.json"):
                        mode = args[0] if args else kwargs.get("mode", "r")
                        if "w" in mode:
                            return meta_handle_write
                        return meta_handle_read
                    return file_handle

                mock_open.side_effect = open_side_effect_2

                # Need to mock hash check (new content)
                mock_embedding = MagicMock()
                mock_embedding.embeddings = [MagicMock(values=[0.1])]
                manager.genai_client.models.embed_content.return_value = mock_embedding
                manager.collection.get.return_value = {"metadatas": []}

                result = manager.index_codebase()

                assert result["files_indexed"] == 1
                manager.collection.upsert.assert_called_once()

                # Verify metadata save called
                # meta_handle_write.__enter__().write called?
                # json.dump calls .write()
                assert meta_handle_write.__enter__.return_value.write.called
