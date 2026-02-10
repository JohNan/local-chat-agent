import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock google.genai and types before importing app.main
sys.modules["google"] = MagicMock()
sys.modules["google.genai"] = MagicMock()
types_mock = MagicMock()
sys.modules["google.genai"].types = types_mock


# Mock Part class
class MockPart:
    def __init__(self, text=None, function_response=None):
        self.text = text
        self.function_response = function_response

    @staticmethod
    def from_function_response(name, response):
        return MockPart(function_response={"name": name, "response": response})

    def __eq__(self, other):
        return (
            self.text == other.text
            and self.function_response == other.function_response
        )

    def __repr__(self):
        return f"Part(text={self.text}, function_response={self.function_response})"


types_mock.Part = MockPart
types_mock.Part.from_function_response = MockPart.from_function_response

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
        self.assertIsNotNone(part.function_response)
        self.assertEqual(part.function_response["name"], "my_tool")
        self.assertEqual(part.function_response["response"]["result"], "tool result")


if __name__ == "__main__":
    unittest.main()
