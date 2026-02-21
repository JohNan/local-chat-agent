"""
Router for system and maintenance endpoints.
"""

import asyncio
import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import CLIENT, DEFAULT_MODEL
from app.services import git_ops, rag_manager, prompt_router, chat_manager
from app.services.lsp_manager import LSPManager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/status")
def api_status():
    """Returns repository status."""
    info = git_ops.get_repo_info()
    info["active_persona"] = prompt_router.load_active_persona()
    info["lsp_servers"] = LSPManager().get_active_servers()
    return info


@router.post("/api/git_pull")
async def api_git_pull():
    """Performs a git pull."""
    result = await asyncio.to_thread(git_ops.perform_git_pull)

    if result.get("success"):
        logger.info("Git pull successful. Triggering background re-indexing...")
        asyncio.create_task(asyncio.to_thread(rag_manager.index_codebase_task))

    return result


@router.post("/rag/reindex")
async def rag_reindex():
    """Triggers a codebase re-index."""
    # Run in background
    asyncio.create_task(asyncio.to_thread(rag_manager.index_codebase_task))
    return {"status": "indexing started"}


@router.get("/api/settings")
def api_settings():
    """Returns system settings."""
    model = chat_manager.get_setting("default_model", DEFAULT_MODEL)
    return {"model": model}


@router.get("/api/models")
def api_models():
    """Returns a list of available Gemini models."""
    if not CLIENT:
        return JSONResponse(
            status_code=500, content={"error": "Gemini client not initialized"}
        )
    try:
        models = []
        for m in CLIENT.models.list():
            if "generateContent" in m.supported_actions and m.name.startswith(
                "models/gemini-"
            ):
                # Strip "models/" prefix
                model_name = m.name.replace("models/", "")
                models.append(model_name)
        return {"models": models}
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to fetch models: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})
