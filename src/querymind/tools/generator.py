"""Generate tests tool — lets the agent create test cases from API info.

The agent can generate tests from:
1. OpenAPI/Swagger spec (already imported)
2. Manual endpoint definitions
3. CRUD patterns for known resources
"""

from __future__ import annotations

from typing import Any

from querymind.testing.generator import (
    generate_crud_tests,
    generate_tests_from_endpoints,
)
from querymind.testing.models import ApiTestCase
from querymind.testing.runner import run_test
from querymind.tools.base import Tool, ToolResult, ToolStatus


class GenerateTests(Tool):
    """Generate and optionally run test cases for an API."""

    @property
    def name(self) -> str:
        return "generate_tests"

    @property
    def description(self) -> str:
        return (
            "Generate test cases for an API. Provide endpoint definitions or "
            "a resource path for CRUD tests. Can run tests immediately or "
            "return them for review."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "base_url": {
                    "type": "string",
                    "description": "Base URL of the API (e.g., http://localhost:3000)",
                },
                "mode": {
                    "type": "string",
                    "enum": ["endpoints", "crud"],
                    "description": (
                        "'endpoints' — generate from explicit endpoint list\n"
                        "'crud' — generate CRUD tests for a resource path"
                    ),
                },
                "endpoints": {
                    "type": "array",
                    "description": "List of endpoint definitions (for mode='endpoints')",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "method": {"type": "string"},
                            "parameters": {"type": "array"},
                            "request_body": {"type": "object"},
                            "responses": {"type": "object"},
                        },
                        "required": ["path", "method"],
                    },
                },
                "resource_path": {
                    "type": "string",
                    "description": "Resource path for CRUD mode (e.g., /api/users)",
                },
                "run_immediately": {
                    "type": "boolean",
                    "description": "Run tests after generating (default: false)",
                },
            },
            "required": ["base_url", "mode"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        try:
            base_url = arguments["base_url"]
            mode = arguments["mode"]
            run_immediately = arguments.get("run_immediately", False)

            # Generate test cases
            test_cases: list[ApiTestCase] = []

            if mode == "endpoints":
                endpoints = arguments.get("endpoints", [])
                if not endpoints:
                    return ToolResult(
                        status=ToolStatus.ERROR,
                        error="mode='endpoints' requires 'endpoints' list",
                    )
                test_cases = generate_tests_from_endpoints(base_url, endpoints)

            elif mode == "crud":
                resource_path = arguments.get("resource_path")
                if not resource_path:
                    return ToolResult(
                        status=ToolStatus.ERROR,
                        error="mode='crud' requires 'resource_path'",
                    )
                test_cases = generate_crud_tests(base_url, resource_path)

            else:
                return ToolResult(
                    status=ToolStatus.ERROR,
                    error=f"Unknown mode: {mode}",
                )

            if not test_cases:
                return ToolResult(
                    status=ToolStatus.SUCCESS,
                    data={
                        "message": "No test cases generated",
                        "count": 0,
                        "tests": [],
                    },
                )

            # Run tests if requested
            results = []
            if run_immediately:
                for tc in test_cases:
                    result = await run_test(tc)
                    results.append({  # pyright: ignore[reportUnknownMemberType]
                        "test_name": result.test_name,
                        "status": result.status.value,
                        "passed": result.passed_count,
                        "failed": result.failed_count,
                        "summary": result.summary(),
                    })

            # Format test cases for output
            test_summaries = []
            for tc in test_cases:
                test_summaries.append({  # pyright: ignore[reportUnknownMemberType]
                    "name": tc.name,
                    "description": tc.description,
                    "method": tc.request.method,
                    "url": tc.request.url,
                    "assertions": len(tc.assertions),
                })

            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={
                    "count": len(test_cases),
                    "tests": test_summaries,
                    "results": results if results else None,
                },
                metadata={
                    "test_count": len(test_cases),
                    "mode": mode,
                    "ran": run_immediately,
                },
            )

        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Test generation failed: {e}",
            )


class GenerateTestsBatch(Tool):
    """Generate test cases for a single endpoint (batch mode).

    Use this tool instead of generate_tests when the API has many endpoints.
    Call it once per endpoint to keep token usage low.
    """

    @property
    def name(self) -> str:
        return "generate_tests_batch"

    @property
    def description(self) -> str:
        return (
            "Generate test cases for a SINGLE endpoint. Use this instead of "
            "generate_tests when the API has many endpoints (>3). Call once "
            "per endpoint, then run the returned tests. Saves tokens by "
            "processing one endpoint at a time."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "base_url": {
                    "type": "string",
                    "description": "Base URL of the API",
                },
                "endpoint": {
                    "type": "object",
                    "description": "Single endpoint definition",
                    "properties": {
                        "path": {"type": "string"},
                        "method": {"type": "string"},
                        "parameters": {"type": "array"},
                        "request_body": {"type": "object"},
                        "responses": {"type": "object"},
                    },
                    "required": ["path", "method"],
                },
                "run_immediately": {
                    "type": "boolean",
                    "description": "Run tests after generating (default: false)",
                },
            },
            "required": ["base_url", "endpoint"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        try:
            base_url = arguments["base_url"]
            endpoint = arguments["endpoint"]
            run_immediately = arguments.get("run_immediately", False)

            # Generate tests for single endpoint
            test_cases = generate_tests_from_endpoints(base_url, [endpoint])

            if not test_cases:
                return ToolResult(
                    status=ToolStatus.SUCCESS,
                    data={"message": "No test cases generated", "count": 0},
                )

            # Run tests if requested
            results = []
            if run_immediately:
                for tc in test_cases:
                    result = await run_test(tc)
                    results.append({  # pyright: ignore[reportUnknownMemberType]
                        "test_name": result.test_name,
                        "status": result.status.value,
                        "passed": result.passed_count,
                        "failed": result.failed_count,
                        "summary": result.summary(),
                    })

            # Format output
            test_summaries = []
            for tc in test_cases:
                test_summaries.append({  # pyright: ignore[reportUnknownMemberType]
                    "name": tc.name,
                    "method": tc.request.method,
                    "url": tc.request.url,
                    "assertions": len(tc.assertions),
                })

            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={
                    "endpoint": f"{endpoint.get('method', 'GET')} {endpoint.get('path', '/')}",
                    "count": len(test_cases),
                    "tests": test_summaries,
                    "results": results if results else None,
                },
            )

        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Test generation failed: {e}",
            )
