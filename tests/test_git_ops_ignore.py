import os
import pytest
from app.services import git_ops

@pytest.fixture
def temp_codebase(tmp_path, mocker):
    """Sets up a temporary codebase root with .gitignore."""
    mocker.patch("app.services.git_ops.CODEBASE_ROOT", str(tmp_path))
    git_ops._load_gitignore_spec.cache_clear()
    yield tmp_path
    git_ops._load_gitignore_spec.cache_clear()

def test_list_files_respects_gitignore(temp_codebase):
    # 1. Setup .gitignore
    gitignore_content = """
ignored_dir/
*.log
secret.txt
"""
    (temp_codebase / ".gitignore").write_text(gitignore_content, encoding="utf-8")

    # 2. Create directory structure

    # Allowed files
    (temp_codebase / "src").mkdir()
    (temp_codebase / "src" / "main.py").write_text("print('hello')", encoding="utf-8")
    (temp_codebase / "README.md").write_text("# README", encoding="utf-8")

    # Ignored directory
    (temp_codebase / "ignored_dir").mkdir()
    (temp_codebase / "ignored_dir" / "should_not_be_seen.txt").write_text("hidden", encoding="utf-8")

    # Ignored file patterns
    (temp_codebase / "error.log").write_text("error", encoding="utf-8")
    (temp_codebase / "src" / "app.log").write_text("log", encoding="utf-8")

    # Specific ignored file
    (temp_codebase / "secret.txt").write_text("secret", encoding="utf-8")

    # 3. Run list_files
    files = git_ops.list_files(".")

    # Normalize files (remove ./ prefix if present)
    files = [f.replace("./", "") if f.startswith("./") else f for f in files]

    # 4. Assertions
    print(f"Files found: {files}")

    # Should contain:
    assert "src/main.py" in files
    assert "README.md" in files
    assert ".gitignore" in files # Usually not ignored unless specified

    # Should NOT contain:
    assert "ignored_dir/should_not_be_seen.txt" not in files
    assert "error.log" not in files
    assert "src/app.log" not in files
    assert "secret.txt" not in files

def test_list_files_default_ignores(temp_codebase):
    """Test that default ignores (like .git) are still respected even without .gitignore."""
    (temp_codebase / ".git").mkdir()
    (temp_codebase / ".git" / "config").write_text("config", encoding="utf-8")

    (temp_codebase / "node_modules").mkdir()
    (temp_codebase / "node_modules" / "package.json").write_text("{}", encoding="utf-8")

    files = git_ops.list_files(".")

    # Normalize files
    files = [f.replace("./", "") if f.startswith("./") else f for f in files]

    assert ".git/config" not in files
    assert "node_modules/package.json" not in files

def test_list_files_nested_ignore(temp_codebase):
    """Test that ignore rules work for nested files."""
    # Case 1: "temp/" should ignore any directory named temp
    (temp_codebase / ".gitignore").write_text("temp/", encoding="utf-8")

    (temp_codebase / "src").mkdir()
    (temp_codebase / "src" / "temp").mkdir()
    (temp_codebase / "src" / "temp" / "data.tmp").write_text("data", encoding="utf-8")

    files = git_ops.list_files(".")
    files = [f.replace("./", "") if f.startswith("./") else f for f in files]

    # "temp/" ignores "src/temp/"
    assert "src/temp/data.tmp" not in files

    # Clear cache because we modified .gitignore
    git_ops._load_gitignore_spec.cache_clear()

    # Case 2: "/temp/" should ONLY ignore root temp
    (temp_codebase / ".gitignore").write_text("/temp/", encoding="utf-8")

    files = git_ops.list_files(".")
    files = [f.replace("./", "") if f.startswith("./") else f for f in files]

    # Should NOT ignore src/temp
    assert "src/temp/data.tmp" in files

    # Check if a root temp exists, it IS ignored
    (temp_codebase / "temp").mkdir()
    (temp_codebase / "temp" / "root.tmp").write_text("root", encoding="utf-8")

    files = git_ops.list_files(".")
    files = [f.replace("./", "") if f.startswith("./") else f for f in files]

    assert "temp/root.tmp" not in files
    assert "src/temp/data.tmp" in files
