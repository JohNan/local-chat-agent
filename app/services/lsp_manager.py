"""
Service for managing Language Server Protocol (LSP) processes.
"""

import asyncio
import collections
import json
import logging
import os
import subprocess
import socket
import threading
import time
from typing import Dict, Any, Optional
from app.services.lsp_registry import LSPRegistry

logger = logging.getLogger(__name__)


class LSPServer:
    """Helper class to manage a single LSP process or socket and its I/O."""

    # pylint: disable=too-many-instance-attributes, too-many-positional-arguments
    def __init__(
        self,
        process: Optional[subprocess.Popen],
        language: str,
        root_path: str,
        sock: Optional[socket.socket] = None,
    ):
        self.process = process
        self.sock = sock
        self.language = language
        self.root_path = root_path
        self.responses: Dict[int, Any] = {}
        self.conditions: Dict[int, threading.Condition] = {}
        self.stderr_buffer = collections.deque(maxlen=20)
        self.lock = threading.Lock()
        self.status = "initializing"
        self.initialization_error: Optional[str] = None
        self.running = True

        self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.reader_thread.start()

        if self.process:
            self.stderr_thread = threading.Thread(target=self._stderr_loop, daemon=True)
            self.stderr_thread.start()

    def is_alive(self) -> bool:
        """Checks if the underlying process or socket is still alive."""
        if not self.running:
            return False
        if self.process:
            return self.process.poll() is None
        if self.sock:
            # We rely on the reader thread detecting disconnects and setting self.running = False
            return True
        return False

    def terminate(self):
        """Terminates the server."""
        self.running = False
        if self.process:
            self.process.terminate()
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
            except Exception:  # pylint: disable=broad-exception-caught
                pass

    def _stderr_loop(self):
        """Reads stderr to prevent buffer filling and deadlock."""
        if not self.process:
            return

        while self.running and self.process.poll() is None:
            try:
                line = self.process.stderr.readline()
                if not line:
                    break
                decoded_line = line.decode("utf-8", errors="ignore").strip()
                with self.lock:
                    self.stderr_buffer.append(decoded_line)
                logger.debug(
                    "[%s] stderr: %s",
                    self.language,
                    decoded_line,
                )
            except Exception:  # pylint: disable=broad-exception-caught
                break

    # pylint: disable=too-many-branches
    def _read_loop(self):
        """Reads JSON-RPC messages from stdout or socket."""
        try:
            if self.process:
                infile = self.process.stdout
            elif self.sock:
                infile = self.sock.makefile("rb")
            else:
                return

            while self.running and self.is_alive():
                # Read headers
                headers = {}
                while True:
                    line = infile.readline()
                    if not line:
                        self.running = False
                        return  # EOF or process died

                    line_str = line.decode("utf-8", errors="ignore").strip()
                    if not line_str:
                        break  # End of headers

                    parts = line_str.split(":", 1)
                    if len(parts) == 2:
                        headers[parts[0].strip()] = parts[1].strip()

                content_len = int(headers.get("Content-Length", 0))
                if content_len > 0:
                    body = infile.read(content_len)
                    if not body:
                        self.running = False
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

                    except json.JSONDecodeError as e:
                        logger.error(
                            "Failed to decode JSON from LSP %s: %s", self.language, e
                        )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error in LSP reader loop for %s: %s", self.language, e)
        finally:
            self.running = False

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
        """Encodes and writes payload to stdin or socket."""
        if not self.running:
            return False
        try:
            body = json.dumps(payload)
            message = f"Content-Length: {len(body)}\r\n\r\n{body}"
            data = message.encode("utf-8")
            if self.process:
                self.process.stdin.write(data)
                self.process.stdin.flush()
            elif self.sock:
                self.sock.sendall(data)
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to write to LSP %s: %s", self.language, e)
            self.running = False
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

    def _get_normalized_path(self, path: str) -> str:
        return os.path.abspath(path)

    def _get_server_key(self, language: str, root_path: str) -> str:
        return f"{language}:{root_path}"

    def get_active_servers(self) -> list[Dict[str, Any]]:
        """Returns a list of active LSP servers."""
        servers = []
        with self._lock:
            for _, server in self._servers.items():
                if not server.is_alive():
                    status = "stopped"
                else:
                    status = server.status
                servers.append(
                    {
                        "language": server.language,
                        "root_path": server.root_path,
                        "pid": server.process.pid if server.process else None,
                        "status": status,
                    }
                )
        return servers

    def _initialize_server_bg(self, server: LSPServer, timeout: float):
        """Runs the initialization sequence in the background."""
        language = server.language
        root_path = server.root_path
        key = self._get_server_key(language, root_path)

        init_params = {
            "processId": os.getpid(),
            "rootUri": f"file://{root_path}",
            "capabilities": {},
        }

        resp = server.send_request("initialize", init_params, timeout=timeout)

        if resp is None:
            # Timeout
            server.status = "failed"
            server.initialization_error = (
                f"failed to initialize within {timeout} seconds"
            )
            logger.error(
                "%s LSP failed to initialize within %s seconds",
                language.capitalize(),
                timeout,
            )
            # Remove from servers dict to allow retry
            with self._lock:
                if key in self._servers:
                    del self._servers[key]
            server.terminate()
            return

        if "error" not in resp:
            server.send_notification("initialized", {})
            server.status = "running"
            return

        # Initialization failed with an error in response
        server.status = "failed"
        server.initialization_error = f"Initialization error: {resp.get('error')}"
        with server.lock:
            stderr_output = "\n".join(server.stderr_buffer)
        logger.error(
            "Failed to initialize LSP server for %s.\nResponse: %s\nRecent stderr:\n%s",
            language,
            resp,
            stderr_output,
        )
        with self._lock:
            if key in self._servers:
                del self._servers[key]
        server.terminate()

    # pylint: disable=too-many-locals
    async def start_server(self, language: str, root_path: str) -> Optional[LSPServer]:
        """Starts or retrieves an existing LSP server."""
        root_path = self._get_normalized_path(root_path)
        key = self._get_server_key(language, root_path)

        with self._lock:
            # Check if existing server is alive
            if key in self._servers:
                server = self._servers[key]
                if server.is_alive():
                    return server

                logger.warning("LSP server for %s died, restarting...", language)
                del self._servers[key]

        registry = LSPRegistry()
        # pylint: disable=protected-access
        config = registry._config.get(language)

        if not config:
            logger.error("No LSP configuration found for language: %s", language)
            return None

        timeout = config.get("timeout", 300.0)
        connection_type = config.get("connection", "stdio")

        try:
            if connection_type == "tcp":
                host = config.get("host", "localhost")
                port = config.get("port")
                if not port:
                    logger.error("TCP connection requires a port for %s", language)
                    return None

                logger.info(
                    "Connecting to LSP server for %s at %s:%s", language, host, port
                )

                # Try to connect with retries
                sock = None
                connected = False
                for _ in range(5):
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        # connect is blocking. Run in thread.
                        await asyncio.to_thread(sock.connect, (host, port))
                        connected = True
                        break
                    except ConnectionRefusedError:
                        sock.close()
                        await asyncio.sleep(1)

                if not connected:
                    logger.error(
                        "Failed to connect to %s LSP at %s:%s", language, host, port
                    )
                    return None

                server = LSPServer(
                    process=None, language=language, root_path=root_path, sock=sock
                )

            else:  # stdio
                bin_name = config["bin"]
                args = config.get("args", [])
                cmd = [bin_name] + args

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

                server = LSPServer(
                    process=process, language=language, root_path=root_path
                )

            with self._lock:
                self._servers[key] = server

            # Start initialization in background
            init_thread = threading.Thread(
                target=self._initialize_server_bg,
                args=(server, timeout),
                daemon=True,
            )
            init_thread.start()

            return server

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to start LSP server for %s: %s", language, e)
            return None

    def _get_supported_languages_in_path(self, root_path: str) -> list[str]:
        """
        Scans the root path once for supported files and returns languages to start.
        """
        registry = LSPRegistry()
        # pylint: disable=protected-access
        configs = registry._config

        lang_to_extensions = {}
        for lang, config in configs.items():
            exts = config.get("extensions", [])
            if exts:
                lang_to_extensions[lang] = tuple(exts)

        if not lang_to_extensions:
            return []

        lang_counts = {lang: 0 for lang in lang_to_extensions}
        found_languages = []
        min_file_threshold = 2

        for _, dirs, files in os.walk(root_path):
            # Skip common ignored directories
            dirs[:] = [
                d
                for d in dirs
                if d not in {".git", "node_modules", "venv", "__pycache__", "dist"}
            ]

            for file in files:
                for lang, extensions in lang_to_extensions.items():
                    if lang in found_languages:
                        continue
                    if file.endswith(extensions):
                        lang_counts[lang] += 1
                        if lang_counts[lang] >= min_file_threshold:
                            found_languages.append(lang)

            if len(found_languages) == len(lang_to_extensions):
                break

        return found_languages

    async def start_supported_servers(self, root_path: str):
        """
        Scans the root path for supported files and starts corresponding LSP servers.
        """
        root_path = self._get_normalized_path(root_path)
        logger.info("Scanning for supported languages to start LSP servers...")

        # Run directory scan in a separate thread to avoid blocking the event loop
        found_languages = await asyncio.to_thread(
            self._get_supported_languages_in_path, root_path
        )

        for language in found_languages:
            logger.info(
                "Found required files for %s, starting LSP server...",
                language,
            )
            await self.start_server(language, root_path)

    async def get_definition(
        self, file_path: str, line: int, col: int
    ) -> Dict[str, Any]:
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
        server = await self.start_server(language, root_path)
        if not server:
            return {"error": "Failed to start LSP server"}

        if server.status == "initializing":
            return {"error": "Server is starting..."}

        if server.status == "failed":
            return {"error": f"Server failed to start: {server.initialization_error}"}

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
