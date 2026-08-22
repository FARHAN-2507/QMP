"""Tests for agent loop (mocked LLM, no real API calls)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from querymind.agent.context import AgentContext
from querymind.agent.loop import AgentLoop
from querymind.agent.state import AgentState, AgentStatus
from querymind.llm.client import ChatResponse, ToolCall
from querymind.tools.executor import ToolExecutor
from querymind.tools.mock import GetCurrentTestEnvironment
from querymind.tools.registry import ToolRegistry


def make_loop(
    llm_response: ChatResponse,
    max_iterations: int = 5,
) -> AgentLoop:
    """Create an AgentLoop with a mocked LLM."""
    reg = ToolRegistry()
    reg.register(GetCurrentTestEnvironment())
    context = AgentContext(tool_registry=reg)
    executor = ToolExecutor(reg)

    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(return_value=llm_response)

    return AgentLoop(
        llm=mock_llm,
        context=context,
        executor=executor,
        max_iterations=max_iterations,
    )


@pytest.mark.asyncio
async def test_loop_text_response() -> None:
    response = ChatResponse(content="Hello! I'm ready.", finish_reason="stop")
    loop = make_loop(response)
    state = AgentState()
    state.add_user_message("hi")

    result = await loop.run(state)

    assert result.status == AgentStatus.COMPLETED
    assert result.final_response == "Hello! I'm ready."
    assert result.iteration == 1


@pytest.mark.asyncio
async def test_loop_tool_then_text() -> None:
    tool_response = ChatResponse(
        tool_calls=[ToolCall(id="c1", name="get_current_test_environment", arguments={})],
        finish_reason="tool_calls",
    )
    text_response = ChatResponse(content="Done!", finish_reason="stop")

    reg = ToolRegistry()
    reg.register(GetCurrentTestEnvironment())
    context = AgentContext(tool_registry=reg)
    executor = ToolExecutor(reg)

    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(side_effect=[tool_response, text_response])

    loop = AgentLoop(llm=mock_llm, context=context, executor=executor, max_iterations=5)
    state = AgentState()
    state.add_user_message("check the environment")

    result = await loop.run(state)

    assert result.status == AgentStatus.COMPLETED
    assert result.final_response == "Done!"
    assert result.iteration == 2
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_call.name == "get_current_test_environment"


@pytest.mark.asyncio
async def test_loop_max_iterations() -> None:
    tool_response = ChatResponse(
        tool_calls=[ToolCall(id="c1", name="get_current_test_environment", arguments={})],
        finish_reason="tool_calls",
    )

    reg = ToolRegistry()
    reg.register(GetCurrentTestEnvironment())
    context = AgentContext(tool_registry=reg)
    executor = ToolExecutor(reg)

    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(return_value=tool_response)

    loop = AgentLoop(llm=mock_llm, context=context, executor=executor, max_iterations=2)
    state = AgentState()
    state.add_user_message("keep going")

    result = await loop.run(state)

    assert result.status == AgentStatus.MAX_ITERATIONS
    assert "2 iterations" in result.final_response


@pytest.mark.asyncio
async def test_loop_llm_error() -> None:
    reg = ToolRegistry()
    context = AgentContext(tool_registry=reg)
    executor = ToolExecutor(reg)

    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(side_effect=RuntimeError("API down"))

    loop = AgentLoop(llm=mock_llm, context=context, executor=executor, max_iterations=5)
    state = AgentState()
    state.add_user_message("test")

    result = await loop.run(state)

    assert result.status == AgentStatus.ERROR
    assert "API down" in result.error
