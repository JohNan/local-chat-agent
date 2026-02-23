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
                "original_prompt": prompt_text,
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


@router.post("/api/jules_session/{session_name:path}/review")
async def review_jules_session(session_name: str):
    """
    Generates a review prompt for a Jules session.
    """
    try:
        # 1. Retrieve task to get original prompt
        task = await asyncio.to_thread(task_manager.get_task_by_session, session_name)
        original_prompt = "Original prompt not available."
        if task and "original_prompt" in task:
            original_prompt = task["original_prompt"]

        # 2. Retrieve session status
        status_result = await jules_api.get_session_status(session_name)

        # 3. Extract PR number
        pr_url = None
        outputs = status_result.get("outputs", [])
        if outputs:
            for output in outputs:
                if "pullRequest" in output and "url" in output["pullRequest"]:
                    pr_url = output["pullRequest"]["url"]
                    break

        if not pr_url:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "No PR URL found in session outputs.",
                },
            )

        # Extract number from URL (assuming github.com/user/repo/pull/123)
        try:
            # e.g. https://github.com/user/repo/pull/123
            url_part = pr_url
            if url_part.endswith("/"):
                url_part = url_part[:-1]
            pr_number_str = url_part.split("/")[-1]
            pr_number = int(pr_number_str)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Could not parse PR number from URL.",
                },
            )

        # 4. Get Diff
        # Run in thread as it uses subprocess
        diff_content = await asyncio.to_thread(git_ops.get_pr_diff, pr_number)

        if diff_content.startswith("Error"):
            return JSONResponse(
                status_code=500, content={"success": False, "error": diff_content}
            )

        # 5. Construct Prompt
        review_prompt = (
            f"Please review the implementation for the following task.\n\n"
            f"**Original Request:**\n{original_prompt}\n\n"
            f"**Pull Request:**\n{pr_url}\n\n"
            f"**Changes:**\n```diff\n{diff_content}\n```\n\n"
            "Please analyze the code for correctness, bugs, and style."
        )

        return {"success": True, "prompt": review_prompt}

    except Exception as e:  # pylint: disable=broad-exception-caught
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
