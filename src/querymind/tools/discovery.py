"""API discovery tool — probes a base URL to discover available endpoints.

This tool sends requests to common paths to find what an API exposes,
even without an OpenAPI spec.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urljoin

import httpx

from querymind.tools.base import Tool, ToolResult, ToolStatus

# Common API paths to probe
COMMON_PATHS = [
    "/",
    "/api",
    "/api/v1",
    "/api/v2",
    "/health",
    "/healthz",
    "/api/health",
    "/status",
    "/api/status",
    "/docs",
    "/api-docs",
    "/swagger",
    "/swagger.json",
    "/openapi.json",
    "/api-docs.json",
    "/redoc",
    "/api/users",
    "/api/auth",
    "/api/auth/login",
    "/api/auth/register",
    "/api/products",
    "/api/items",
    "/api/posts",
    "/api/comments",
    "/api/settings",
    "/api/config",
    "/graphql",
    "/.well-known/openapi.json",
]


class DiscoverApi(Tool):
    """Discover API endpoints by probing common paths."""

    def __init__(self, auth_provider: Any | None = None) -> None:
        self._auth_provider = auth_provider

    @property
    def name(self) -> str:
        return "discover_api"

    @property
    def description(self) -> str:
        return (
            "Discover available endpoints on a base URL by probing common paths. "
            "Returns a list of discovered endpoints with their HTTP methods and "
            "status codes. Use this to find out what an API offers."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "base_url": {
                    "type": "string",
                    "description": "Base URL of the API (e.g. http://localhost:3000)",
                },
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of specific paths to probe (overrides defaults)",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Request timeout in seconds (default: 5)",
                },
            },
            "required": ["base_url"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        base_url = arguments["base_url"].rstrip("/")
        paths = arguments.get("paths") or COMMON_PATHS
        timeout = arguments.get("timeout", 5)

        discovered: list[dict[str, Any]] = []

        try:
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=False, verify=False
            ) as client:
                for path in paths:
                    url = urljoin(base_url + "/", path.lstrip("/"))
                    try:
                        # Apply auth headers if configured
                        headers: dict[str, str] = {}
                        if self._auth_provider:
                            headers = self._auth_provider.apply_auth(headers, url)

                        start = time.monotonic()
                        response = await client.request("GET", url, headers=headers)
                        elapsed_ms = int((time.monotonic() - start) * 1000)

                        # Keep endpoints that return real content (not 404/405/500)
                        if response.status_code not in (404, 405, 500, 502, 503):
                            discovered.append({
                                "path": path,
                                "status_code": response.status_code,
                                "method": response.headers.get("allow", "GET"),
                                "elapsed_ms": elapsed_ms,
                                "content_type": response.headers.get("content-type", ""),
                            })
                    except httpx.RequestError:
                        continue

        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Discovery failed: {e}",
            )

        if not discovered:
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={
                    "message": f"No endpoints discovered at {base_url}",
                    "suggestion": "Try providing a specific URL or check if the API is running.",
                },
            )

        return ToolResult(
            status=ToolStatus.SUCCESS,
            data={
                "base_url": base_url,
                "endpoints": discovered,
                "total_found": len(discovered),
            },
            metadata={"base_url": base_url, "endpoints_found": len(discovered)},
        )
