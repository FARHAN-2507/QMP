"""Tests for HTTP tool."""

import pytest

from querymind.tools.http import SendHttpRequest


def test_http_tool_schema() -> None:
    tool = SendHttpRequest()
    assert tool.name == "send_http_request"
    schema = tool.input_schema
    assert schema["type"] == "object"
    assert "method" in schema["properties"]
    assert "url" in schema["properties"]


@pytest.mark.asyncio
async def test_http_tool_bad_url() -> None:
    """Test with an unreachable URL returns error."""
    tool = SendHttpRequest()
    result = await tool.execute({
        "method": "GET",
        "url": "http://192.0.2.1:12345/test",
        "timeout": 3,
    })
    assert not result.is_success
