import os
import re
import subprocess
import logging

logger = logging.getLogger(__name__)

# Default to /codebase inside Docker, but fallback to current directory for local testing
CODEBASE_ROOT = os.environ.get("CODEBASE_ROOT", "/codebase")


def get_repo_info():
    """
    Retrieves Git repository information including project name, branch, and Source ID.
    """
    try:
        remote_url = ""
        # 1. Try git remote get-url origin
        try:
            remote_url_bytes = subprocess.check_output(
                ["git", "remote", "get-url", "origin"],
                cwd=CODEBASE_ROOT,
                stderr=subprocess.DEVNULL,
            )
            remote_url = remote_url_bytes.decode("utf-8").strip()
        except Exception:
            pass

        # 2. Fallback to .git/config
        if not remote_url:
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
                        url_match = re.search(r"url\s*=\s*(\S+)", block_content)
                        if url_match:
                            remote_url = url_match.group(1)
                except Exception as e:
                    logger.warning(f"Failed to parse git config: {e}")

        project = "Unknown"
        branch = "main"  # Default

        # Get current branch
        try:
            branch_bytes = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=CODEBASE_ROOT,
                stderr=subprocess.DEVNULL,
            )
            branch = branch_bytes.decode("utf-8").strip()
        except Exception:
            pass

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

    except Exception as e:
        logger.error(f"Error getting repo info: {e}")
        return {"project": "No Git Repo", "branch": "-", "source_id": ""}


def perform_git_pull():
    logger.info("Starting git pull...")
    try:
        result = subprocess.run(
            ["git", "pull"],
            cwd=CODEBASE_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        logger.debug(f"Git stdout: {result.stdout}")
        return {"success": True, "output": result.stdout}
    except subprocess.CalledProcessError as e:
        logger.error(f"Git stderr: {e.stderr}")
        return {"success": False, "output": e.stderr or e.stdout}
    except Exception as e:
        logger.error(f"Git pull failed: {e}")
        return {"success": False, "output": str(e)}


def list_files(directory: str = ".") -> list[str]:
    """
    Lists all files in the given directory (recursive), ignoring specific directories.
    Returns a list of relative file paths.
    """
    logger.debug(f"Scanning files in: {CODEBASE_ROOT}")
    files_list = []

    # Sanitize directory input to be relative to root
    if directory.startswith("/"):
        directory = directory.lstrip("/")

    base_path = os.path.join(CODEBASE_ROOT, directory)

    if not os.path.exists(base_path):
        return [f"Error: Directory {directory} does not exist."]

    for root, dirs, files in os.walk(base_path):
        # Ignore directories
        dirs[:] = [
            d
            for d in dirs
            if d not in {".git", "__pycache__", "node_modules", "venv", ".env"}
        ]

        for file in files:
            full_path = os.path.join(root, file)
            # Get relative path from CODEBASE_ROOT
            rel_path = os.path.relpath(full_path, CODEBASE_ROOT)
            files_list.append(rel_path)

    logger.debug(f"Found {len(files_list)} files.")
    return files_list


def read_file(filepath: str) -> str:
    """
    Reads and returns the text content of a file.
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
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"
