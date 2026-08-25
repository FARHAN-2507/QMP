"""Smoke test tool — lets the agent run quick smoke tests.

The agent calls this tool to run smoke tests without generating
full test suites. Fast, no token cost for test generation.
"""

from __future__ import annotations

from typing import Any

from querymind.testing.models import TestStatus
from querymind.testing.smoke import SmokeTestConfig, run_smoke_tests
from querymind.tools.base import Tool, ToolResult, ToolStatus


class RunSmokeTests(Tool):
    """Run smoke tests against an API endpoint."""

    def __init__(self, auth_provider: Any | None = None) -> None:
        self._auth_provider = auth_provider

    @property
    def name(self) -> str:
        return "run_smoke_tests"

    @property
    def description(self) -> str:
        return (
            "Run fast smoke tests against an API. Tests health endpoints, "
            "discovers available endpoints, and validates basic functionality. "
            "No token cost for test generation — tests are defined in code."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "base_url": {
                    "type": "string",
                    "description": "Base URL of the API to test",
                },
                "openapi_url": {
                    "type": "string",
                    "description": "Optional OpenAPI spec URL for smarter tests",
                },
                "timeout_ms": {
                    "type": "integer",
                    "description": "Max response time in milliseconds (default: 5000)",
                },
                "include_write_tests": {
                    "type": "boolean",
                    "description": "Include POST/PUT/DELETE tests (default: false)",
                },
            },
            "required": ["base_url"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        try:
            base_url = arguments["base_url"]
            timeout_ms = arguments.get("timeout_ms", 5000)
            include_write = arguments.get("include_write_tests", False)

            # Create config
            config = SmokeTestConfig(
                base_url=base_url,
                timeout_ms=timeout_ms,
                include_write_tests=include_write,
                auth_provider=self._auth_provider,
            )

            # Load OpenAPI spec if provided
            spec = None
            openapi_url = arguments.get("openapi_url")
            if openapi_url:
                try:
                    import httpx
                    async with httpx.AsyncClient(verify=False, timeout=30) as client:
                        response = await client.get(openapi_url)
                        response.raise_for_status()
                        spec = response.json()
                except Exception as e:
                    return ToolResult(
                        status=ToolStatus.ERROR,
                        error=f"Failed to load OpenAPI spec: {e}",
                    )

            # Run smoke tests
            results = await run_smoke_tests(config, spec=spec)

            # Summarize results
            total = len(results)
            passed = sum(1 for r in results if r.status == TestStatus.PASSED)
            failed = sum(1 for r in results if r.status == TestStatus.FAILED)
            errors = sum(1 for r in results if r.status == TestStatus.ERROR)

            # Build detailed results
            details: list[dict[str, object]] = []
            for r in results:
                details.append({
                    "test": r.test_name,
                    "status": r.status.value,
                    "elapsed_ms": r.elapsed_ms,
                    "status_code": r.response_status_code,
                    "error": r.error,
                })

            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={
                    "summary": {
                        "total": total,
                        "passed": passed,
                        "failed": failed,
                        "errors": errors,
                    },
                    "details": details,
                },
                metadata={
                    "base_url": base_url,
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "errors": errors,
                },
            )

        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Smoke test failed: {e}",
            )
