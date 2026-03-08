from app.services.web_ops import fetch_url
from unittest.mock import patch, MagicMock
import sys

def test():
    with patch("app.services.web_ops.requests.get") as mock_get:
        # Mock allowed URL response
        mock_response_allowed = MagicMock()
        mock_response_allowed.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_response_allowed.iter_content.return_value = [b"<html><body><h1>Example Domain</h1></body></html>"]

        # Mock forbidden URL response
        mock_response_forbidden = MagicMock()
        mock_response_forbidden.headers = {"Content-Type": "application/pdf"}

        def side_effect(url, **kwargs):
            if url == "https://example.com":
                return mock_response_allowed
            else:
                return mock_response_forbidden

        mock_get.side_effect = side_effect

        # Test allowed
        print("Testing allowed URL...")
        res1 = fetch_url("https://example.com")
        if "Example Domain" in res1:
            print("Success for allowed URL.")
        else:
            print("Failed for allowed URL. Output:", res1)
            sys.exit(1)

        # Test forbidden
        print("Testing forbidden URL...")
        res2 = fetch_url("https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf")
        expected = "Error: Downloading files is strictly forbidden. The browser tool is only for viewing text-based web pages."
        if res2 == expected:
            print("Success for forbidden URL.")
            mock_response_forbidden.close.assert_called_once()
            print("Close was called on forbidden response.")
        else:
            print("Failed for forbidden URL. Got:", res2)
            sys.exit(1)

test()
