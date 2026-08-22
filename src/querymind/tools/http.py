"""HTTP request tool — sends real HTTP requests to target APIs.

This is the first real QueryMind capability. It supports
GET, POST, PUT, PATCH, DELETE with headers, body, and timeouts.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from querymind.tools.base import Tool, ToolResult, ToolStatus


class SendHttpRequest(Tool):
    """Send an HTTP request to a target API."""

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
                    "enum": ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
                    "description": "HTTP method",
                },
                "url": {
                    "type": "string",
                    "description": "Full URL to send the request to",
                },
                "headers": {
                    "type": "object",
                    "description": "Optional HTTP headers as key-value pairs",
                },
                "body": {
                    "type": "object",
                    "description": "Optional JSON body for POST/PUT/PATCH requests",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Request timeout in seconds (default: 30)",
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

        try:
            start = time.monotonic()
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
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
