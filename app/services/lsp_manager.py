"""
Service for managing Language Server Protocol (LSP) processes.
"""

import json
import logging
import os
import subprocess
import threading
import time
from typing import Dict, Any, Optional
from app.services.lsp_registry import LSPRegistry

logger = logging.getLogger(__name__)


class LSPServer:
    """Helper class to manage a single LSP process and its I/O."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, process: subprocess.Popen, language: str, root_path: str):
        self.process = process
        self.language = language
        self.root_path = root_path
        self.responses: Dict[int, Any] = {}
        self.conditions: Dict[int, threading.Condition] = {}
        self.lock = threading.Lock()
        self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.reader_thread.start()
        self.stderr_thread = threading.Thread(target=self._stderr_loop, daemon=True)
        self.stderr_thread.start()

    def _stderr_loop(self):
        """Reads stderr to prevent buffer filling and deadlock."""
        while self.process.poll() is None:
            try:
                line = self.process.stderr.readline()
                if not line:
                    break
                logger.debug(
                    "[%s] stderr: %s",
                    self.language,
                    line.decode("utf-8", errors="ignore").strip(),
                )
            except Exception:  # pylint: disable=broad-exception-caught
                break

    def _read_loop(self):
        """Reads JSON-RPC messages from stdout."""
        while self.process.poll() is None:
            try:
                # Read headers
                headers = {}
                while True:
                    line = self.process.stdout.readline()
                    if not line:
                        return  # EOF or process died

                    line_str = line.decode("utf-8", errors="ignore").strip()
                    if not line_str:
                        break  # End of headers

                    parts = line_str.split(":", 1)
                    if len(parts) == 2:
                        headers[parts[0].strip()] = parts[1].strip()

                content_len = int(headers.get("Content-Length", 0))
                if content_len > 0:
                    body = self.process.stdout.read(content_len)
                    if not body:
                        break

                    try:
                        msg = json.loads(body)

                        # If it's a response with an ID, notify waiter
                        if "id" in msg and msg["id"] is not None:
                            req_id = msg["id"]
                            with self.lock:
                                self.responses[req_id] = msg
                                if req_id in self.conditions:
                                    with self.conditions[req_id]:
                                        self.conditions[req_id].notify()
                        # Notifications (no id) are currently ignored or just logged
                        # else:
                        #    logger.debug("LSP Notification: %s", msg)

                    except json.JSONDecodeError as e:
                        logger.error(
                            "Failed to decode JSON from LSP %s: %s", self.language, e
                        )

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error in LSP reader loop for %s: %s", self.language, e)
                break

    def send_request(
        self, method: str, params: Any, timeout: float = 30.0
    ) -> Optional[Dict[str, Any]]:
        """Sends a request and waits for a response."""
        req_id = int(time.time() * 1000000) % 10000000
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}

        condition = threading.Condition()
        with self.lock:
            self.conditions[req_id] = condition

        if not self._send_payload(payload):
            with self.lock:
                del self.conditions[req_id]
            return None

        # Wait for response
        response = None
        with condition:
            if condition.wait(timeout):
                with self.lock:
                    response = self.responses.get(req_id)
                    # Cleanup
                    if req_id in self.responses:
                        del self.responses[req_id]
            else:
                logger.warning(
                    "Timeout waiting for LSP response id %s from %s",
                    req_id,
                    self.language,
                )

        with self.lock:
            if req_id in self.conditions:
                del self.conditions[req_id]

        return response

    def send_notification(self, method: str, params: Any):
        """Sends a notification (no response expected)."""
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        self._send_payload(payload)

    def _send_payload(self, payload: Dict[str, Any]) -> bool:
        """Encodes and writes payload to stdin."""
        try:
            body = json.dumps(payload)
            message = f"Content-Length: {len(body)}\r\n\r\n{body}"
            self.process.stdin.write(message.encode("utf-8"))
            self.process.stdin.flush()
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to write to LSP %s: %s", self.language, e)
            return False


class LSPManager:
    """Singleton manager for LSP server processes."""

    _instance = None
    _servers: Dict[str, LSPServer] = {}
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LSPManager, cls).__new__(cls)
        return cls._instance

    def _get_server_key(self, language: str, root_path: str) -> str:
        return f"{language}:{root_path}"

    def start_server(self, language: str, root_path: str) -> Optional[LSPServer]:
        """Starts or retrieves an existing LSP server."""
        key = self._get_server_key(language, root_path)

        with self._lock:
            # Check if existing server is alive
            if key in self._servers:
                server = self._servers[key]
                if server.process.poll() is None:
                    return server

                logger.warning("LSP server for %s died, restarting...", language)
                del self._servers[key]

            registry = LSPRegistry()
            # pylint: disable=protected-access
            config = registry._config.get(language)

            if not config:
                logger.error("No LSP configuration found for language: %s", language)
                return None

            bin_name = config["bin"]
            args = config.get("args", [])
            cmd = [bin_name] + args

            try:
                logger.info(
                    "Starting LSP server for %s at %s with cmd: %s",
                    language,
                    root_path,
                    cmd,
                )
                # pylint: disable=consider-using-with
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,  # Capture stderr to keep it clean
                    cwd=root_path,
                    bufsize=0,
                )

                server = LSPServer(process, language, root_path)

                # Initialize
                init_params = {
                    "processId": os.getpid(),
                    "rootUri": f"file://{root_path}",
                    "capabilities": {},
                }
                # Increase timeout for initialization (some servers are slow)
                resp = server.send_request("initialize", init_params, timeout=60.0)
                if resp and "error" not in resp:
                    server.send_notification("initialized", {})
                    self._servers[key] = server
                    return server

                logger.error(
                    "Failed to initialize LSP server for %s. Response: %s",
                    language,
                    resp,
                )
                process.terminate()
                return None

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Failed to start LSP server for %s: %s", language, e)
                return None

    def start_supported_servers(self, root_path: str):
        """
        Scans the root path for supported files and starts corresponding LSP servers.
        """
        logger.info("Scanning for supported languages to start LSP servers...")
        registry = LSPRegistry()
        # pylint: disable=protected-access
        for language, config in registry._config.items():
            extensions = config.get("extensions", [])
            if not extensions:
                continue

            found = False
            # Walk the directory to find a matching file
            for root, dirs, files in os.walk(root_path):
                # Skip common ignored directories
                dirs[:] = [
                    d
                    for d in dirs
                    if d not in {".git", "node_modules", "venv", "__pycache__", "dist"}
                ]

                for file in files:
                    if any(file.endswith(ext) for ext in extensions):
                        found = True
                        break
                if found:
                    break

            if found:
                logger.info("Found %s files, starting LSP server...", language)
                self.start_server(language, root_path)

    def get_definition(self, file_path: str, line: int, col: int) -> Dict[str, Any]:
        """
        Finds the definition of the symbol at the given location.
        line and col are 1-based.
        """
        abs_path = os.path.abspath(file_path)

        # Determine language and config
        registry = LSPRegistry()
        ext = os.path.splitext(file_path)[1]
        config = registry.get_config_by_extension(ext)
        if not config:
            return {"error": f"No LSP support for extension {ext}"}

        language = self._get_language_name(registry, config)
        if not language:
            return {"error": "Language unknown"}

        # Find root and start server
        root_path = self._find_root(
            abs_path, config.get("root_markers", [])
        ) or os.path.dirname(abs_path)
        server = self.start_server(language, root_path)
        if not server:
            return {"error": "Failed to start LSP server"}

        return self._request_definition(server, abs_path, language, line, col)

    def _get_language_name(
        self, registry: LSPRegistry, config: Dict[str, Any]
    ) -> Optional[str]:
        # pylint: disable=protected-access
        for lang, cfg in registry._config.items():
            if cfg == config:
                return lang
        return None

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def _request_definition(
        self, server: LSPServer, abs_path: str, language: str, line: int, col: int
    ) -> Dict[str, Any]:
        """Helper to send didOpen and definition request."""
        # Read file content
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:  # pylint: disable=broad-exception-caught
            return {"error": f"Failed to read file: {e}"}

        server.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": f"file://{abs_path}",
                    "languageId": language,
                    "version": 1,
                    "text": content,
                }
            },
        )

        # Request Definition (Convert 1-based to 0-based)
        response = server.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": f"file://{abs_path}"},
                "position": {"line": line - 1, "character": col - 1},
            },
        )

        if response and "result" in response:
            return {"result": response["result"]}
        if response and "error" in response:
            return {"error": response["error"]}
        return {"error": "Request failed or timed out"}

    def _find_root(self, file_path: str, markers: list[str]) -> Optional[str]:
        """Finds project root by looking for markers."""
        current_dir = os.path.dirname(file_path)
        # Stop at root
        while os.path.dirname(current_dir) != current_dir:
            for marker in markers:
                if os.path.exists(os.path.join(current_dir, marker)):
                    return current_dir
            if os.path.exists(os.path.join(current_dir, ".git")):
                return current_dir
            current_dir = os.path.dirname(current_dir)
        return None
