"""Tests for LLM abstraction layer."""

from querymind.llm.client import (
    ChatMessage,
    ChatResponse,
    Role,
    ToolCall,
    ToolDefinition,
)


def test_chat_message_to_dict() -> None:
    msg = ChatMessage(role=Role.USER, content="Hello")
    d = msg.to_provider_dict()
    assert d == {"role": "user", "content": "Hello"}


def test_chat_message_system() -> None:
    msg = ChatMessage(role=Role.SYSTEM, content="You are a helpful assistant.")
    d = msg.to_provider_dict()
    assert d["role"] == "system"


def test_chat_message_tool() -> None:
    msg = ChatMessage(role=Role.TOOL, content='{"ok": true}', tool_call_id="call_123")
    d = msg.to_provider_dict()
    assert d["role"] == "tool"
    assert d["tool_call_id"] == "call_123"


def test_tool_definition_to_provider_dict() -> None:
    td = ToolDefinition(
        name="send_http_request",
        description="Send an HTTP request",
        parameters={
            "type": "object",
            "properties": {
                "method": {"type": "string"},
                "url": {"type": "string"},
            },
        },
    )
    d = td.to_provider_dict()
    assert d["type"] == "function"
    assert d["function"]["name"] == "send_http_request"
    assert d["function"]["description"] == "Send an HTTP request"
    assert "properties" in d["function"]["parameters"]


def test_tool_call() -> None:
    tc = ToolCall(id="call_1", name="send_http_request", arguments={"method": "GET", "url": "http://test"})
    assert tc.id == "call_1"
    assert tc.arguments["method"] == "GET"


def test_chat_response_no_tool_calls() -> None:
    r = ChatResponse(content="Hello!", finish_reason="stop")
    assert r.has_tool_calls is False
    assert r.content == "Hello!"


def test_chat_response_with_tool_calls() -> None:
    r = ChatResponse(
        tool_calls=[ToolCall(id="c1", name="test_tool", arguments={})],
        finish_reason="tool_calls",
    )
    assert r.has_tool_calls is True


def test_chat_response_usage() -> None:
    r = ChatResponse(
        content="ok",
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    )
    assert r.usage["total_tokens"] == 15
