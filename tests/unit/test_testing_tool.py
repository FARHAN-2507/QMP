"""Tests for test engine tool."""

import pytest

from querymind.tools.testing import RunTest


def test_run_test_tool_properties() -> None:
    tool = RunTest()
    assert tool.name == "run_test"
    assert "method" in tool.input_schema["properties"]
    assert "url" in tool.input_schema["properties"]
    assert "assertions" in tool.input_schema["properties"]


@pytest.mark.asyncio
async def test_run_test_bad_url() -> None:
    tool = RunTest()
    result = await tool.execute({
        "name": "test bad url",
        "method": "GET",
        "url": "http://192.0.2.1:12345/test",
        "assertions": [
            {"type": "status_code", "expected": 200},
        ],
    })
    assert result.is_success  # tool executed correctly
    assert result.data["status"] == "error"  # but the test errored


@pytest.mark.asyncio
async def test_run_test_no_assertions() -> None:
    tool = RunTest()
    result = await tool.execute({
        "name": "no assertions",
        "method": "GET",
        "url": "http://192.0.2.1:12345/test",
        "assertions": [],
    })
    assert result.is_success
    assert result.data["status"] in ("passed", "error")
