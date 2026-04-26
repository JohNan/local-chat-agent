#!/usr/bin/env python3
"""
Placeholder MCP Server for the Gemini CLI integration.
This script will eventually host the Python tools (like list_files, search_codebase_semantic)
as an MCP server for the CLI to connect to.
"""

import sys
import json
import logging

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

def main():
    logger.info("MCP Server starting...")
    # TODO: Implement the FastMCP server or similar here

    # Just loop to keep the process alive for now if invoked manually
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        # Minimal mock JSON-RPC response
        try:
            req = json.loads(line)
            if "id" in req:
                resp = {"jsonrpc": "2.0", "id": req["id"], "result": {}}
                print(json.dumps(resp), flush=True)
        except json.JSONDecodeError:
            pass

if __name__ == "__main__":
    main()
