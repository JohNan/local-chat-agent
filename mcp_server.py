#!/usr/bin/env python3
"""
MCP Server for the Gemini CLI integration.
Exposes Python tools as an MCP server using FastMCP.
"""

import sys
import os
import logging
import subprocess
from typing import Optional, Dict

# Ensure we can import from the app package
sys.path.insert(0, os.getcwd())

# pylint: disable=wrong-import-position
from mcp.server.fastmcp import FastMCP
from app.services import git_ops, web_ops, rag_manager

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

mcp = FastMCP("JulesAppServer")


# Tool Registration (Direct)
@mcp.tool()
def list_files(directory: str = ".") -> list[str]:
    """Lists files in the directory."""
    return git_ops.list_files(directory)


@mcp.tool()
def read_file(filepath: str) -> str:
    """Reads a file."""
    return git_ops.read_file(filepath)


@mcp.tool()
def get_file_history(filepath: str) -> str:
    """Gets git history for a file."""
    return git_ops.get_file_history(filepath)


@mcp.tool()
def get_recent_commits() -> str:
    """Gets recent commits."""
    return git_ops.get_recent_commits()


@mcp.tool()
def grep_code(pattern: str) -> str:
    """Searches the codebase for a pattern."""
    return git_ops.grep_code(pattern)


@mcp.tool()
def read_android_manifest() -> str:
    """Reads the Android manifest."""
    return git_ops.read_android_manifest()


@mcp.tool()
def write_to_docs(filename: str, content: str) -> str:
    """Writes to a documentation file."""
    return git_ops.write_to_docs(filename, content)


@mcp.tool()
def write_file_safe(filepath: str, content: str) -> str:
    """Safely overwrites a file with new content."""
    return git_ops.write_file_safe(filepath, content)


@mcp.tool()
def replace_in_file_safe(filepath: str, old_string: str, new_string: str) -> str:
    """Safely replaces the first occurrence of a string in a file."""
    return git_ops.replace_in_file_safe(filepath, old_string, new_string)


@mcp.tool()
def fetch_url(url: str) -> str:
    """Fetches a URL."""
    return web_ops.fetch_url(url)


@mcp.tool()
def run_shell_command(command: str) -> str:
    """
    Runs a shell command and returns the output.
    Useful as a fallback if the built-in shell tool fails for complex redirections.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        output = []
        if result.stdout:
            output.append(result.stdout)
        if result.stderr:
            output.append(f"STDERR:\n{result.stderr}")

        if not output:
            # pylint: disable=line-too-long
            return f"Command '{command}' executed successfully with no output (Exit code: {result.returncode})."
            # pylint: enable=line-too-long

        return "\n".join(output)
    except subprocess.TimeoutExpired:
        return f"Error: Command '{command}' timed out after 120 seconds."
    except Exception as e:  # pylint: disable=broad-exception-caught
        return f"Error executing shell command: {e}"


# Lazy Initialization for LSPManager
_LSP_MANAGER = None  # pylint: disable=invalid-name


def _get_lsp_manager():
    """Lazily initializes the LSPManager."""
    global _LSP_MANAGER  # pylint: disable=global-statement
    if _LSP_MANAGER is None:
        # pylint: disable=import-outside-toplevel
        from app.services.lsp_manager import LSPManager

        _LSP_MANAGER = LSPManager()
    return _LSP_MANAGER


# Proxy Tools for LSP-dependent functions
@mcp.tool()
async def get_definition(file_path: str, line: int, col: int) -> dict:
    """Gets a definition using LSP."""
    _get_lsp_manager()  # Ensure initialization
    return await git_ops.get_definition(file_path, line, col)


@mcp.tool()
def get_file_outline(filepath: str) -> str:
    """Gets a file outline."""
    _get_lsp_manager()  # Ensure initialization
    return git_ops.get_file_outline(filepath)


# Conditional Registration
if os.environ.get("GOOGLE_API_KEY"):

    @mcp.tool()
    def search_codebase_semantic(query: str, filters: Optional[Dict] = None):
        """Searches the codebase semantically."""
        return rag_manager.search_codebase_semantic(query, filters)


def main():
    """Main entry point."""
    logger.info("MCP Server starting...")
    mcp.run()


if __name__ == "__main__":
    main()
