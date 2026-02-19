
import pytest
from app.agent_engine import _extract_error_message

def test_extract_error_message_gemini_503():
    error_str = """google.genai.errors.ServerError: 503 Service Unavailable. {'message': '{\n  "error": {\n    "code": 503,\n    "message": "This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.",\n    "status": "UNAVAILABLE"\n  }\n}\n', 'status': 'Service Unavailable'}"""
    expected = "This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later."
    assert _extract_error_message(error_str) == expected

def test_extract_error_message_simple():
    error_str = "ValueError: Something went wrong"
    expected = "ValueError: Something went wrong"
    assert _extract_error_message(error_str) == expected

def test_extract_error_message_nested_json():
    # Test with a different message inside nested JSON
    error_str = """SomeError: {'message': '{\n  "error": {\n    "message": "Custom error message"\n  }\n}\n'}"""
    expected = "Custom error message"
    assert _extract_error_message(error_str) == expected

def test_extract_error_no_match():
    # Test when regex doesn't match
    error_str = "Just a plain string error"
    expected = "Just a plain string error"
    assert _extract_error_message(error_str) == expected
