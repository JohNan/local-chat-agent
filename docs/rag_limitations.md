# RAG System Limitations and Configuration

This document outlines the rate limiting and model configuration for the RAG (Retrieval-Augmented Generation) system to avoid API quota issues.

## Embedding Models
- **Primary Model:** `text-embedding-004`
- **Fallback Model:** `gemini-embedding-001`

Note: `text-embedding-001` is deprecated and returns 404 in the v1beta API.

## Rate Limits
The Google Gemini API for embeddings is subject to the following limits (configured in `app/services/rag_manager.py`):
- **Tokens Per Minute (TPM):** 1,000
- **Requests Per Minute (RPM):** 3,000

The system uses a thread-safe `RateLimiter` to enforce these limits. Token counts are estimated as `characters / 4`.

## Task Types
To optimize retrieval performance, specific task types are used during embedding generation:
- **Indexing (Documents):** `RETRIEVAL_DOCUMENT`
- **Search (Queries):** `CODE_RETRIEVAL_QUERY`
