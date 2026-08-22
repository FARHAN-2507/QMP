"""Mock tool for Phase 2 — get_current_test_environment.

This tool returns information about the current testing environment.
It exists to verify the agent loop works end-to-end without
connecting to any real APIs.
"""

from __future__ import annotations

from typing import Any

from querymind.tools.base import Tool, ToolResult, ToolStatus


class GetCurrentTestEnvironment(Tool):
    """Returns information about the current test environment."""

    @property
    def name(self) -> str:
        return "get_current_test_environment"

    @property
    def description(self) -> str:
        return (
            "Returns information about the current testing environment, "
            "including the configured API base URL and available endpoints. "
            "Use this to understand what environment you are testing against."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        return ToolResult(
            status=ToolStatus.SUCCESS,
            data={
                "environment": "development",
                "base_url": "http://localhost:3000",
                "available_endpoints": [
                    {"method": "POST", "path": "/api/auth/login"},
                    {"method": "POST", "path": "/api/auth/register"},
                    {"method": "GET", "path": "/api/users/me"},
                    {"method": "GET", "path": "/api/health"},
                ],
                "note": "This is a mock environment for Phase 2 testing.",
            },
        )
