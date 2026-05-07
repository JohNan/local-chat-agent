#!/usr/bin/env python3
"""
MCP Server for the Gemini CLI integration.
Exposes Python tools as an MCP server using FastMCP.
"""

import sys
import os
import logging
from typing import Optional, Dict

# Ensure we can import from the app package
sys.path.insert(0, os.getcwd())

from mcp.server.fastmcp import FastMCP
from app.services import git_ops, web_ops, rag_manager

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

mcp = FastMCP("JulesAppServer")

# Tool Registration (Direct)
@mcp.tool()
def list_files(directory: str = ".") -> list[str]:
    return git_ops.list_files(directory)

@mcp.tool()
def read_file(filepath: str) -> str:
    return git_ops.read_file(filepath)

@mcp.tool()
def get_file_history(filepath: str) -> str:
    return git_ops.get_file_history(filepath)

@mcp.tool()
def get_recent_commits() -> str:
    return git_ops.get_recent_commits()

@mcp.tool()
def grep_code(pattern: str) -> str:
    return git_ops.grep_code(pattern)

@mcp.tool()
def read_android_manifest() -> str:
    return git_ops.read_android_manifest()

@mcp.tool()
def write_to_docs(filename: str, content: str) -> str:
    return git_ops.write_to_docs(filename, content)

@mcp.tool()
def fetch_url(url: str) -> str:
    return web_ops.fetch_url(url)

# Lazy Initialization for LSPManager
_lsp_manager = None

def _get_lsp_manager():
    global _lsp_manager
    if _lsp_manager is None:
        from app.services.lsp_manager import LSPManager
        _lsp_manager = LSPManager()
        # Optionally wait for servers to start, but the tools handle it
    return _lsp_manager

# Proxy Tools for LSP-dependent functions
@mcp.tool()
async def get_definition(file_path: str, line: int, col: int) -> dict:
    _get_lsp_manager()  # Ensure initialization
    return await git_ops.get_definition(file_path, line, col)

@mcp.tool()
def get_file_outline(filepath: str) -> str:
    _get_lsp_manager()  # Ensure initialization
    return git_ops.get_file_outline(filepath)

# Conditional Registration
if os.environ.get("GOOGLE_API_KEY"):
    @mcp.tool()
    def search_codebase_semantic(query: str, filters: Optional[Dict] = None):
        return rag_manager.search_codebase_semantic(query, filters)

def main():
    logger.info("MCP Server starting...")
    mcp.run()

if __name__ == "__main__":
    main()
