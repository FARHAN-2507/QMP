"""Tests for Groq provider (mocked, no real API calls)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from querymind.llm.client import ChatMessage, Role, ToolDefinition
from querymind.llm.groq import GroqProvider


def test_validate_config_missing_key() -> None:
    provider = GroqProvider(api_key="", model="test-model")
    assert provider.validate_config() is False


def test_validate_config_with_key() -> None:
    provider = GroqProvider(api_key="gsk_test_key", model="test-model")
    assert provider.validate_config() is True


def test_validate_config_missing_model() -> None:
    provider = GroqProvider(api_key="gsk_test_key", model="")
    assert provider.validate_config() is True


@pytest.mark.asyncio
async def test_chat_raises_without_config() -> None:
    provider = GroqProvider(api_key="", model="test-model")
    with pytest.raises(ValueError, match="not configured"):
        await provider.chat(messages=[ChatMessage(role=Role.USER, content="hi")])


@pytest.mark.asyncio
async def test_chat_basic_response() -> None:
    provider = GroqProvider(api_key="gsk_test_key", model="test-model")

    mock_message = MagicMock()
    mock_message.content = "Hello from Groq"
    mock_message.tool_calls = None

    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_choice.finish_reason = "stop"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.model = "test-model"
    mock_response.usage = MagicMock(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
    )

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch.object(provider, "_get_client", return_value=mock_client):
        result = await provider.chat(
            messages=[ChatMessage(role=Role.USER, content="Hello")]
        )

    assert result.content == "Hello from Groq"
    assert result.has_tool_calls is False
    assert result.model == "test-model"
    assert result.usage["total_tokens"] == 15


@pytest.mark.asyncio
async def test_chat_with_tool_calls() -> None:
    provider = GroqProvider(api_key="gsk_test_key", model="test-model")

    mock_func = MagicMock()
    mock_func.name = "send_http_request"
    mock_func.arguments = '{"method": "GET", "url": "http://test"}'

    mock_tool_call = MagicMock()
    mock_tool_call.id = "call_abc"
    mock_tool_call.function = mock_func

    mock_message = MagicMock()
    mock_message.content = None
    mock_message.tool_calls = [mock_tool_call]

    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_choice.finish_reason = "tool_calls"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.model = "test-model"
    mock_response.usage = None

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch.object(provider, "_get_client", return_value=mock_client):
        result = await provider.chat(
            messages=[ChatMessage(role=Role.USER, content="Call the tool")],
            tools=[ToolDefinition(name="send_http_request", description="desc")],
        )

    assert result.has_tool_calls is True
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "send_http_request"
    assert result.tool_calls[0].arguments["method"] == "GET"


@pytest.mark.asyncio
async def test_chat_with_tools_in_payload() -> None:
    provider = GroqProvider(api_key="gsk_test_key", model="test-model")

    mock_message = MagicMock()
    mock_message.content = "I don't need tools right now"
    mock_message.tool_calls = None

    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_choice.finish_reason = "stop"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.model = "test-model"
    mock_response.usage = None

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    tools = [ToolDefinition(name="my_tool", description="A test tool")]

    with patch.object(provider, "_get_client", return_value=mock_client):
        result = await provider.chat(
            messages=[ChatMessage(role=Role.USER, content="Hello")],
            tools=tools,
            temperature=0.5,
            max_tokens=100,
        )

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["temperature"] == 0.5
    assert call_kwargs["max_tokens"] == 100
    assert len(call_kwargs["tools"]) == 1
    assert result.content == "I don't need tools right now"
