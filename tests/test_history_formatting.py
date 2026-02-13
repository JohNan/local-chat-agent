"""
Tests for history formatting.
"""

import unittest
import sys
import os

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Now import app.services.llm_service
# pylint: disable=wrong-import-position, protected-access
from app.services import llm_service


class TestHistoryFormat(unittest.TestCase):
    """Test suite for history formatting."""

    def test_legacy_function_message(self):
        """Test formatting of legacy function messages (text only)."""
        # Legacy: function message with only text
        history = [
            {"role": "user", "parts": [{"text": "call tool"}]},
            {"role": "function", "parts": [{"text": "tool result"}]},
            {"role": "user", "parts": [{"text": "current message"}]},
        ]

        formatted = llm_service.format_history(history)

        # Expectation: role mapped to 'user', text part preserved
        self.assertEqual(len(formatted), 2)
        self.assertEqual(formatted[1]["role"], "user")
        self.assertEqual(formatted[1]["parts"][0].text, "tool result")

    def test_new_function_message(self):
        """Test formatting of new function messages (with functionResponse)."""
        # New: function message with functionResponse
        history = [
            {"role": "user", "parts": [{"text": "call tool"}]},
            {
                "role": "function",
                "parts": [
                    {
                        "text": "tool result",
                        "functionResponse": {
                            "name": "my_tool",
                            "response": {"result": "tool result"},
                        },
                    }
                ],
            },
            {"role": "user", "parts": [{"text": "current message"}]},
        ]

        formatted = llm_service.format_history(history)

        # Expectation: role KEPT as 'function' because it has proper parts
        self.assertEqual(formatted[1]["role"], "function")

        # Expect functionResponse part
        part = formatted[1]["parts"][0]

        try:
            # Try accessing attribute directly (Pydantic model style)
            # The field name in `from_function_response` is `response`.
            # But the part likely stores it in `function_response` or similar.
            # Let's dump it to be safe.
            data = part.model_dump(exclude_none=True)
            self.assertIn("function_response", data)
            self.assertEqual(data["function_response"]["name"], "my_tool")
            self.assertEqual(
                data["function_response"]["response"]["result"], "tool result"
            )
        except AttributeError:
            # Fallback for older pydantic or different structure
            self.fail(f"Could not inspect part: {part}")


if __name__ == "__main__":
    unittest.main()
