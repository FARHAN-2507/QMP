"""Tests for mock tool."""

import pytest

from querymind.tools.mock import GetCurrentTestEnvironment


@pytest.mark.asyncio
async def test_mock_tool_returns_env() -> None:
    tool = GetCurrentTestEnvironment()
    result = await tool.execute({})
    assert result.is_success
    data = result.data
    assert data["environment"] == "development"
    assert data["base_url"] == "http://localhost:3000"
    assert len(data["available_endpoints"]) > 0


def test_mock_tool_schema() -> None:
    tool = GetCurrentTestEnvironment()
    assert tool.name == "get_current_test_environment"
    assert tool.input_schema["type"] == "object"
