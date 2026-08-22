"""Tests for tool registry and executor."""

from typing import Any

import pytest

from querymind.llm.client import ToolCall
from querymind.tools.base import Tool, ToolResult, ToolStatus
from querymind.tools.executor import ToolExecutor
from querymind.tools.registry import ToolRegistry


class SimpleTool(Tool):
    @property
    def name(self) -> str:
        return "simple"

    @property
    def description(self) -> str:
        return "Simple tool"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"msg": {"type": "string"}},
            "required": ["msg"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        return ToolResult(status=ToolStatus.SUCCESS, data=f"echo: {arguments['msg']}")


class NoArgsTool(Tool):
    @property
    def name(self) -> str:
        return "noargs"

    @property
    def description(self) -> str:
        return "No args tool"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        return ToolResult(status=ToolStatus.SUCCESS, data="done")


# --- Registry tests ---


def test_register_and_resolve() -> None:
    reg = ToolRegistry()
    tool = SimpleTool()
    reg.register(tool)
    assert reg.resolve("simple") is tool
    assert reg.resolve("nonexistent") is None


def test_list_tools() -> None:
    reg = ToolRegistry()
    reg.register(SimpleTool())
    reg.register(NoArgsTool())
    assert len(reg) == 2
    assert "simple" in reg
    assert "noargs" in reg
    assert set(reg.list_names()) == {"simple", "noargs"}


def test_to_definitions() -> None:
    reg = ToolRegistry()
    reg.register(SimpleTool())
    defs = reg.to_definitions()
    assert len(defs) == 1
    assert defs[0]["function"]["name"] == "simple"


# --- Executor tests ---


@pytest.mark.asyncio
async def test_executor_success() -> None:
    reg = ToolRegistry()
    reg.register(SimpleTool())
    executor = ToolExecutor(reg)
    tc = ToolCall(id="c1", name="simple", arguments={"msg": "hello"})
    result = await executor.execute(tc)
    assert result.is_success
    assert result.data == "echo: hello"


@pytest.mark.asyncio
async def test_executor_tool_not_found() -> None:
    reg = ToolRegistry()
    executor = ToolExecutor(reg)
    tc = ToolCall(id="c1", name="missing", arguments={})
    result = await executor.execute(tc)
    assert not result.is_success
    assert "not found" in result.error


@pytest.mark.asyncio
async def test_executor_missing_required_arg() -> None:
    reg = ToolRegistry()
    reg.register(SimpleTool())
    executor = ToolExecutor(reg)
    tc = ToolCall(id="c1", name="simple", arguments={})
    result = await executor.execute(tc)
    assert not result.is_success
    assert result.status == ToolStatus.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_executor_no_args_tool() -> None:
    reg = ToolRegistry()
    reg.register(NoArgsTool())
    executor = ToolExecutor(reg)
    tc = ToolCall(id="c1", name="noargs", arguments={})
    result = await executor.execute(tc)
    assert result.is_success
    assert result.data == "done"
