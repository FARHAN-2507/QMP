"""Curl parser tool — extracts request details from curl commands.

When the user pastes a curl command, this tool parses it and
automatically configures auth + sends the request.
"""

from __future__ import annotations

import re
from typing import Any

from querymind.security.provider import AuthProvider
from querymind.tools.base import Tool, ToolResult, ToolStatus


def parse_curl(curl_cmd: str) -> dict[str, Any]:
    """Parse a curl command into components.

    Returns dict with: method, url, headers, body, auth_type, auth_value
    """
    # Remove line continuations
    curl_cmd = curl_cmd.replace("\\\n", " ").replace("\\\r\n", " ")

    result: dict[str, Any] = {
        "method": "GET",
        "url": "",
        "headers": {},
        "body": None,
        "auth_type": None,
        "auth_value": None,
    }

    # Extract URL - look for quotes after curl or -X
    url_match = re.search(r"""(?:curl\s+)(?:['"]?)(https?://[^\s'"]+)""", curl_cmd)
    if url_match:
        result["url"] = url_match.group(1).rstrip("/")

    # Also try to find URL after -X flag
    if not result["url"]:
        url_match = re.search(r"""['"]?(https?://[^\s'"]+)['"]?""", curl_cmd)
        if url_match:
            result["url"] = url_match.group(1)

    # Extract method
    method_match = re.search(r"-X\s+(\w+)", curl_cmd)
    if method_match:
        result["method"] = method_match.group(1).upper()

    # Extract headers
    header_pattern = re.compile(r"""-H\s+['"]([^'"]+)['"]""")
    for match in header_pattern.finditer(curl_cmd):
        header = match.group(1)
        if ":" in header:
            key, value = header.split(":", 1)
            result["headers"][key.strip()] = value.strip()

    # Extract bearer token
    auth_match = re.search(
        r"""(?:Authorization['"]?\s*[:=]\s*['"]?)?\s*Bearer\s+([^\s'"]+)""",
        curl_cmd,
        re.IGNORECASE,
    )
    if auth_match:
        result["auth_type"] = "bearer"
        result["auth_value"] = auth_match.group(1)

    # Extract API key from headers
    if not result["auth_type"]:
        for key, value in result["headers"].items():
            if "api" in key.lower() and "key" in key.lower():
                result["auth_type"] = "api_key"
                result["auth_value"] = value
                result["auth_header_name"] = key
                break

    # Extract body from -d or --data
    body_match = re.search(r"""(?:-d|--data)\s+['"](.+?)['"]\s*(?:-[H]|$)""", curl_cmd)
    if body_match:
        import json
        try:
            result["body"] = json.loads(body_match.group(1))
        except Exception:
            result["body"] = body_match.group(1)
        if result["method"] == "GET":
            result["method"] = "POST"

    return result


class ParseCurl(Tool):
    """Parse a curl command and extract request details."""

    @property
    def name(self) -> str:
        return "parse_curl"

    @property
    def description(self) -> str:
        return (
            "Parse a curl command and extract the URL, method, headers, and auth. "
            "Use this when the user pastes a curl command. Returns structured "
            "request details that can be used with send_http_request."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "curl_command": {
                    "type": "string",
                    "description": "The curl command to parse",
                },
            },
            "required": ["curl_command"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        curl_cmd = arguments.get("curl_command", "")
        if not curl_cmd:
            return ToolResult(
                status=ToolStatus.ERROR,
                error="No curl command provided",
            )

        try:
            parsed = parse_curl(curl_cmd)

            if not parsed["url"]:
                return ToolResult(
                    status=ToolStatus.ERROR,
                    error="Could not extract URL from curl command",
                )

            return ToolResult(
                status=ToolStatus.SUCCESS,
                data=parsed,
                metadata={"url": parsed["url"], "method": parsed["method"]},
            )

        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Failed to parse curl command: {e}",
            )


class RunCurl(Tool):
    """Parse curl and send the request automatically."""

    def __init__(self, auth_provider: AuthProvider | None = None) -> None:
        self._auth_provider = auth_provider

    @property
    def name(self) -> str:
        return "run_curl"

    @property
    def description(self) -> str:
        return (
            "Parse a curl command and send the request immediately. "
            "Auto-configures auth from the curl headers. Use this when "
            "the user pastes a curl command to test an API."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "curl_command": {
                    "type": "string",
                    "description": "The curl command to execute",
                },
            },
            "required": ["curl_command"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        import time

        import httpx

        curl_cmd = arguments.get("curl_command", "")
        if not curl_cmd:
            return ToolResult(
                status=ToolStatus.ERROR,
                error="No curl command provided",
            )

        try:
            parsed = parse_curl(curl_cmd)
        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Failed to parse curl: {e}",
            )

        if not parsed["url"]:
            return ToolResult(
                status=ToolStatus.ERROR,
                error="Could not extract URL from curl command",
            )

        url = parsed["url"]
        method = parsed["method"]
        headers = parsed["headers"]

        # Auto-configure auth from curl
        if parsed["auth_type"] and self._auth_provider:
            from querymind.security.models import AuthConfig, AuthType

            # Extract base URL from full URL
            url_parts = url.split("/")
            base_url = "/".join(url_parts[:3]) if len(url_parts) >= 3 else url

            if parsed["auth_type"] == "bearer":
                config = AuthConfig(
                    type=AuthType.BEARER,
                    base_url=base_url,
                    token=parsed["auth_value"],
                )
                self._auth_provider.set_auth(base_url=base_url, config=config)
            elif parsed["auth_type"] == "api_key":
                header_name = parsed.get("auth_header_name", "X-API-Key")
                config = AuthConfig(
                    type=AuthType.API_KEY,
                    base_url=base_url,
                    key_name=header_name,
                    key_value=parsed["auth_value"],
                )
                self._auth_provider.set_auth(base_url=base_url, config=config)

        # Apply auth to headers
        if self._auth_provider:
            headers = self._auth_provider.apply_auth(headers, url)

        try:
            start = time.monotonic()
            async with httpx.AsyncClient(
                timeout=30, follow_redirects=True, verify=False,
            ) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=parsed["body"],
                )
            elapsed_ms = int((time.monotonic() - start) * 1000)

            # Parse response
            try:
                resp_body = response.json()
            except Exception:
                resp_body = response.text[:2000]

            # Check for auth errors
            if response.status_code in (401, 403):
                return ToolResult(
                    status=ToolStatus.AUTH_REQUIRED,
                    error=(
                        f"Authentication failed ({response.status_code}). "
                        "The token from curl may be expired or invalid."
                    ),
                    data={
                        "status_code": response.status_code,
                        "body": resp_body,
                        "url": url,
                        "method": method,
                    },
                )

            data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": resp_body,
                "elapsed_ms": elapsed_ms,
                "success": 200 <= response.status_code < 400,
                "url": url,
                "method": method,
            }

            return ToolResult(
                status=ToolStatus.SUCCESS,
                data=data,
                metadata={"url": url, "method": method, "status": response.status_code},
            )

        except httpx.TimeoutException:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Request timed out: {method} {url}",
            )
        except httpx.RequestError as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Request failed: {method} {url} — {e}",
            )
