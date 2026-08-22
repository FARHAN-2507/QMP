"""Test engine tool — lets the agent run structured test cases.

The agent defines test cases with requests and assertions.
The deterministic engine executes them and evaluates results.
"""

from __future__ import annotations

from typing import Any

from querymind.testing.models import (
    ApiTestCase,
    ApiTestRequest,
    Assertion,
    AssertionType,
)
from querymind.testing.runner import run_test
from querymind.tools.base import Tool, ToolResult, ToolStatus


class RunTest(Tool):
    """Run a single test case against an API endpoint."""

    def __init__(self, auth_provider: Any | None = None) -> None:
        self._auth_provider = auth_provider

    @property
    def name(self) -> str:
        return "run_test"

    @property
    def description(self) -> str:
        return (
            "Run a single test case against an API endpoint. Define the request "
            "(method, URL, headers, body) and assertions (status code, headers, "
            "JSON properties, response time). Returns deterministic pass/fail results."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Test name",
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
                    "description": "HTTP method",
                },
                "url": {
                    "type": "string",
                    "description": "Full URL to test",
                },
                "headers": {
                    "type": "object",
                    "description": "HTTP headers",
                },
                "body": {
                    "type": "object",
                    "description": "Request body (for POST/PUT/PATCH)",
                },
                "assertions": {
                    "type": "array",
                    "description": "List of assertions to evaluate",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": [
                                    "status_code",
                                    "status_code_range",
                                    "header_exists",
                                    "header_equals",
                                    "json_property_exists",
                                    "json_property_equals",
                                    "json_property_type",
                                    "body_contains",
                                    "response_time_ms",
                                    "body_not_empty",
                                ],
                                "description": "Assertion type",
                            },
                            "expected": {
                                "description": "Expected value",
                            },
                            "path": {
                                "type": "string",
                                "description": "JSON path for property assertions (dot notation)",
                            },
                            "description": {
                                "type": "string",
                                "description": "Human-readable description of what this checks",
                            },
                        },
                        "required": ["type"],
                    },
                },
            },
            "required": ["name", "method", "url"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        try:
            # Build request
            request = ApiTestRequest(
                method=arguments["method"].upper(),
                url=arguments["url"],
                headers=arguments.get("headers", {}),
                body=arguments.get("body"),
            )

            # Build assertions
            assertions = []
            for a in arguments.get("assertions", []):
                assertions.append(Assertion(  # pyright: ignore[reportUnknownMemberType]
                    type=AssertionType(a["type"]),
                    expected=a.get("expected"),
                    path=a.get("path"),
                    description=a.get("description", ""),
                ))

            test_case = ApiTestCase(
                name=arguments["name"],
                request=request,
                assertions=assertions,  # pyright: ignore[reportUnknownArgumentType]
            )

            result = await run_test(test_case, auth_provider=self._auth_provider)

            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={
                    "test_name": result.test_name,
                    "status": result.status.value,
                    "passed": result.passed_count,
                    "failed": result.failed_count,
                    "total": len(result.assertion_results),
                    "elapsed_ms": result.elapsed_ms,
                    "status_code": result.response_status_code,
                    "summary": result.summary(),
                    "details": [
                        {
                            "assertion": a.assertion.description or a.assertion.type.value,
                            "passed": a.passed,
                            "message": a.message,
                        }
                        for a in result.assertion_results
                    ],
                },
                metadata={
                    "test_name": result.test_name,
                    "status": result.status.value,
                },
            )

        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Test execution failed: {e}",
            )
