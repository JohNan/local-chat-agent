"""
Router for chat history management.
"""

import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services import chat_manager
from app.services.llm_service import clear_cache

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/history")
def api_history(limit: int = 20, offset: int = 0):
    """Retrieves paginated chat history."""
    result = chat_manager.get_history_page(limit, offset)
    return result


@router.post("/api/context_reset")
def api_context_reset():
    """Inserts a context reset marker."""
    try:
        chat_manager.add_context_marker()
        clear_cache()  # Invalidate cache
        return {"status": "success"}
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error adding context marker: %s", e)
        return JSONResponse(
            status_code=500, content={"status": "error", "error": str(e)}
        )


@router.post("/api/reset")
def api_reset():
    """Resets chat history."""
    try:
        chat_manager.reset_history()
        clear_cache()  # Invalidate cache
        return {"status": "success"}
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error resetting history: %s", e)
        return JSONResponse(
            status_code=500, content={"status": "error", "error": str(e)}
        )
