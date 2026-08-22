"""Tests for generate_tests tool."""

import pytest

from querymind.tools.generator import GenerateTests


def test_tool_properties() -> None:
    tool = GenerateTests()
    assert tool.name == "generate_tests"
    assert "base_url" in tool.input_schema["properties"]
    assert "mode" in tool.input_schema["properties"]


@pytest.mark.asyncio
async def test_generate_endpoints_mode() -> None:
    tool = GenerateTests()
    result = await tool.execute({
        "base_url": "http://localhost:3000",
        "mode": "endpoints",
        "endpoints": [
            {"path": "/api/users", "method": "GET"},
        ],
    })
    assert result.is_success
    assert result.data["count"] >= 1


@pytest.mark.asyncio
async def test_generate_crud_mode() -> None:
    tool = GenerateTests()
    result = await tool.execute({
        "base_url": "http://localhost:3000",
        "mode": "crud",
        "resource_path": "/api/users",
    })
    assert result.is_success
    assert result.data["count"] == 5


@pytest.mark.asyncio
async def test_generate_endpoints_requires_list() -> None:
    tool = GenerateTests()
    result = await tool.execute({
        "base_url": "http://localhost:3000",
        "mode": "endpoints",
    })
    assert not result.is_success
    assert "endpoints" in result.error


@pytest.mark.asyncio
async def test_generate_crud_requires_path() -> None:
    tool = GenerateTests()
    result = await tool.execute({
        "base_url": "http://localhost:3000",
        "mode": "crud",
    })
    assert not result.is_success
    assert "resource_path" in result.error


@pytest.mark.asyncio
async def test_generate_bad_mode() -> None:
    tool = GenerateTests()
    result = await tool.execute({
        "base_url": "http://localhost:3000",
        "mode": "invalid",
    })
    assert not result.is_success
    assert "Unknown mode" in result.error


@pytest.mark.asyncio
async def test_generate_empty_endpoints() -> None:
    tool = GenerateTests()
    result = await tool.execute({
        "base_url": "http://localhost:3000",
        "mode": "endpoints",
        "endpoints": [],
    })
    # Empty endpoints list is treated as missing
    assert not result.is_success
    assert "endpoints" in result.error
