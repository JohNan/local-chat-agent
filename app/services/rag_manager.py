"""
RAG Manager Service.
Handles indexing and retrieval of code snippets using ChromaDB and Gemini Embeddings.
"""

import os
import logging
import hashlib
import threading
import time
import chromadb
from google import genai
from google.genai import types

from app.services.git_ops import get_repo_info, CODEBASE_ROOT, load_gitignore_spec

logger = logging.getLogger(__name__)

# Constants
CHROMA_DB_PATH = os.environ.get("CHROMA_DB_PATH", "./chroma_db")
COLLECTION_NAME = "company_codebase"
# Try 001 first, fallback to 004 if needed.
EMBEDDING_MODEL_PRIMARY = "gemini-embedding-001"
EMBEDDING_MODEL_FALLBACK = "text-embedding-004"


class RateLimiter:
    """Thread-safe rate limiter using a token bucket algorithm for TPM and RPM."""

    # pylint: disable=too-few-public-methods

    def __init__(self, tpm: int, rpm: int):
        self.tpm = tpm
        self.rpm = rpm
        self.tokens = tpm
        self.requests = rpm
        self.last_update = time.time()
        self.lock = threading.Lock()

    def acquire(self, tokens: int):
        """Waits until enough tokens and requests are available."""
        # Ensure we don't ask for more tokens than the max bucket size
        tokens_to_acquire = min(tokens, self.tpm)

        while True:
            with self.lock:
                now = time.time()
                elapsed = now - self.last_update

                # Replenish tokens and requests based on elapsed time
                self.tokens = min(self.tpm, self.tokens + elapsed * (self.tpm / 60.0))
                self.requests = min(
                    self.rpm, self.requests + elapsed * (self.rpm / 60.0)
                )
                self.last_update = now

                # If enough tokens and requests, consume them and proceed
                if self.tokens >= tokens_to_acquire and self.requests >= 1:
                    self.tokens -= tokens_to_acquire
                    self.requests -= 1
                    return

            # Not enough resources, wait a bit OUTSIDE the lock
            time.sleep(0.1)


