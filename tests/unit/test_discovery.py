"""Tests for API discovery tool."""

import pytest

from querymind.tools.discovery import DiscoverApi


def test_discover_api_tool_properties() -> None:
    tool = DiscoverApi()
    assert tool.name == "discover_api"
    assert "base_url" in tool.input_schema["properties"]
    assert "base_url" in tool.input_schema["required"]


@pytest.mark.asyncio
async def test_discover_api_bad_url() -> None:
    tool = DiscoverApi()
    result = await tool.execute({
        "base_url": "http://192.0.2.1:12345",
        "paths": ["/test"],
        "timeout": 3,
    })
    assert result.is_success
    # When nothing is found, returns a message
    assert "message" in result.data or result.data.get("total_found", 0) == 0
