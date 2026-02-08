"""
Service module for Git operations.
"""

import os
import re
import subprocess
import logging
from functools import lru_cache
import pathspec

logger = logging.getLogger(__name__)

# Default to /codebase inside Docker, but fallback to current directory for local testing
CODEBASE_ROOT = os.environ.get("CODEBASE_ROOT", "/codebase")


@lru_cache(maxsize=1)
def _get_remote_url():
    """Attempts to retrieve the git remote origin URL."""
    remote_url = ""

    # 1. Try .git/config (Much faster than subprocess)
    git_config_path = os.path.join(CODEBASE_ROOT, ".git", "config")
    if os.path.exists(git_config_path):
        try:
            with open(git_config_path, "r", encoding="utf-8") as f:
                content = f.read()
            remote_block_match = re.search(
                r'\[remote "origin"\](.*?)(?=\[|$)', content, re.DOTALL
            )
            if remote_block_match:
                block_content = remote_block_match.group(1)
                # Handle quoted and unquoted URLs
                url_match = re.search(r'url\s*=\s*(?:"([^"]+)"|(\S+))', block_content)
                if url_match:
                    # Group 1 is quoted content, Group 2 is unquoted content
                    remote_url = url_match.group(1) or url_match.group(2)
        except OSError as e:
            logger.warning("Failed to parse git config: %s", e)

    # 2. Fallback to git remote get-url origin
    if not remote_url:
        try:
            remote_url_bytes = subprocess.check_output(
                ["git", "remote", "get-url", "origin"],
                cwd=CODEBASE_ROOT,
                stderr=subprocess.DEVNULL,
            )
            remote_url = remote_url_bytes.decode("utf-8").strip()
        except subprocess.CalledProcessError:
            pass
        except FileNotFoundError:
            pass

    return remote_url


def _get_current_branch():
    """Attempts to retrieve the current git branch."""
    branch = "main"  # Default
    try:
        branch_bytes = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=CODEBASE_ROOT,
            stderr=subprocess.DEVNULL,
        )
        branch = branch_bytes.decode("utf-8").strip()
    except subprocess.CalledProcessError:
        pass
    except FileNotFoundError:
        pass
    return branch


@lru_cache(maxsize=1)
def get_repo_info():
    """
    Retrieves Git repository information including project name, branch, and Source ID.
    """
    try:
        remote_url = _get_remote_url()
        branch = _get_current_branch()

        project = "Unknown"
        source_id = ""

        if remote_url:
            if remote_url.endswith(".git"):
                remote_url = remote_url[:-4]

            # Parse user/repo from github url
            # Supports https://github.com/user/repo and git@github.com:user/repo
            match = re.search(r"github\.com[:/]([\w.-]+)/([\w.-]+)", remote_url)
            if match:
                user = match.group(1)
                repo = match.group(2)
                project = f"{user}/{repo}"
                source_id = f"sources/github/{user}/{repo}"
            else:
                project = remote_url.split("/")[-1]

        return {
            "project": project,
            "branch": branch,
            "source_id": source_id,
        }

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error getting repo info: %s", e)
        return {"project": "No Git Repo", "branch": "-", "source_id": ""}


