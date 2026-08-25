"""Tests for agent context."""

from querymind.agent.context import TOOL_SETS, AgentContext
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


# --- Tool phase filtering tests ---


def test_tool_phase_setup_filters_tools() -> None:
    from querymind.tools.http import SendHttpRequest
    from querymind.tools.mock import GetCurrentTestEnvironment

    reg = ToolRegistry()
    reg.register(GetCurrentTestEnvironment())
    reg.register(SendHttpRequest())
    ctx = AgentContext(tool_registry=reg)

    # Full mode — all tools
    ctx.set_phase("full")
    defs = ctx.get_tool_definitions()
    assert len(defs) == 2

    # Setup phase — filter to setup tools only
    ctx.set_phase("setup")
    defs = ctx.get_tool_definitions()
    # get_current_test_environment is not in setup phase, so should be filtered
    assert len(defs) == 0


def test_tool_phase_invalid_ignored() -> None:
    ctx = AgentContext(tool_registry=ToolRegistry())
    ctx.set_phase("invalid_phase")
    assert ctx._current_phase == "full"


def test_tool_sets_defined() -> None:
    assert "setup" in TOOL_SETS
    assert "testing" in TOOL_SETS
    assert "reporting" in TOOL_SETS
    assert "full" in TOOL_SETS


# --- System prompt consolidation tests ---


def test_system_prompt_consolidation() -> None:
    """Verify prompt changes after first call."""
    ctx = AgentContext(tool_registry=ToolRegistry())

    # First call — bootstrap prompt
    prompt1 = ctx.get_system_prompt()
    assert "CAPABILITIES" in prompt1
    assert len(prompt1) > 500

    # Increment call count
    ctx.increment_call_count()

    # Second call — working prompt
    prompt2 = ctx.get_system_prompt()
    assert "CAPABILITIES" not in prompt2
    assert len(prompt2) < len(prompt1)
