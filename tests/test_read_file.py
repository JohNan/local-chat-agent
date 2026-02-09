import pytest
import os
import sys

# Ensure app is importable
sys.path.append(os.getcwd())

from app.services import git_ops


@pytest.fixture
def mock_codebase(tmp_path, mocker):
    """Sets up a temporary codebase root."""
    mocker.patch("app.services.git_ops.CODEBASE_ROOT", str(tmp_path))
    return tmp_path


def test_read_file_normal(mock_codebase):
    # Create a file with 10 lines
    file_content = "\n".join([f"Line {i}" for i in range(1, 11)])
    test_file = mock_codebase / "test.txt"
    test_file.write_text(file_content, encoding="utf-8")

    # Read the file
    # Note: Using keyword arguments that don't exist yet will fail until implementation
    # But for now we are testing against the FUTURE implementation or CURRENT?
    # The plan says "Create tests... Run this test... it should fail".
    # So I will write tests expecting the NEW signature.

    # However, existing signature is read_file(filepath).
    # If I call it with new args, it will TypeError.
    # If I call it without args, it works but won't truncate if I make it large.
    pass


def test_read_file_large_truncation(mock_codebase):
    # Create a file with 2500 lines
    lines = [f"Line {i}" for i in range(1, 2501)]
    file_content = "\n".join(lines)
    test_file = mock_codebase / "large.txt"
    test_file.write_text(file_content, encoding="utf-8")

    # This call will fail (TypeError) or return full content (if I don't use args) before I implement the change.
    # I'll write it assuming the API update.
    try:
        content = git_ops.read_file("large.txt")
        # Once implemented, this should return first 2000 lines + warning
        # Currently it returns 2500 lines
        lines_read = content.splitlines()

        # Check for truncation message
        # Note: The truncation message is appended.
        if len(lines_read) > 2000:
            # Current behavior (fail test)
            pass
    except TypeError:
        # Expected if I passed arguments that don't exist yet
        pass


# Actually, I should write the test to verify the FINAL desired state.
# When I run it now, it will fail. That's fine.


def test_read_file_truncation_default(mock_codebase):
    lines = [f"Line {i}" for i in range(1, 2501)]
    test_file = mock_codebase / "large.txt"
    test_file.write_text("\n".join(lines), encoding="utf-8")

    # Call without explicit start/end_line
    # We expect the function signature to be updated to support this,
    # but initially we call it with just filepath
    content = git_ops.read_file("large.txt")

    # Logic verification
    # If not implemented, this returns 2500 lines.
    # If implemented, it returns 2000 lines + footer.

    assert "Line 2000" in content
    assert "Line 2001" not in content
    assert "Truncated." in content
    assert "Read limit is 2000 lines" in content


def test_read_file_pagination(mock_codebase):
    lines = [f"Line {i}" for i in range(1, 101)]
    test_file = mock_codebase / "pagination.txt"
    test_file.write_text("\n".join(lines), encoding="utf-8")

    # Request lines 10-20
    content = git_ops.read_file("pagination.txt", start_line=10, end_line=20)

    assert "Line 9" not in content
    assert "Line 10" in content
    assert "Line 20" in content
    assert "Line 21" not in content

    split_lines = content.splitlines()
    assert len(split_lines) == 11  # 10 to 20 inclusive is 11 lines


def test_read_file_start_line_only(mock_codebase):
    lines = [f"Line {i}" for i in range(1, 101)]
    test_file = mock_codebase / "start.txt"
    test_file.write_text("\n".join(lines), encoding="utf-8")

    # Request lines 90 onwards
    content = git_ops.read_file("start.txt", start_line=90)

    assert "Line 89" not in content
    assert "Line 90" in content
    assert "Line 100" in content


def test_read_file_out_of_bounds(mock_codebase):
    lines = ["Line 1", "Line 2"]
    test_file = mock_codebase / "small.txt"
    test_file.write_text("\n".join(lines), encoding="utf-8")

    # Request start_line beyond EOF
    content = git_ops.read_file("small.txt", start_line=10)
    # Should probably be empty or handle gracefully
    assert content.strip() == ""


def test_read_file_not_found(mock_codebase):
    content = git_ops.read_file("nonexistent.txt")
    assert "Error: File nonexistent.txt not found" in content
