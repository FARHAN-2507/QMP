"""HTTP request tool — sends real HTTP requests to target APIs.

This is the first real QueryMind capability. It supports
GET, POST, PUT, PATCH, DELETE with headers, body, and timeouts.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from querymind.security.provider import AuthProvider
from querymind.tools.base import Tool, ToolResult, ToolStatus


class SendHttpRequest(Tool):
    """Send an HTTP request to a target API."""

    def __init__(self, auth_provider: AuthProvider | None = None) -> None:
        self._auth_provider = auth_provider

    @property
    def name(self) -> str:
        return "send_http_request"

    @property
    def description(self) -> str:
        return (
            "Send an HTTP request to a URL. Supports GET, POST, PUT, PATCH, DELETE. "
            "Use this to test API endpoints, check responses, and investigate behavior."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "description": "HTTP method: GET, POST, PUT, PATCH, DELETE",
                },
                "url": {
                    "type": "string",
                    "description": "Full URL to send the request to",
                },
                "body": {
                    "type": "object",
                    "description": "Optional JSON body for POST/PUT/PATCH",
                },
            },
            "required": ["method", "url"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        method = arguments["method"].upper()
        url = arguments["url"]
        headers = arguments.get("headers", {})
        body = arguments.get("body")
        timeout = arguments.get("timeout", 30)

        # Apply auth headers if configured
        if self._auth_provider:
            headers = self._auth_provider.apply_auth(headers, url)

        try:
            start = time.monotonic()
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True, verify=False,
            ) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body,
                )
            elapsed_ms = int((time.monotonic() - start) * 1000)

            # Truncate response body to avoid overwhelming the LLM
            try:
                resp_body = response.json()
            except Exception:
                resp_body = response.text[:2000]

            # Check for auth errors
            if response.status_code in (401, 403):
                return ToolResult(
                    status=ToolStatus.AUTH_REQUIRED,
                    error=(
                        f"Authentication required ({response.status_code}). "
                        "Use /auth set to configure credentials."
                    ),
                    data={
                        "status_code": response.status_code,
                        "body": resp_body,
                        "url": url,
                        "method": method,
                    },
                    metadata={"url": url, "method": method, "status": response.status_code},
                )

            data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": resp_body,
                "elapsed_ms": elapsed_ms,
                "success": 200 <= response.status_code < 400,
            }

            return ToolResult(
                status=ToolStatus.SUCCESS,
                data=data,
                metadata={"url": url, "method": method, "status": response.status_code},
            )

        except httpx.TimeoutException:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Request timed out after {timeout}s: {method} {url}",
            )
        except httpx.RequestError as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Request failed: {method} {url} — {e}",
            )
