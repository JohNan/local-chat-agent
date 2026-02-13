"""
RAG Manager Service.
Handles indexing and retrieval of code snippets using ChromaDB and Gemini Embeddings.
"""

import os
import logging
import hashlib
import json
import chromadb
from google import genai

logger = logging.getLogger(__name__)

# Constants
CHROMA_DB_PATH = os.environ.get("CHROMA_DB_PATH", "./chroma_db")
METADATA_PATH = ".rag/rag_metadata.json"
COLLECTION_NAME = "codebase"
# Try 004 first, fallback to 001 if needed.
EMBEDDING_MODEL_PRIMARY = "gemini-embedding-001"
EMBEDDING_MODEL_FALLBACK = "text-embedding-001"


class RAGManager:
    """Manages the vector store and embedding generation."""

    def __init__(self):
        try:
            self.chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
            self.collection = self.chroma_client.get_or_create_collection(
                name=COLLECTION_NAME
            )
            logger.info("ChromaDB initialized at %s", CHROMA_DB_PATH)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to initialize ChromaDB: %s", e)
            self.chroma_client = None
            self.collection = None

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("GOOGLE_API_KEY not set. RAG will not function.")
            self.genai_client = None
        else:
            try:
                self.genai_client = genai.Client(api_key=api_key)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Failed to initialize Gemini Client: %s", e)
                self.genai_client = None

    def _calculate_hash(self, content: str) -> str:
        """Calculates MD5 hash of content."""
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def _get_embeddings(self, texts: list[str]) -> list[list[float]] | None:
        """Generates embeddings for the given list of texts."""
        if not self.genai_client:
            return None

        # Try primary model
        try:
            result = self.genai_client.models.embed_content(
                model=EMBEDDING_MODEL_PRIMARY, contents=texts
            )
            if hasattr(result, "embeddings") and result.embeddings:
                return [e.values for e in result.embeddings]
            return None
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning(
                "Failed to embed with %s: %s. Trying fallback.",
                EMBEDDING_MODEL_PRIMARY,
                e,
            )

            # Try fallback model
            try:
                result = self.genai_client.models.embed_content(
                    model=EMBEDDING_MODEL_FALLBACK, contents=texts
                )
                if hasattr(result, "embeddings") and result.embeddings:
                    return [e.values for e in result.embeddings]
                return None
            except Exception as e2:  # pylint: disable=broad-exception-caught
                logger.error(
                    "Failed to embed with fallback %s: %s", EMBEDDING_MODEL_FALLBACK, e2
                )
                return None

    def index_codebase(self):
        """Indexes the codebase by walking through files."""
        # pylint: disable=too-many-locals, too-many-branches, too-many-statements
        if not self.collection:
            return {"status": "error", "message": "ChromaDB not initialized"}

        logger.info("Starting codebase indexing...")

        # Load metadata
        file_timestamps = {}
        if os.path.exists(METADATA_PATH):
            try:
                with open(METADATA_PATH, "r", encoding="utf-8") as f:
                    file_timestamps = json.load(f)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Failed to load metadata: %s", e)

        files_indexed = 0

        # Basic extensions to include
        valid_extensions = {
            ".py",
            ".js",
            ".ts",
            ".tsx",
            ".java",
            ".kt",
            ".md",
            ".html",
            ".css",
            ".json",
        }

        pending_documents = []
        pending_metadatas = []
        pending_ids = []
        updated_timestamps = {}

        for root, _, files in os.walk("."):
            # Skip common ignore directories
            if any(
                ignore in root
                for ignore in [
                    "venv",
                    ".git",
                    "node_modules",
                    "__pycache__",
                    "chroma_db",
                    "site-packages",
                    ".rag",
                ]
            ):
                continue

            for file in files:
                if not any(file.endswith(ext) for ext in valid_extensions):
                    continue

                filepath = os.path.join(root, file)
                # Normalize path
                filepath = os.path.relpath(filepath, ".")

                try:
                    current_mtime = os.path.getmtime(filepath)

                    # Check if file unchanged based on timestamp
                    if (
                        filepath in file_timestamps
                        and file_timestamps[filepath] == current_mtime
                    ):
                        updated_timestamps[filepath] = current_mtime
                        logger.debug("Skipping unchanged file: %s", filepath)
                        continue

                    # File changed (timestamp diff)
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()

                    file_hash = self._calculate_hash(content)

                    # Check if file already indexed with same hash (content check optimization)
                    # We query for any chunk of this file to check its metadata
                    existing_docs = self.collection.get(
                        where={"filepath": filepath}, limit=1
                    )

                    if existing_docs and existing_docs["metadatas"]:
                        existing_metadata = existing_docs["metadatas"][0]
                        if existing_metadata.get("file_hash") == file_hash:
                            # Content same, just update timestamp
                            updated_timestamps[filepath] = current_mtime
                            continue

                    # File changed or new. Delete existing chunks.
                    self.collection.delete(where={"filepath": filepath})

                    # Chunking
                    chunks = self._chunk_text(content)

                    for i, chunk in enumerate(chunks):
                        chunk_id = f"{filepath}:{i}"
                        pending_ids.append(chunk_id)
                        pending_documents.append(chunk)
                        pending_metadatas.append(
                            {
                                "filepath": filepath,
                                "chunk_index": i,
                                "file_hash": file_hash,
                            }
                        )

                    files_indexed += 1
                    updated_timestamps[filepath] = current_mtime

                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.error("Error indexing file %s: %s", filepath, e)

        # Process batches
        batch_size = 100
        total_chunks = len(pending_documents)
        logger.info("Processing %d chunks in batches of %d", total_chunks, batch_size)

        for i in range(0, total_chunks, batch_size):
            batch_docs = pending_documents[i : i + batch_size]
            batch_ids = pending_ids[i : i + batch_size]
            batch_metas = pending_metadatas[i : i + batch_size]

            try:
                embeddings = self._get_embeddings(batch_docs)
                if embeddings:
                    # Check if we got correct number of embeddings
                    if len(embeddings) != len(batch_docs):
                        logger.error(
                            "Mismatch in embeddings count for batch starting at %d", i
                        )
                        continue

                    self.collection.upsert(
                        ids=batch_ids,
                        embeddings=embeddings,
                        documents=batch_docs,
                        metadatas=batch_metas,
                    )
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error processing batch starting at %d: %s", i, e)

        # Save metadata
        try:
            os.makedirs(os.path.dirname(METADATA_PATH), exist_ok=True)
            with open(METADATA_PATH, "w", encoding="utf-8") as f:
                json.dump(updated_timestamps, f, indent=2)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to save metadata: %s", e)

        logger.info("Indexing complete. Indexed %d files.", files_indexed)
        return {"status": "success", "files_indexed": files_indexed}

    def _chunk_text(
        self, text: str, chunk_size: int = 2000, overlap: int = 200
    ) -> list[str]:
        """Splits text into chunks."""
        if not text:
            return []

        chunks = []
        start = 0
        text_len = len(text)

        if text_len <= chunk_size:
            return [text]

        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunks.append(text[start:end])
            start += chunk_size - overlap

        return chunks

    def retrieve_context(self, query: str, n_results: int = 5) -> str:
        """Retrieves relevant code snippets for a query."""
        if not self.collection:
            return "Error: ChromaDB not initialized."

        embeddings = self._get_embeddings([query])
        if not embeddings or not embeddings[0]:
            return "Error: Could not generate embedding for query."
        embedding = embeddings[0]

        try:
            results = self.collection.query(
                query_embeddings=[embedding], n_results=n_results
            )

            # Format results
            formatted_results = []

            if results and results.get("documents"):
                docs = results["documents"][0]
                metas = results["metadatas"][0]

                for i, doc in enumerate(docs):
                    metadata = metas[i] if i < len(metas) else {}
                    filepath = metadata.get("filepath", "unknown")
                    formatted_results.append(f"File: {filepath}\nContent:\n{doc}\n---")

            if not formatted_results:
                return "No relevant code found."

            return "\n".join(formatted_results)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error retrieving context: %s", e)
            return f"Error during retrieval: {e}"


# Singleton instance
_RAG_MANAGER = None


def get_rag_manager():
    """Returns the singleton RAGManager instance."""
    # pylint: disable=global-statement
    global _RAG_MANAGER
    if _RAG_MANAGER is None:
        _RAG_MANAGER = RAGManager()
    return _RAG_MANAGER


def index_codebase_task():
    """Wrapper for async task."""
    manager = get_rag_manager()
    return manager.index_codebase()


def retrieve_context(query: str):
    """Wrapper for tool call."""
    manager = get_rag_manager()
    return manager.retrieve_context(query)
