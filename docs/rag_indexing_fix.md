# RAG Indexing Fix: Correcting Codebase Root

## Issue
The `RAGManager` currently indexes the codebase by walking the current working directory (`.`). In a containerized environment (Docker), the current working directory is `/app`, which contains only the agent's backend code. However, the actual user codebase is mounted at `/codebase` (controlled by the `CODEBASE_ROOT` environment variable).

This results in the RAG manager indexing the agent's own source files (approx. 19-24 files) instead of the user's project files (e.g., +100 Kotlin/TypeScript files).

## Affected Component
- `app/services/rag_manager.py`

## Proposed Changes

### 1. Update Imports
Import `CODEBASE_ROOT` from `app.services.git_ops` into `app/services/rag_manager.py`.

### 2. Refactor `index_codebase`
- Change `os.walk(".")` to `os.walk(CODEBASE_ROOT)`.
- Use `os.path.relpath(..., CODEBASE_ROOT)` to calculate the `filepath` for metadata.
- Ensure that when calling `_process_file_indexing`, the full path is used for reading the file, or the method is updated to handle relative paths by joining them with `CODEBASE_ROOT`.

### 3. Update `_process_file_indexing`
- Ensure `open(filepath, ...)` uses the absolute path if `filepath` is relative.
- Ensure `os.path.getmtime(filepath)` uses the absolute path.

### 4. Consistent Ignoring (Optional but Recommended)
- Make `_load_gitignore_spec` in `app/services/git_ops.py` public (rename to `load_gitignore_spec`).
- Use `load_gitignore_spec()` in `RAGManager.index_codebase` to filter files, ensuring consistency with the `list_files` tool.

### 5. Update Tests
- Update `tests/test_rag_manager.py` to reflect the change from `.` to `CODEBASE_ROOT`.
- Ensure mocks in tests account for the root directory change.
