"""Tests for OpenAPI parser tool."""

import pytest

from querymind.tools.openapi import ImportOpenApi, parse_openapi_spec

SAMPLE_SPEC = {
    "openapi": "3.0.0",
    "info": {
        "title": "Test API",
        "version": "1.0.0",
        "description": "A test API",
    },
    "servers": [{"url": "http://localhost:3000"}],
    "paths": {
        "/api/users": {
            "get": {
                "summary": "List users",
                "operationId": "listUsers",
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                    },
                ],
                "responses": {
                    "200": {"description": "Success"},
                },
            },
            "post": {
                "summary": "Create user",
                "operationId": "createUser",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "email": {"type": "string"},
                                },
                                "required": ["name", "email"],
                            },
                        },
                    },
                },
                "responses": {
                    "201": {"description": "Created"},
                },
            },
        },
        "/api/users/{id}": {
            "get": {
                "summary": "Get user by ID",
                "operationId": "getUser",
                "parameters": [
                    {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}},
                ],
                "responses": {
                    "200": {"description": "Success"},
                    "404": {"description": "Not found"},
                },
            },
        },
    },
}


def test_parse_openapi_spec_info() -> None:
    result = parse_openapi_spec(SAMPLE_SPEC)
    assert result["title"] == "Test API"
    assert result["version"] == "1.0.0"
    assert result["description"] == "A test API"


def test_parse_openapi_spec_endpoints() -> None:
    result = parse_openapi_spec(SAMPLE_SPEC)
    assert result["totalEndpoints"] == 3
    methods = [(e["method"], e["path"]) for e in result["endpoints"]]
    assert ("GET", "/api/users") in methods
    assert ("POST", "/api/users") in methods
    assert ("GET", "/api/users/{id}") in methods


def test_parse_openapi_spec_parameters() -> None:
    result = parse_openapi_spec(SAMPLE_SPEC)
    get_users = next(
        e for e in result["endpoints"]
        if e["path"] == "/api/users" and e["method"] == "GET"
    )
    assert len(get_users["parameters"]) == 1
    assert get_users["parameters"][0]["name"] == "limit"
    assert get_users["parameters"][0]["in"] == "query"


def test_parse_openapi_spec_request_body() -> None:
    result = parse_openapi_spec(SAMPLE_SPEC)
    post_users = next(
        e for e in result["endpoints"]
        if e["path"] == "/api/users" and e["method"] == "POST"
    )
    assert "requestBody" in post_users
    props = post_users["requestBody"]["properties"]
    assert "name" in props
    assert "email" in props


def test_parse_openapi_spec_servers() -> None:
    result = parse_openapi_spec(SAMPLE_SPEC)
    assert result["servers"] == ["http://localhost:3000"]


@pytest.mark.asyncio
async def test_import_openapi_inline() -> None:
    import json

    tool = ImportOpenApi()
    result = await tool.execute({"spec_json": json.dumps(SAMPLE_SPEC)})
    assert result.is_success
    assert result.data["title"] == "Test API"
    assert result.data["totalEndpoints"] == 3


@pytest.mark.asyncio
async def test_import_openapi_no_input() -> None:
    tool = ImportOpenApi()
    result = await tool.execute({})
    assert not result.is_success
    assert "must be provided" in result.error


@pytest.mark.asyncio
async def test_import_openapi_invalid_json() -> None:
    tool = ImportOpenApi()
    result = await tool.execute({"spec_json": "not json"})
    assert not result.is_success
    assert "Invalid JSON" in result.error


def test_import_openapi_tool_properties() -> None:
    tool = ImportOpenApi()
    assert tool.name == "import_openapi"
    assert "url" in tool.input_schema["properties"]
    assert "spec_json" in tool.input_schema["properties"]
