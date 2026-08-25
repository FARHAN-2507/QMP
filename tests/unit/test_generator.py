"""Tests for test generator module."""

import pytest

from querymind.testing.generator import (
    generate_crud_tests,
    generate_tests_from_endpoints,
)


def test_generate_from_single_endpoint() -> None:
    endpoints = [
        {"path": "/api/users", "method": "GET"},
    ]
    tests = generate_tests_from_endpoints("http://localhost:3000", endpoints)
    assert len(tests) >= 1
    assert tests[0].request.method == "GET"
    assert "localhost:3000" in tests[0].request.url


def test_generate_from_multiple_endpoints() -> None:
    endpoints = [
        {"path": "/api/users", "method": "GET"},
        {"path": "/api/users", "method": "POST"},
        {"path": "/api/posts", "method": "GET"},
    ]
    tests = generate_tests_from_endpoints("http://localhost:3000", endpoints)
    assert len(tests) >= 3


def test_generate_post_with_body() -> None:
    endpoints = [
        {
            "path": "/api/users",
            "method": "POST",
            "request_body": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                },
                "required": ["name", "email"],
            },
        },
    ]
    tests = generate_tests_from_endpoints("http://localhost:3000", endpoints)
    post_tests = [t for t in tests if t.request.method == "POST"]
    assert len(post_tests) >= 1
    assert post_tests[0].request.body is not None
    assert "name" in post_tests[0].request.body
    assert "email" in post_tests[0].request.body


def test_generate_error_cases_for_non_root() -> None:
    endpoints = [
        {"path": "/api/users", "method": "GET"},
    ]
    tests = generate_tests_from_endpoints("http://localhost:3000", endpoints)
    error_tests = [t for t in tests if "non-existent" in t.name]
    assert len(error_tests) >= 1


def test_generate_crud_tests() -> None:
    tests = generate_crud_tests("http://localhost:3000", "/api/users")
    assert len(tests) == 5
    methods = [t.request.method for t in tests]
    assert "GET" in methods
    assert "POST" in methods
    assert "PUT" in methods
    assert "DELETE" in methods


def test_generate_crud_tests_urls() -> None:
    tests = generate_crud_tests("http://localhost:3000", "/api/users")
    urls = [t.request.url for t in tests]
    assert any("/api/users" in u for u in urls)
    assert any("/api/users/1" in u for u in urls)


def test_generate_empty_endpoints() -> None:
    tests = generate_tests_from_endpoints("http://localhost:3000", [])
    assert tests == []


def test_generate_preserves_base_url() -> None:
    endpoints = [{"path": "/test", "method": "GET"}]
    tests = generate_tests_from_endpoints("https://api.example.com/v1", endpoints)
    assert tests[0].request.url.startswith("https://api.example.com/v1")


# --- GenerateTestsBatch tool tests ---


@pytest.mark.asyncio
async def test_batch_tool_generates_single_endpoint():
    from querymind.tools.generator import GenerateTestsBatch

    tool = GenerateTestsBatch()
    result = await tool.execute({
        "base_url": "http://localhost:3000",
        "endpoint": {"path": "/api/users", "method": "GET"},
    })
    assert result.is_success
    assert result.data["count"] >= 1
    assert result.data["endpoint"] == "GET /api/users"


@pytest.mark.asyncio
async def test_batch_tool_with_post_endpoint():
    from querymind.tools.generator import GenerateTestsBatch

    tool = GenerateTestsBatch()
    result = await tool.execute({
        "base_url": "http://localhost:3000",
        "endpoint": {
            "path": "/api/users",
            "method": "POST",
            "request_body": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    })
    assert result.is_success
    assert result.data["count"] >= 1


@pytest.mark.asyncio
async def test_batch_tool_missing_endpoint():
    from querymind.tools.generator import GenerateTestsBatch

    tool = GenerateTestsBatch()
    result = await tool.execute({
        "base_url": "http://localhost:3000",
    })
    assert not result.is_success
    assert "endpoint" in result.error