class RAGManager:
    """Manages the vector store and embedding generation."""

    def __init__(self):
        self.rate_limiter = RateLimiter(tpm=1000, rpm=3000)

        chroma_host = os.environ.get("CHROMA_HOST")
        chroma_port = os.environ.get("CHROMA_PORT", "8000")

        try:
            if chroma_host:
                self.chroma_client = chromadb.HttpClient(
                    host=chroma_host, port=chroma_port
                )
                logger.info(
                    "ChromaDB initialized via HTTP Client at %s:%s",
                    chroma_host,
                    chroma_port,
                )
                self.collection = self.chroma_client.get_or_create_collection(
                    name=COLLECTION_NAME
                )
                self._migrate_if_needed()
            else:
                self.chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
                logger.info(
                    "ChromaDB initialized via Persistent Client at %s", CHROMA_DB_PATH
                )
                self.collection = self.chroma_client.get_or_create_collection(
                    name=COLLECTION_NAME
                )
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

    def _migrate_if_needed(self):
        """Migrates data from local PersistentClient to shared HttpClient if needed."""
        # pylint: disable=too-many-locals, too-many-branches
        if not os.path.exists(CHROMA_DB_PATH):
            return

        try:
            repo_info = get_repo_info()
            project_name = repo_info.get("project", "Unknown")

            # Check if shared collection already has data for this repo
            existing_shared_data = self.collection.get(
                where={"repo": project_name}, limit=1
            )
            if (
                existing_shared_data
                and existing_shared_data.get("ids") is not None
                and len(existing_shared_data.get("ids")) > 0
            ):
                return  # Data already exists for this repo in shared DB

            logger.info(
                "Starting automatic migration from local ChromaDB to shared server..."
            )
            local_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

            # Since local DB used 'codebase', not 'company_codebase', we might need to handle both
            # Let's check collections
            collections = local_client.list_collections()
            local_collection = None
            for c in collections:
                # The name could be 'codebase' or 'company_codebase'
                if c.name in ("codebase", COLLECTION_NAME):
                    local_collection = local_client.get_collection(c.name)
                    break

            if not local_collection:
                logger.info("No local collection found to migrate.")
                return

            local_data = local_collection.get(
                include=["metadatas", "documents", "embeddings"]
            )
            if (
                not local_data
                or local_data.get("ids") is None
                or len(local_data.get("ids")) == 0
            ):
                return

            ids = local_data["ids"]
            metadatas = local_data["metadatas"]
            documents = local_data["documents"]
            embeddings = local_data.get("embeddings")

            new_metadatas = []
            for meta in metadatas:
                # Ensure the new enriched schema is present
                new_meta = meta.copy() if meta else {}
                new_meta["repo"] = project_name

                filepath = new_meta.get("filepath", "unknown")
                if "language" not in new_meta:
                    _, ext = os.path.splitext(filepath)
                    new_meta["language"] = ext[1:] if ext else "unknown"

                if "start_line" not in new_meta:
                    new_meta["start_line"] = 0
                if "end_line" not in new_meta:
                    new_meta["end_line"] = 0
                if "entity_type" not in new_meta:
                    new_meta["entity_type"] = "chunk"
                if "last_modified" not in new_meta:
                    try:
                        new_meta["last_modified"] = os.path.getmtime(filepath)
                    except Exception:  # pylint: disable=broad-exception-caught
                        new_meta["last_modified"] = 0.0

                new_metadatas.append(new_meta)

            # Perform upsert in batches
            batch_size = 100
            for i in range(0, len(ids), batch_size):
                upsert_kwargs = {
                    "ids": ids[i : i + batch_size],
                    "documents": documents[i : i + batch_size],
                    "metadatas": new_metadatas[i : i + batch_size],
                }
                if embeddings is not None and len(embeddings) > 0:
                    upsert_kwargs["embeddings"] = embeddings[i : i + batch_size]

                self.collection.upsert(**upsert_kwargs)

            logger.info(
                "Successfully migrated %d chunks from local to shared ChromaDB.",
                len(ids),
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error during ChromaDB migration: %s", e)

    def _calculate_hash(self, content: str) -> str:
        """Calculates MD5 hash of content."""
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def _get_embeddings(
        self, texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> list[list[float]] | None:
        """Generates embeddings for the given list of texts."""
        if not self.genai_client:
            return None

        total_characters = sum(len(text) for text in texts)
        tokens = max(1, int(total_characters / 4))
        self.rate_limiter.acquire(tokens)

        # Try primary model
        try:
            result = self.genai_client.models.embed_content(
                model=EMBEDDING_MODEL_PRIMARY,
                contents=texts,
                config=types.EmbedContentConfig(task_type=task_type),
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
                    model=EMBEDDING_MODEL_FALLBACK,
                    contents=texts,
                    config=types.EmbedContentConfig(task_type=task_type),
                )
                if hasattr(result, "embeddings") and result.embeddings:
                    return [e.values for e in result.embeddings]
                return None
            except Exception as e2:  # pylint: disable=broad-exception-caught
                logger.error(
                    "Failed to embed with fallback %s: %s", EMBEDDING_MODEL_FALLBACK, e2
                )
                return None

    def _process_file_indexing(self, filepath, pending_data, existing_info=None):
        """Processes a single file for indexing."""
        # pylint: disable=too-many-locals

        full_path = os.path.join(CODEBASE_ROOT, filepath)

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            file_hash = self._calculate_hash(content)

            existing_ids = set()
            if existing_info:
                if existing_info.get("file_hash") == file_hash:
                    return False  # Skip unchanged file
                existing_ids = existing_info.get("chunk_ids", set())

            # Chunking
            chunks = self._chunk_text(content)
            new_ids = {f"{filepath}:{i}" for i in range(len(chunks))}

            orphaned_ids = list(existing_ids - new_ids)
            if orphaned_ids:
                pending_data["deletions"].extend(orphaned_ids)

            repo_info = get_repo_info()
            project_name = repo_info.get("project", "Unknown")
            _, ext = os.path.splitext(filepath)
            language = ext[1:] if ext else "unknown"

            try:
                last_modified = os.path.getmtime(full_path)
            except Exception:  # pylint: disable=broad-exception-caught
                last_modified = 0.0

            module = filepath.split(os.sep)[0] if os.sep in filepath else "root"

            for i, (chunk, start_line, end_line) in enumerate(chunks):
                chunk_id = f"{filepath}:{i}"
                pending_data["ids"].append(chunk_id)
                pending_data["documents"].append(chunk)
                pending_data["metadatas"].append(
                    {
                        "repo": project_name,
                        "filepath": filepath,
                        "language": language,
                        "start_line": start_line,
                        "end_line": end_line,
                        "entity_type": "chunk",
                        "last_modified": last_modified,
                        "chunk_index": i,
                        "file_hash": file_hash,
                        "module": module,
                    }
                )

            return True

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error indexing file %s: %s", filepath, e)
            return False

    def index_codebase(self):
        """Indexes the codebase by walking through files."""
        # pylint: disable=too-many-locals, too-many-branches, too-many-statements
        if not self.collection:
            return {"status": "error", "message": "ChromaDB not initialized"}

        logger.info("Starting codebase indexing...")

        files_indexed = 0
        valid_extensions = (
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
        )
        ignore_dirs = {
            "venv",
            ".git",
            "node_modules",
            "__pycache__",
            "chroma_db",
            "site-packages",
            "build",
            "dist",
            ".gradle",
            "out",
        }

        pending_data = {
            "documents": [],
            "metadatas": [],
            "ids": [],
            "deletions": [],
        }

        existing_files = self._fetch_existing_metadata()
        spec = load_gitignore_spec()

        for root, dirs, files in os.walk(CODEBASE_ROOT):
            # Calculate relative path from CODEBASE_ROOT to current 'root'
            # pylint: disable=duplicate-code
            rel_root = os.path.relpath(root, CODEBASE_ROOT)
            if rel_root == ".":
                rel_root = ""

            # Filter directories in-place to prevent recursion into ignored ones
            valid_dirs = []
            for d in dirs:
                # Construct path relative to repo root
                d_path = os.path.join(rel_root, d)

                # Check explicit ignore list first
                if d in ignore_dirs:
                    continue

                # Check against .gitignore (append slash for directory match)
                if not spec.match_file(d_path + "/"):
                    valid_dirs.append(d)

            # Update dirs in-place to prune traversal
            dirs[:] = valid_dirs
            # pylint: enable=duplicate-code

            for file in files:
                if file.endswith((".min.js", ".bundle.js")):
                    continue
                if file in ("package-lock.json", "yarn.lock"):
                    continue

                if not file.endswith(valid_extensions):
                    continue

                rel_path = os.path.join(rel_root, file)
                if spec.match_file(rel_path):
                    continue

                filepath = rel_path
                existing_info = existing_files.get(filepath)
                if self._process_file_indexing(filepath, pending_data, existing_info):
                    files_indexed += 1

        # Process batches
        batch_size = 100
        total_chunks = len(pending_data["documents"])
        logger.info("Processing %d chunks in batches of %d", total_chunks, batch_size)

        for i in range(0, total_chunks, batch_size):
            batch_docs = pending_data["documents"][i : i + batch_size]
            batch_ids = pending_data["ids"][i : i + batch_size]
            batch_metas = pending_data["metadatas"][i : i + batch_size]

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

        # Process deletions
        total_deletions = len(pending_data["deletions"])
        if total_deletions > 0:
            logger.info("Processing %d orphaned chunks for deletion", total_deletions)
            for i in range(0, total_deletions, batch_size):
                batch_del_ids = pending_data["deletions"][i : i + batch_size]
                try:
                    self.collection.delete(ids=batch_del_ids)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.error("Error deleting batch starting at %d: %s", i, e)

        logger.info("Indexing complete. Indexed %d files.", files_indexed)
        return {"status": "success", "files_indexed": files_indexed}

    def _fetch_existing_metadata(self) -> dict:
        """Fetches metadata for all existing files to avoid N+1 queries."""
        existing_files = {}
        try:
            all_docs = self.collection.get(include=["metadatas"])
            if all_docs and all_docs.get("ids") and all_docs.get("metadatas"):
                for doc_id, meta in zip(all_docs["ids"], all_docs["metadatas"]):
                    fp = meta.get("filepath")
                    if not fp:
                        continue
                    if fp not in existing_files:
                        existing_files[fp] = {
                            "file_hash": meta.get("file_hash"),
                            "chunk_ids": set(),
                        }
                    existing_files[fp]["chunk_ids"].add(doc_id)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error fetching existing metadata: %s", e)
        return existing_files

    def _chunk_text(
        self, text: str, chunk_size: int = 2000, overlap: int = 200
    ) -> list[tuple[str, int, int]]:
        """Splits text into chunks, returning (chunk_text, start_line, end_line)."""
        if not text:
            return []

        chunks = []
        start = 0
        text_len = len(text)

        if text_len <= chunk_size:
            start_line = 1
            end_line = text.count("\n") + 1
            return [(text, start_line, end_line)]

        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunk = text[start:end]
            start_line = text[:start].count("\n") + 1
            end_line = start_line + chunk.count("\n")
            chunks.append((chunk, start_line, end_line))
            start += chunk_size - overlap

        return chunks

    def clear_repo_index(self):
        """Clears the RAG index for the current repository."""
        if not self.collection:
            logger.error("Cannot clear index: ChromaDB not initialized")
            return {"status": "error", "message": "ChromaDB not initialized"}

        try:
            repo_info = get_repo_info()
            project_name = repo_info.get("project", "Unknown")

            logger.info("Clearing RAG index for project: %s", project_name)
            self.collection.delete(where={"repo": project_name})

            return {"status": "success", "message": f"Index cleared for {project_name}"}
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error clearing repo index: %s", e)
            return {"status": "error", "message": str(e)}

    def search_codebase_semantic(
        self, query: str, n_results: int = 5, filters: dict = None
    ) -> str:
        """Retrieves relevant code snippets for a query."""
        # pylint: disable=too-many-locals
        if not self.collection:
            return "Error: ChromaDB not initialized."

        embeddings = self._get_embeddings([query], task_type="CODE_RETRIEVAL_QUERY")
        if not embeddings or not embeddings[0]:
            return "Error: Could not generate embedding for query."
        embedding = embeddings[0]

        try:
            query_kwargs = {"query_embeddings": [embedding], "n_results": n_results}
            if filters:
                query_kwargs["where"] = filters

            results = self.collection.query(**query_kwargs)

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


def clear_repo_index():
    """Wrapper for clearing the repo index."""
    manager = get_rag_manager()
    return manager.clear_repo_index()


def search_codebase_semantic(query: str, filters: dict = None):
    """
    Searches the codebase using semantic vector embeddings.
    Use this tool to find relevant code snippets based on natural language queries,
    high-level concepts, or functionality descriptions (e.g., 'how does auth work',
    'user login logic').
    Optionally accepts complex metadata filters using Chroma's syntax.
    """
    manager = get_rag_manager()
    return manager.search_codebase_semantic(query, filters=filters)
