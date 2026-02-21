"""
Tests for main application execution arguments.
"""
import sys
import runpy
from unittest.mock import MagicMock
import pytest

# pylint: disable=redefined-outer-name

@pytest.fixture
def mock_uvicorn(mocker):
    """Mock uvicorn module."""
    mock = MagicMock()
    mocker.patch.dict(sys.modules, {"uvicorn": mock})
    return mock

def test_main_execution_default(mocker, mock_uvicorn):
    """Test main execution with default arguments."""
    # Clear environment variables relevant to config
    mocker.patch.dict("os.environ", {}, clear=True)

    # Remove app.config from sys.modules to ensure it reloads with new env
    if "app.config" in sys.modules:
        del sys.modules["app.config"]
    if "app.main" in sys.modules:
        del sys.modules["app.main"]

    # Execute the file
    # We catch SystemExit because sometimes scripts call sys.exit()
    try:
        runpy.run_path("app/main.py", run_name="__main__")
    except SystemExit:
        pass

    # Check if uvicorn.run was called
    mock_uvicorn.run.assert_called_once()
    _, kwargs = mock_uvicorn.run.call_args
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 5000

def test_main_execution_env_vars(mocker, mock_uvicorn):
    """Test main execution with environment variables."""
    # Set environment variables
    mocker.patch.dict("os.environ", {"HOST": "10.0.0.1", "PORT": "8080"})

    # Remove app.config from sys.modules to ensure it reloads with new env
    if "app.config" in sys.modules:
        del sys.modules["app.config"]
    if "app.main" in sys.modules:
        del sys.modules["app.main"]

    # Execute the file
    try:
        runpy.run_path("app/main.py", run_name="__main__")
    except SystemExit:
        pass

    # Check if uvicorn.run was called
    mock_uvicorn.run.assert_called_once()
    _, kwargs = mock_uvicorn.run.call_args
    assert kwargs["host"] == "10.0.0.1"
    assert kwargs["port"] == 8080
