import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from collections import defaultdict
import uuid

from acp.schema import (
    AgentMessageChunk,
    AgentThoughtChunk,
    UserMessageChunk,
    ToolCallStart,
    ToolCallProgress,
    TextContentBlock,
)
from app.services.llm_service import CLILLMService, TurnContext, ACPClientHandler


@pytest.mark.asyncio
async def test_acp_client_handler_streaming_logic():
    mock_task_state = AsyncMock()
    turn_marker = "==TEST_MARKER=="
    handler = ACPClientHandler(mock_task_state, turn_marker)

    # 1. Simulate History re-emission with marker
    # The CLI might send the whole history in one chunk
    history_text = f"User: Hi\nAssistant: Hello\nUser: Next\n\n{turn_marker}\n\n"
    history_chunk = UserMessageChunk(
        type="userMessageChunk",
        content=TextContentBlock(type="text", text=history_text),
    )
    await handler.session_update("sess", history_chunk)
    assert handler.marker_found is True
    # Should NOT have broadcasted anything yet as it's a UserMessageChunk
    assert mock_task_state.broadcast.call_count == 0

    # 2. Simulate New Text (Delta)
    # Some implementations send deltas
    delta_chunk = AgentMessageChunk(
        type="agentMessageChunk",
        content=TextContentBlock(type="text", text="I am "),
    )
    await handler.session_update("sess", delta_chunk)
    assert handler.current_text_segment == "I am "
    mock_task_state.broadcast.assert_called_with('event: message\ndata: "I am "\n\n')

    # 3. Simulate Another Delta
    delta_chunk2 = AgentMessageChunk(
        type="agentMessageChunk",
        content=TextContentBlock(type="text", text="working."),
    )
    await handler.session_update("sess", delta_chunk2)
    assert handler.current_text_segment == "I am working."

    # 4. Simulate Full Re-emission (some CLIs do this for every chunk)
    # History + Marker + "I am working. Also..."
    full_text = history_text + "I am working. Also thinking."
    full_chunk = AgentMessageChunk(
        type="agentMessageChunk",
        content=TextContentBlock(type="text", text=full_text),
    )
    await handler.session_update("sess", full_chunk)
    # Should have detected the new part " Also thinking."
    assert handler.current_text_segment == "I am working. Also thinking."
    # Last call should be the delta
    mock_task_state.broadcast.assert_called_with('event: message\ndata: " Also thinking."\n\n')

    # 5. Simulate Tool Call
    tool_start = ToolCallStart(
        type="toolCallStart",
        toolCallId="t1",
        title="search",
    )
    await handler.session_update("sess", tool_start)
    assert handler.tool_usage_counts["search"] == 1
    # current_text_segment should have been moved to reasoning_trace
    assert len(handler.reasoning_trace) == 1
    assert handler.reasoning_trace[0] == "I am working. Also thinking."
    assert handler.current_text_segment == ""


@pytest.mark.asyncio
@patch("app.services.llm_service.spawn_agent_process")
@patch("app.services.chat_manager.get_setting")
async def test_clillm_service_execute_turn_completion(mock_get_setting, mock_spawn):
    mock_get_setting.return_value = "gemini-test"
    
    mock_conn = AsyncMock()
    mock_proc = AsyncMock()
    
    class AsyncContextManagerMock:
        async def __aenter__(self): return mock_conn, mock_proc
        async def __aexit__(self, *args): pass
    
    mock_spawn.return_value = AsyncContextManagerMock()
    
    service = CLILLMService()
    mock_task_state = AsyncMock()
    
    # Verify that it calls prompt and returns results
    tool_counts, reasoning, final_answer = await service.execute_turn(
        chat_session=None,
        current_msg="Hello",
        task_state=mock_task_state,
        turn_context=TurnContext()
    )
    
    assert mock_conn.prompt.called
    assert isinstance(tool_counts, defaultdict)
    assert isinstance(reasoning, list)
    # Since we didn't simulate updates, results should be empty but structured correctly
    assert final_answer == ""
