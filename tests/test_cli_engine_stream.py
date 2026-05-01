import pytest
import asyncio
from unittest.mock import AsyncMock

from acp.schema import AgentMessageChunk, TextContentBlock
from app.services.llm_service import ACPClientHandler


@pytest.mark.asyncio
async def test_acp_client_handler_stream():
    """Test that ACPClientHandler extracts the delta stream based on previous_history_len."""
    mock_task_state = AsyncMock()
    mock_task_state.broadcast = AsyncMock()

    # Suppose turn 1 resulted in 5 characters: "Hello"
    client = ACPClientHandler(mock_task_state, previous_history_len=5)

    # Turn 2 outputs previous "Hello" + new answer "\nWorld!"
    stream_chunks = [
        "H",
        "Hel",
        "Hello",
        "Hello\n",
        "Hello\nWorld!"
    ]

    for chunk in stream_chunks:
        content = TextContentBlock(text=chunk, type="text")
        update = AgentMessageChunk(content=content, session_update="agent_message_chunk")
        await client.session_update("session_1", update)

    assert client.final_answer == "\nWorld!"

    # Verify that the broadcast was called for the new characters
    assert mock_task_state.broadcast.call_count == 2
    # First call: \n
    # Second call: World!
    calls = mock_task_state.broadcast.call_args_list
    assert '"\\n"' in calls[0][0][0]
    assert '"World!"' in calls[1][0][0]

@pytest.mark.asyncio
async def test_acp_client_handler_exact_concat():
    """Test what happens if the CLI Engine concatenates exact delta (though usually absolute)."""
    mock_task_state = AsyncMock()
    mock_task_state.broadcast = AsyncMock()

    client = ACPClientHandler(mock_task_state, previous_history_len=0)

    stream_chunks = [
        "Hello",
        "World!"
    ]

    for chunk in stream_chunks:
        content = TextContentBlock(text=chunk, type="text")
        update = AgentMessageChunk(content=content, session_update="agent_message_chunk")
        await client.session_update("session_1", update)

    assert client.final_answer == "HelloWorld!"
