"""Tests for agent runtime."""

from unittest.mock import AsyncMock

import pytest

from querymind.agent.runtime import AgentRuntime
from querymind.agent.state import AgentStatus
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
