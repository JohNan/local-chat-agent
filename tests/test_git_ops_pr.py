"""
Tests for git_ops PR functions.
"""

import unittest
from unittest.mock import patch, MagicMock
from app.services import git_ops


class TestGitOpsPR(unittest.TestCase):
    """Test suite for git PR operations."""

    @patch("app.services.git_ops.subprocess.run")
    def test_get_pr_diff_success(self, mock_run):
        """Test successful PR diff retrieval."""
        # Mock successful execution
        mock_result = MagicMock()
        mock_result.stdout = "diff content"
        mock_run.return_value = mock_result

        diff = git_ops.get_pr_diff(123)

        self.assertEqual(diff, "diff content")

        # Verify calls
        # 1. fetch
        # 2. diff
        # 3. branch -D
        self.assertEqual(mock_run.call_count, 3)

        calls = mock_run.call_args_list
        # calls[0][0][0] is the command list
        self.assertIn("fetch", calls[0][0][0])
        self.assertIn("diff", calls[1][0][0])
        self.assertIn("branch", calls[2][0][0])

    @patch("app.services.git_ops.subprocess.run")
    def test_get_pr_diff_error(self, mock_run):
        """Test error handling during PR diff retrieval."""
        # Mock error
        # pylint: disable=no-member
        mock_run.side_effect = git_ops.subprocess.CalledProcessError(
            1, "cmd", stderr="error"
        )

        diff = git_ops.get_pr_diff(123)

        self.assertIn("Error retrieving PR diff", diff)
