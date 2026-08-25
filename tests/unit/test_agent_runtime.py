"""Tests for agent runtime."""

from unittest.mock import AsyncMock

import pytest

from querymind.agent.runtime import AgentRuntime
from querymind.agent.state import AgentState, AgentStatus
from querymind.llm.client import ChatResponse
from querymind.llm.groq import GroqProvider


@pytest.mark.asyncio
async def test_runtime_register_default_tools() -> None:
    llm = GroqProvider(api_keys=["test"], model="test")
    runtime = AgentRuntime(llm=llm)
    assert "get_current_test_environment" in runtime.registry


def test_runtime_tools_summary() -> None:
    llm = GroqProvider(api_keys=["test"], model="test")
    runtime = AgentRuntime(llm=llm)
    summary = runtime.get_tools_summary()
    assert "get_current_test_environment" in summary


@pytest.mark.asyncio
async def test_runtime_run() -> None:
    response = ChatResponse(content="I checked the environment.", finish_reason="stop")
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(return_value=response)

    runtime = AgentRuntime(llm=mock_llm)
    state = await runtime.run("check the environment")

    assert state.status == AgentStatus.COMPLETED
    assert state.final_response == "I checked the environment."


def test_session_compression() -> None:
    """Verify old tool results are compressed on session load."""
    llm = GroqProvider(api_keys=["test"], model="test")
    runtime = AgentRuntime(llm=llm)

    # Create state with many tool results
    runtime._state = AgentState()
    runtime._state.add_user_message("test")

    # Add old tool results (long content)
    for i in range(10):
        runtime._state.add_tool_result(
            f"c{i}",
            "x" * 500,  # Long content
            "send_request",
        )

    # Add recent messages
    runtime._state.add_user_message("done")

    # Compress
    runtime._compress_loaded_session()

    # Old tool results should be compressed
    tool_msgs = [m for m in runtime._state.messages if m.role.value == "tool"]
    old_compressed = [m for m in tool_msgs if "compressed" in (m.content or "")]
    assert len(old_compressed) > 0
    # All compressed messages should be short
    for m in old_compressed:
        assert len(m.content) < 50
