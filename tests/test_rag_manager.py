import pytest
from unittest.mock import MagicMock, patch
import os

# We need to ensure we can import app
import sys

sys.path.append(os.getcwd())

from app.services.rag_manager import RAGManager, get_rag_manager


@pytest.fixture
def mock_chroma():
    with patch("app.services.rag_manager.chromadb.PersistentClient") as mock:
        yield mock


@pytest.fixture
def mock_genai():
    with patch("app.services.rag_manager.genai.Client") as mock:
        yield mock


def test_rag_manager_initialization(mock_chroma, mock_genai):
    # Ensure env var is set for test
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"}):
        manager = RAGManager()
        assert manager.chroma_client is not None
        assert manager.genai_client is not None


def test_index_codebase(mock_chroma, mock_genai):
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
            with patch("builtins.open", new_callable=MagicMock) as mock_open:
                mock_file = MagicMock()
                mock_file.read.return_value = "print('hello')"
                mock_open.return_value.__enter__.return_value = mock_file

                # Mock collection.get returning empty (new file)
                mock_collection.get.return_value = {"metadatas": []}

                result = manager.index_codebase()

                assert result["status"] == "success"
                assert result["files_indexed"] == 1
                mock_collection.upsert.assert_called_once()


def test_retrieve_context(mock_chroma, mock_genai):
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
        assert "File: test.py" in context
        assert "content" in context


def test_index_codebase_optimization(mock_chroma, mock_genai):
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"}):
        manager = RAGManager()

        mock_collection = MagicMock()
        manager.collection = mock_collection

        # Use simple hash for testing
        with patch.object(manager, "_calculate_hash", return_value="dummy_hash"):

            # Mock os.walk
            with patch("os.walk") as mock_walk:
                mock_walk.return_value = [(".", [], ["test.py"])]
                with patch("builtins.open", new_callable=MagicMock) as mock_open:
                    mock_file = MagicMock()
                    mock_file.read.return_value = "content"
                    mock_open.return_value.__enter__.return_value = mock_file

                    # Case 1: File exists and hash matches
                    mock_collection.get.return_value = {
                        "metadatas": [{"file_hash": "dummy_hash"}]
                    }

                    result = manager.index_codebase()

                    # Should skip upsert and delete
                    mock_collection.upsert.assert_not_called()
                    mock_collection.delete.assert_not_called()
                    assert result["files_indexed"] == 0

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
