"""
Router for Jules and task management endpoints.
"""

import asyncio
import logging
import traceback
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services import jules_api, task_manager, chat_manager, git_ops

logger = logging.getLogger(__name__)

router = APIRouter()


class DeployRequest(BaseModel):
    """Request model for deployment endpoint."""

    prompt: str


@router.post("/api/deploy_to_jules")
async def deploy_to_jules_route(request: DeployRequest):
    """Endpoint to deploy session to Jules."""
    try:
        prompt_text = request.prompt
        if not prompt_text:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No prompt provided"},
            )

        repo_info = await asyncio.to_thread(git_ops.get_repo_info)
        result = await jules_api.deploy_to_jules(prompt_text, repo_info)

        # Save task
        if result and "name" in result:
            task_data = {
                "session_name": result["name"],
                "prompt_preview": prompt_text[:50]
                + ("..." if len(prompt_text) > 50 else ""),
                "status": "pending",  # Initial status
            }
            await asyncio.to_thread(task_manager.add_task, task_data)

            # Save confirmation message to chat
            message = (
                f"Started Jules task: {result['name']}\nPrompt: {prompt_text[:50]}..."
            )
            await asyncio.to_thread(chat_manager.save_message, "model", message)

        return {"success": True, "result": result}

    except Exception as e:  # pylint: disable=broad-exception-caught
        # Save error message to chat
        message = f"Failed to start Jules task. Error: {str(e)}"
        await asyncio.to_thread(chat_manager.save_message, "model", message)

        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(e)}
        )


@router.get("/api/tasks")
def api_tasks():
    """Returns list of tasks."""
    return task_manager.load_tasks()


@router.post("/api/tasks/{session_name:path}/sync")
async def api_tasks_sync(session_name: str):
    """Syncs status with Jules API."""
    try:
        status_result = await jules_api.get_session_status(session_name)
        new_status = status_result.get("state", "unknown")
        updated_task = await asyncio.to_thread(
            task_manager.update_task_status, session_name, new_status
        )
        return updated_task
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to sync task: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/jules_session/{session_name:path}")
async def get_jules_session_status(session_name: str):
    """Retrieves the status of a Jules session."""
    try:
        result = await jules_api.get_session_status(session_name)
        return result
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(e)}
        )
