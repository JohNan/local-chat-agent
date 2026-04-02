"""
Tests for the web_ops service.
"""

import requests
import pytest
from unittest.mock import MagicMock, patch
from app.services.web_ops import fetch_url

def test_fetch_url_success_html():
    """Test successful fetching of an HTML page."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.iter_content.return_value = [b"<html><body>Hello World</body></html>"]
        mock_get.return_value = mock_response

        result = fetch_url("http://example.com")
        assert "Hello World" in result
        mock_get.assert_called_once_with("http://example.com", timeout=10, stream=True)

def test_fetch_url_success_plain_text():
    """Test successful fetching of a plain text file."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/plain; charset=utf-8"}
        mock_response.iter_content.return_value = [b"Hello Plain Text"]
        mock_get.return_value = mock_response

        result = fetch_url("http://example.com/text")
        assert result == "Hello Plain Text"

def test_fetch_url_forbidden_content_type():
    """Test that non-text content types are rejected."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "image/png"}
        mock_get.return_value = mock_response

        result = fetch_url("http://example.com/image.png")
        assert "Error: Downloading files is strictly forbidden" in result
        mock_response.close.assert_called_once()

def test_fetch_url_size_limit():
    """Test that content exceeding the size limit is truncated."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/plain"}

        # 5MB + some extra
        chunk_size = 8192
        num_chunks = (5 * 1024 * 1024 // chunk_size) + 2
        mock_response.iter_content.return_value = [b"a" * chunk_size] * num_chunks
        mock_get.return_value = mock_response

        result = fetch_url("http://example.com/large")
        # The result should be at least 5MB but definitely not the full content
        assert len(result) >= 5 * 1024 * 1024
        assert len(result) < num_chunks * chunk_size

def test_fetch_url_timeout():
    """Test handling of request timeouts."""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.Timeout()
        result = fetch_url("http://example.com")
        assert "Error: Request to http://example.com timed out." in result

def test_fetch_url_connection_error():
    """Test handling of connection errors."""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError()
        result = fetch_url("http://example.com")
        assert "Error: Failed to connect to http://example.com." in result

def test_fetch_url_http_error():
    """Test handling of HTTP errors (e.g., 404, 500)."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Client Error")
        mock_get.return_value = mock_response

        result = fetch_url("http://example.com/404")
        assert "Error: Failed to fetch http://example.com/404. Exception: 404 Client Error" in result

def test_fetch_url_generic_exception():
    """Test handling of unexpected exceptions."""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = Exception("Something went wrong")
        result = fetch_url("http://example.com")
        assert "Error: Unexpected error processing http://example.com. Exception: Something went wrong" in result
