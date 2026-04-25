# ADR 001: Vector Store Abstraction

## Status
Proposed

## Context
The current `RAGManager` implementation in `app/services/rag_manager.py` is tightly coupled with ChromaDB. This makes it difficult to:
1. Swap the vector database for other providers (e.g., Qdrant, Pinecone).
2. Unit test the `RAGManager` without a running ChromaDB instance.
3. Manage different indexing strategies independently of the storage layer.

## Decision
We will introduce a `BaseVectorStore` abstract base class (interface) that defines the core operations:
- `add_documents(ids, documents, metadatas)`
- `query(query_text, n_results)`
- `delete(ids)`
- `peek()`

The existing ChromaDB logic will be moved into a concrete implementation called `ChromaVectorStore`.

## Consequences
- **Positive:** Decoupled architecture, easier testing using mocks or in-memory stores.
- **Positive:** Flexibility to support multiple backends.
- **Negative:** Slightly increased complexity due to the abstraction layer.
