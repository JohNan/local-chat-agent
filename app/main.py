"""
FastAPI application for the backend.
"""

import os
import sys
import logging
import asyncio
from contextlib import asynccontextmanager, AsyncExitStack

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import get_mcp_servers
from app.services import rag_manager, llm_service
from app.services.database import DatabaseManager
from app.services.lsp_manager import LSPManager
from app.routers import chat, system, history, jules

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Lifespan context manager for the FastAPI app."""
    # Database Initialization
    logger.info("Initializing database...")
    db = DatabaseManager()
    await asyncio.to_thread(db.init_db)
    await asyncio.to_thread(db.migrate_from_json)

    # Startup
    logger.info("Starting background RAG indexing...")
    asyncio.create_task(asyncio.to_thread(rag_manager.index_codebase_task))

    # Initialize LSP Servers
    logger.info("Initializing LSP servers...")
    asyncio.create_task(asyncio.to_thread(LSPManager().start_supported_servers, "."))

    # Initialize MCP Clients
    async with AsyncExitStack() as stack:
        mcp_servers = get_mcp_servers()
        for name, config in mcp_servers.items():
            try:
                logger.info("Initializing MCP server: %s", name)
                server_params = StdioServerParameters(
                    command=config["command"],
                    args=config.get("args", []),
                    env={**os.environ, **config.get("env", {})},
                )

                read, write = await stack.enter_async_context(
                    stdio_client(server_params)
                )
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()

                # List tools
                result = await session.list_tools()

                # Store session
                llm_service.MCP_SESSIONS[name] = session

                # Convert and store tools
                for tool in result.tools:
                    tool_name = tool.name
                    # Convert to Gemini FunctionDeclaration
                    func_decl = types.FunctionDeclaration(
                        name=tool_name,
                        description=tool.description,
                        parameters=tool.inputSchema,
                    )

                    llm_service.MCP_TOOL_DEFINITIONS.append(func_decl)
                    llm_service.MCP_TOOL_TO_SESSION_MAP[tool_name] = session

                logger.info(
                    "MCP server %s initialized with %d tools", name, len(result.tools)
                )

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Failed to initialize MCP server %s: %s", name, e)

        yield
        logger.info("Shutting down MCP sessions...")
    # Shutdown (if needed)


app = FastAPI(lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(system.router)
app.include_router(chat.router)
app.include_router(history.router)
app.include_router(jules.router)


# Mount static folder
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount(
    "/static",
    StaticFiles(directory=static_dir),
    name="static",
)


@app.get("/")
def index():
    """Renders the main page."""
    # Serve index.html from static/dist
    index_path = os.path.join(os.path.dirname(__file__), "static/dist/index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Frontend not found"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000)
