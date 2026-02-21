import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.services.rag_manager import RAGManager


class TestRAGGitIgnore(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()

        # Change to the temp dir so os.walk(".") works there
        os.chdir(self.test_dir)

        # Create .gitignore
        with open(".gitignore", "w") as f:
            f.write("secret.py\nignored_dir/\n")

        # Create secret.py (should be ignored)
        with open("secret.py", "w") as f:
            f.write("SECRET_KEY = '12345'")

        # Create allowed.py (should be indexed)
        with open("allowed.py", "w") as f:
            f.write("print('hello')")

        # Create ignored directory
        os.makedirs("ignored_dir")
        with open("ignored_dir/stuff.py", "w") as f:
            f.write("print('ignore me')")

        # Create a nested directory that is allowed
        os.makedirs("allowed_dir")
        with open("allowed_dir/nested.py", "w") as f:
            f.write("print('nested hello')")

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_gitignore_respected(self):

        with patch(
            "app.services.rag_manager.chromadb.PersistentClient"
        ) as mock_chroma, patch(
            "app.services.rag_manager.genai.Client"
        ) as mock_genai, patch.dict(
            os.environ, {"GOOGLE_API_KEY": "fake_key"}
        ):

            manager = RAGManager()

            manager.collection = MagicMock()
            manager.genai_client = MagicMock()

            # Mock embeddings to return as many embeddings as input texts
            def side_effect_embed(model, contents):
                mock_res = MagicMock()
                # Create a list of embeddings matching the input length
                mock_res.embeddings = [MagicMock(values=[0.1] * 768) for _ in contents]
                return mock_res

            manager.genai_client.models.embed_content.side_effect = side_effect_embed

            # Mock collection.get to return empty (new files) for all calls
            manager.collection.get.return_value = {"metadatas": [], "ids": []}

            # Run indexing
            result = manager.index_codebase()

            # Verify result status
            self.assertEqual(result.get("status"), "success")

            # Check what was sent to upsert
            calls = manager.collection.upsert.call_args_list
            indexed_files = set()
            for call in calls:
                # kwargs['metadatas'] is a list of dicts
                metadatas = call.kwargs.get("metadatas", [])
                if not metadatas and len(call.args) > 3:
                    metadatas = call.args[3]

                for meta in metadatas:
                    indexed_files.add(meta["filepath"])

            print(f"Indexed files: {indexed_files}")

            # Assertions
            self.assertNotIn(
                "secret.py", indexed_files, "secret.py should be ignored by .gitignore"
            )
            self.assertFalse(
                any("ignored_dir" in f for f in indexed_files),
                "ignored_dir should be ignored",
            )
            self.assertIn("allowed.py", indexed_files, "allowed.py should be indexed")
            self.assertIn(
                "allowed_dir/nested.py",
                indexed_files,
                "allowed_dir/nested.py should be indexed",
            )

            # Additional assertion: Verify the number of indexed files matches what we expect
            # We expect allowed.py and allowed_dir/nested.py
            self.assertEqual(
                len(indexed_files),
                2,
                f"Expected 2 indexed files, got {len(indexed_files)}",
            )


if __name__ == "__main__":
    unittest.main()
