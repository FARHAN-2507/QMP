"""Tests for tool abstraction."""

from typing import Any

import pytest

from querymind.tools.base import Tool, ToolResult, ToolStatus


class DummyTool(Tool):
    @property
    def name(self) -> str:
        return "dummy"

    @property
    def description(self) -> str:
        return "A dummy tool"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"x": {"type": "integer"}},
            "required": ["x"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        return ToolResult(status=ToolStatus.SUCCESS, data={"x": arguments["x"]})


def test_tool_result_success() -> None:
    r = ToolResult(status=ToolStatus.SUCCESS, data="ok")
    assert r.is_success is True
    assert r.to_content_string() == "ok"


def test_tool_result_error() -> None:
    r = ToolResult(status=ToolStatus.ERROR, error="boom")
    assert r.is_success is False
    assert "boom" in r.to_content_string()


def test_tool_result_dict_data() -> None:
    r = ToolResult(status=ToolStatus.SUCCESS, data={"key": "value"})
    assert "key" in r.to_content_string()


def test_tool_properties() -> None:
    t = DummyTool()
    assert t.name == "dummy"
    assert t.description == "A dummy tool"
    assert "x" in t.input_schema["properties"]


@pytest.mark.asyncio
async def test_tool_execute() -> None:
    t = DummyTool()
    result = await t.execute({"x": 42})
    assert result.is_success
    assert result.data == {"x": 42}


def test_tool_to_definition() -> None:
    t = DummyTool()
    d = t.to_definition()
    assert d["type"] == "function"
    assert d["function"]["name"] == "dummy"
    assert d["function"]["description"] == "A dummy tool"


def test_to_content_string_truncates_long_result() -> None:
    long_data = "x" * 5000
    r = ToolResult(status=ToolStatus.SUCCESS, data=long_data)
    result = r.to_content_string(max_length=1000)
    assert len(result) < 5000
    assert "truncated" in result


def test_to_content_string_no_truncation_when_short() -> None:
    short_data = "hello"
    r = ToolResult(status=ToolStatus.SUCCESS, data=short_data)
    result = r.to_content_string(max_length=1000)
    assert result == "hello"
