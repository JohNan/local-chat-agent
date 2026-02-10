import unittest
import sys
import os
from google.genai import types

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Now import app.main
from app import main


class TestHistoryFormat(unittest.TestCase):
    def test_legacy_function_message(self):
        # Legacy: function message with only text
        history = [
            {"role": "user", "parts": [{"text": "call tool"}]},
            {"role": "function", "parts": [{"text": "tool result"}]},
            {"role": "user", "parts": [{"text": "current message"}]},
        ]

        formatted = main._format_history(history)

        # Expectation: role mapped to 'user', text part preserved
        self.assertEqual(len(formatted), 2)
        self.assertEqual(formatted[1]["role"], "user")
        self.assertEqual(formatted[1]["parts"][0].text, "tool result")

    def test_new_function_message(self):
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

        formatted = main._format_history(history)

        # Expectation: role KEPT as 'function' because it has proper parts
        self.assertEqual(formatted[1]["role"], "function")

        # Expect functionResponse part
        part = formatted[1]["parts"][0]

        # The real types.Part might not expose function_response as a property directly
        # It's likely hidden or accessed differently. Let's check or inspect.
        # But we can check via .to_json_dict() or similar if properties fail.
        # Or inspect the object directly.

        # Based on previous `dir(types.Part)`, it has `function_response` logic internally?
        # No, `dir` showed `from_function_response` but didn't show an explicit `function_response` property?
        # Wait, `dir` showed `__pydantic_fields__` etc. It's a Pydantic model.
        # So it likely has attributes matching the constructor args or fields.

        # Let's try direct attribute access first, but be prepared for failures.
        # If it fails, we can use `part.model_dump()` or `part.dict()` (since it's pydantic v2/v1 compat).

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
