"""
FastAPI application for the backend.
"""

import os
import sys
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.services import rag_manager
from app.services.database import DatabaseManager
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
    yield
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
