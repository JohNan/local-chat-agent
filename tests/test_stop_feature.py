import sys
import os
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport

# Ensure app is importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app import agent_engine


@pytest.mark.asyncio
async def test_api_stop_no_active_task():
    """Test /api/stop when no task is running."""
    # Ensure no task is running
    agent_engine.CURRENT_STATE = None

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post("/api/stop")
    assert response.status_code == 200
    assert response.json() == {"status": "no_active_task"}


@pytest.mark.asyncio
async def test_api_stop_with_active_task():
    """Test /api/stop when a task is running."""

    # Create a dummy task that sleeps forever
    async def dummy_task():
        try:
            while True:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass

    # Manually set the CURRENT_STATE
    task = asyncio.create_task(dummy_task())
    state = agent_engine.TaskState()
    state.task_handle = task
    agent_engine.CURRENT_STATE = state

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post("/api/stop")

        assert response.status_code == 200
        assert response.json() == {"status": "stopped"}

        # Verify task is cancelled
        # Give it a moment to process cancellation if needed, though cancel() is synchronous in scheduling
        await asyncio.sleep(0)
        assert task.cancelled() or task.done()

    finally:
        # Cleanup
        if not task.done():
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        agent_engine.CURRENT_STATE = None
