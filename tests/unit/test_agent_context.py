"""Tests for agent context."""

from querymind.agent.context import AgentContext
from querymind.llm.client import ChatMessage, Role
from querymind.tools.mock import GetCurrentTestEnvironment
from querymind.tools.registry import ToolRegistry


def test_system_prompt() -> None:
    ctx = AgentContext(tool_registry=ToolRegistry())
    assert "QueryMind" in ctx.get_system_prompt()


def test_custom_system_prompt() -> None:
    ctx = AgentContext(tool_registry=ToolRegistry(), system_prompt="Custom prompt")
    assert ctx.get_system_prompt() == "Custom prompt"


def test_tool_definitions() -> None:
    reg = ToolRegistry()
    reg.register(GetCurrentTestEnvironment())
    ctx = AgentContext(tool_registry=reg)
    defs = ctx.get_tool_definitions()
    assert len(defs) == 1
    assert defs[0].name == "get_current_test_environment"


def test_build_messages_prepends_system() -> None:
    ctx = AgentContext(tool_registry=ToolRegistry())
    messages = [ChatMessage(role=Role.USER, content="hello")]
    result = ctx.build_messages(messages)
    assert len(result) == 2
    assert result[0].role.value == "system"
    assert result[1].role.value == "user"


def test_build_messages_no_duplicate_system() -> None:
    ctx = AgentContext(tool_registry=ToolRegistry())
    messages = [
        ChatMessage(role=Role.SYSTEM, content="Custom system"),
        ChatMessage(role=Role.USER, content="hello"),
    ]
    result = ctx.build_messages(messages)
    assert len(result) == 2
    assert result[0].content == "Custom system"
