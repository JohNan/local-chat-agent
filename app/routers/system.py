"""
Router for system and maintenance endpoints.
"""

import asyncio
import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from google.genai import types

from app.config import CLIENT, DEFAULT_MODEL
from app.services import git_ops, rag_manager, prompt_router, chat_manager, llm_service
from app.services.lsp_manager import LSPManager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/status")
async def api_status():
    """Returns repository status including token count."""
    info = await asyncio.to_thread(git_ops.get_repo_info)
    info["active_persona"] = await asyncio.to_thread(prompt_router.load_active_persona)
    info["lsp_servers"] = LSPManager().get_active_servers()

    # Calculate token count
    try:
        if CLIENT:
            history = await asyncio.to_thread(chat_manager.load_chat_history)
            formatted_history = await asyncio.to_thread(
                llm_service.format_history, history, include_last=True
            )
            active_persona = info["active_persona"]
            system_instruction = prompt_router.get_system_instruction(active_persona)

            model = await asyncio.to_thread(
                chat_manager.get_setting, "default_model", DEFAULT_MODEL
            )
            config = types.CountTokensConfig(system_instruction=system_instruction)
            if system_instruction:
                formatted_history.insert(
                    0,
                    types.Content(
                        role="user", parts=[types.Part(text=system_instruction)]
                    ),
                )
            response = CLIENT.models.count_tokens(
                model=model,
                contents=formatted_history,
            )
            info["token_count"] = response.total_tokens
        else:
            info["token_count"] = None
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to count tokens: %s", e)
        info["token_count"] = None

    return info


class GitPushRequest(BaseModel):
    """Request model for git push."""

    branch_name: str
    commit_message: str
    switch_back: bool = True


@router.get("/api/git_status")
def api_git_status():
    """Returns the git status."""
    status = git_ops.get_git_status()
    return {"status": status}


@router.post("/api/git_push")
async def api_git_push(request: GitPushRequest):
    """Performs a git push."""
    result = await asyncio.to_thread(
        git_ops.perform_git_push,
        request.branch_name,
        request.commit_message,
        request.switch_back,
    )
    return result


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


@router.post("/api/rag/clear_and_reindex")
async def clear_and_reindex_rag():
    """Clears the RAG index for the current repository and rebuilds it."""
    logger.info("Clearing and rebuilding RAG index...")
    rag_manager.clear_repo_index()

    # Run re-indexing in background
    asyncio.create_task(asyncio.to_thread(rag_manager.index_codebase_task))
    return {"status": "Index cleared. Rebuilding in background..."}


class SettingsRequest(BaseModel):
    """Request model for updating settings."""

    model: str


@router.get("/api/settings")
def api_settings():
    """Returns system settings."""
    model = chat_manager.get_setting("default_model", DEFAULT_MODEL)
    return {"model": model}


@router.post("/api/settings")
def save_settings(request: SettingsRequest):
    """Saves system settings."""
    chat_manager.save_setting("default_model", request.model)
    return {"status": "updated", "model": request.model}


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