def perform_git_pull():
    """
    Executes 'git pull' in the codebase root.
    """
    logger.info("Starting git pull...")
    try:
        result = subprocess.run(
            ["git", "pull"],
            cwd=CODEBASE_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        logger.debug("Git stdout: %s", result.stdout)
        return {"success": True, "output": result.stdout}
    except subprocess.CalledProcessError as e:
        logger.error("Git stderr: %s", e.stderr)
        return {"success": False, "output": e.stderr or e.stdout}
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Git pull failed: %s", e)
        return {"success": False, "output": str(e)}


@lru_cache(maxsize=1)
def _load_gitignore_spec() -> pathspec.PathSpec:
    """Loads .gitignore patterns and returns a PathSpec."""
    ignore_patterns = [".git/", "__pycache__/", "node_modules/", "venv/", ".env"]
    gitignore_path = os.path.join(CODEBASE_ROOT, ".gitignore")
    if os.path.exists(gitignore_path):
        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                ignore_patterns.extend(f.readlines())
        except OSError as e:
            logger.warning("Failed to read .gitignore: %s", e)
    return pathspec.PathSpec.from_lines("gitwildmatch", ignore_patterns)


def list_files(directory: str = ".") -> list[str]:
    """
    Lists all files in the given directory (recursive), ignoring specific directories.
    Returns a list of relative file paths.
    """
    logger.debug("Scanning files in: %s", CODEBASE_ROOT)
    files_list = []

    # Sanitize directory input to be relative to root
    if directory.startswith("/"):
        directory = directory.lstrip("/")

    base_path = os.path.join(CODEBASE_ROOT, directory)

    if not os.path.exists(base_path):
        return [f"Error: Directory {directory} does not exist."]

    spec = _load_gitignore_spec()

    for root, dirs, files in os.walk(base_path):
        # Calculate relative path from CODEBASE_ROOT to current 'root'
        # This is needed to check ignores which are relative to git root
        rel_root = os.path.relpath(root, CODEBASE_ROOT)
        if rel_root == ".":
            rel_root = ""

        # Filter directories in-place to prevent recursion into ignored ones
        # We iterate over a copy of dirs so we can modify dirs safely
        valid_dirs = []
        for d in dirs:
            # Construct path relative to repo root
            d_path = os.path.join(rel_root, d)
            # Check if directory matches ignore patterns
            # Append slash to ensure it matches directory-only patterns like "dir/"
            if not spec.match_file(d_path + "/"):
                valid_dirs.append(d)

        # Update dirs in-place to prune traversal
        dirs[:] = valid_dirs

        for file in files:
            rel_path = os.path.join(rel_root, file)
            if not spec.match_file(rel_path):
                files_list.append(rel_path)

    logger.debug("Found %d files.", len(files_list))
    return files_list


def read_file(filepath: str, start_line: int = 1, end_line: int = None) -> str:
    """
    Reads and returns the text content of a file.

    Args:
        filepath: The path of the file to read.
        start_line: The line number to start reading from (1-based, inclusive). Defaults to 1.
        end_line: The line number to stop reading at (1-based, inclusive).
                  If None and the file is large (>2000 lines), it truncates to the first 2000 lines.

    Returns:
        The content of the file, potentially truncated or sliced.
    """
    # Sanitize filepath
    if filepath.startswith("/"):
        filepath = filepath.lstrip("/")

    full_path = os.path.abspath(os.path.join(CODEBASE_ROOT, filepath))
    root_abs = os.path.abspath(CODEBASE_ROOT)

    # Security check: Ensure we are still inside CODEBASE_ROOT using commonpath
    try:
        if os.path.commonpath([full_path, root_abs]) != root_abs:
            return "Error: Access denied. Cannot read outside of codebase."
    except ValueError:
        # Can happen on different drives on Windows, essentially outside
        return "Error: Access denied. Cannot read outside of codebase."

    if not os.path.exists(full_path):
        return f"Error: File {filepath} not found."

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            total_lines = len(lines)

            # Determine slice range
            # 1-based indexing for input, 0-based for slicing
            start_idx = max(0, start_line - 1)

            should_truncate = False
            if end_line is None:
                if start_line == 1 and total_lines > 2000:
                    end_idx = 2000
                    should_truncate = True
                else:
                    end_idx = total_lines
            else:
                end_idx = end_line

            # Handle out of bounds gracefully
            if start_idx >= total_lines:
                return ""

            # Python list slicing handles end_idx > len gracefully
            content = "".join(lines[start_idx:end_idx])

            if should_truncate:
                content += (
                    f"\n... [File truncated. Showing lines 1-2000 of {total_lines}. "
                    "Use start_line=2001 to read more.]"
                )

            return content

    except OSError as e:
        return f"Error reading file: {str(e)}"


def get_file_history(filepath: str, max_count: int = 10) -> str:
    """
    Retrieves the git history for a specific file.

    Args:
        filepath: The path of the file to get history for.
        max_count: The maximum number of commits to retrieve. Defaults to 10.

    Returns:
        A string containing the git history, or an error message.
    """
    # Sanitize filepath
    if filepath.startswith("/"):
        filepath = filepath.lstrip("/")

    try:
        # Use git log to get the history
        result = subprocess.run(
            [
                "git",
                "log",
                "-n",
                str(max_count),
                "--pretty=format:%h - %an, %ar : %s",
                "--",
                filepath,
            ],
            cwd=CODEBASE_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout or "No history found for this file."
    except subprocess.CalledProcessError as e:
        logger.error("Git log failed: %s", e.stderr)
        return f"Error retrieving history: {e.stderr or e.stdout}"
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error retrieving file history: %s", e)
        return f"Error retrieving history: {str(e)}"


def get_recent_commits(max_count: int = 10) -> str:
    """
    Retrieves the most recent commits for the repository.

    Args:
        max_count: The maximum number of commits to retrieve. Defaults to 10.

    Returns:
        A string containing the recent commits, or an error message.
    """
    try:
        # Use git log to get the recent commits
        result = subprocess.run(
            [
                "git",
                "log",
                "-n",
                str(max_count),
                "--pretty=format:%h - %an, %ar : %s",
            ],
            cwd=CODEBASE_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout or "No recent commits found."
    except subprocess.CalledProcessError as e:
        logger.error("Git log failed: %s", e.stderr)
        return f"Error retrieving recent commits: {e.stderr or e.stdout}"
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error retrieving recent commits: %s", e)
        return f"Error retrieving recent commits: {str(e)}"


def grep_code(query: str, case_sensitive: bool = False) -> str:
    """
    Searches the codebase for a specific string pattern.
    Uses 'git grep' if available, otherwise falls back to 'grep'.

    Args:
        query: The string to search for.
        case_sensitive: Whether the search should be case-sensitive. Defaults to False.

    Returns:
        A string containing the search results (truncated to 2000 chars), or an error message.
    """
    try:
        # Determine grep command
        # Preferred: git grep -n [-i] "query"
        cmd = ["git", "grep", "-n"]

        if not case_sensitive:
            cmd.append("-i")

        cmd.append(query)

        # Check if we are in a git repo
        is_git_repo = os.path.exists(os.path.join(CODEBASE_ROOT, ".git"))

        if not is_git_repo:
            # Fallback to standard grep: grep -r -n [-i] "query" .
            cmd = ["grep", "-r", "-n"]
            if not case_sensitive:
                cmd.append("-i")
            cmd.append(query)
            cmd.append(".")

        # Execute
        result = subprocess.run(
            cmd,
            cwd=CODEBASE_ROOT,
            capture_output=True,
            text=True,
            check=False,  # Don't raise on grep exit code 1 (no matches)
        )

        output = result.stdout
        if result.returncode > 1:
            # Grep error (exit code 2 usually)
            return f"Error executing grep: {result.stderr or 'Unknown error'}"

        if not output:
            return "No matches found."

        # Truncate
        if len(output) > 2000:
            return output[:2000] + "\n... [Output truncated to 2000 chars]"

        return output

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error searching code: %s", e)
        return f"Error searching code: {str(e)}"
