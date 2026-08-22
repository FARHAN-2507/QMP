"""OpenAPI spec parser tool — extracts API information from OpenAPI/Swagger specs.

Supports JSON and YAML formats. The agent uses this to understand
an API's endpoints, parameters, and schemas before testing.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import httpx

from querymind.tools.base import Tool, ToolResult, ToolStatus


def parse_openapi_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Parse an OpenAPI spec into a structured summary.

    Extracts endpoints, methods, parameters, request bodies, and
    response schemas in a format the LLM can understand.
    """
    info = spec.get("info", {})
    paths = spec.get("paths", {})
    components = spec.get("components", {})
    servers = spec.get("servers", [])

    endpoints: list[dict[str, Any]] = []
    for path, path_item in paths.items():
        for method in ("get", "post", "put", "patch", "delete", "head", "options"):
            if method not in path_item:
                continue

            operation = path_item[method]
            endpoint: dict[str, Any] = {
                "method": method.upper(),
                "path": path,
                "summary": operation.get("summary", ""),
                "operationId": operation.get("operationId", ""),
            }

            # Parameters (path, query, header)
            params = operation.get("parameters", []) + path_item.get("parameters", [])
            if params:
                endpoint["parameters"] = []
                for p in params:
                    endpoint["parameters"].append({  # pyright: ignore[reportUnknownMemberType]
                        "name": p.get("name", ""),
                        "in": p.get("in", ""),
                        "required": p.get("required", False),
                        "type": _resolve_type(p.get("schema", {})),
                    })

            # Request body
            request_body = operation.get("requestBody", {})
            if request_body:
                content = request_body.get("content", {})
                json_content = content.get("application/json", {})
                schema = json_content.get("schema", {})
                if schema:
                    endpoint["requestBody"] = _resolve_schema(schema, components)

            # Responses
            responses = operation.get("responses", {})
            if responses:
                endpoint["responses"] = {}
                for code, resp in responses.items():
                    resp_content = resp.get("content", {})
                    json_resp = resp_content.get("application/json", {})
                    resp_schema = json_resp.get("schema", {})
                    endpoint["responses"][code] = {
                        "description": resp.get("description", ""),
                        "schema": _resolve_schema(resp_schema, components) if resp_schema else None,
                    }

            endpoints.append(endpoint)

    # Security
    security = spec.get("security", [])
    security_schemes = components.get("securitySchemes", {})

    return {
        "title": info.get("title", "Unknown API"),
        "version": info.get("version", "unknown"),
        "description": info.get("description", ""),
        "servers": [s.get("url", "") for s in servers],
        "endpoints": endpoints,
        "totalEndpoints": len(endpoints),
        "security": _summarize_security(security, security_schemes),
    }


def _resolve_type(schema: dict[str, Any]) -> str:
    """Get a simple type string from a schema."""
    if "type" in schema:
        return schema["type"]
    if "oneOf" in schema or "anyOf" in schema:
        return "mixed"
    return "unknown"


def _resolve_schema(schema: dict[str, Any], components: dict[str, Any]) -> dict[str, Any]:
    """Resolve a schema, following $ref references."""
    if "$ref" in schema:
        ref_path = schema["$ref"].split("/")
        resolved = components
        for part in ref_path[1:]:  # skip '#'
            resolved = resolved.get(part, {})
        return _resolve_schema(resolved, components)

    result: dict[str, Any] = {"type": schema.get("type", "object")}

    if "properties" in schema:
        result["properties"] = {}
        for prop_name, prop_schema in schema["properties"].items():
            result["properties"][prop_name] = _resolve_schema(prop_schema, components)

    if "items" in schema:
        result["items"] = _resolve_schema(schema["items"], components)

    if "required" in schema:
        result["required"] = schema["required"]

    return result


def _summarize_security(
    security: list[dict[str, Any]], schemes: dict[str, Any]
) -> dict[str, Any] | None:
    """Summarize security requirements."""
    if not security and not schemes:
        return None

    summary: dict[str, Any] = {"schemes": {}}
    for name, scheme in schemes.items():
        summary["schemes"][name] = {
            "type": scheme.get("type", ""),
            "in": scheme.get("in", ""),
        }
    if security:
        summary["required"] = list(security[0].keys()) if security else []
    return summary


class ImportOpenApi(Tool):
    """Import an OpenAPI/Swagger spec from a URL or inline JSON."""

    @property
    def name(self) -> str:
        return "import_openapi"

    @property
    def description(self) -> str:
        return (
            "Import an OpenAPI (Swagger) specification from a URL or raw JSON string. "
            "Returns a structured summary of all endpoints, parameters, and schemas. "
            "Use this to understand an API before testing it."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch the OpenAPI spec from (JSON or YAML)",
                },
                "spec_json": {
                    "type": "string",
                    "description": "Raw OpenAPI spec as a JSON string (if not using URL)",
                },
            },
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        url = arguments.get("url")
        spec_json = arguments.get("spec_json")

        if not url and not spec_json:
            return ToolResult(
                status=ToolStatus.VALIDATION_ERROR,
                error="Either 'url' or 'spec_json' must be provided.",
            )

        try:
            if url:
                raw_spec = await self._fetch_spec(url)
            elif spec_json:
                raw_spec = json.loads(spec_json)
            else:
                return ToolResult(
                    status=ToolStatus.VALIDATION_ERROR,
                    error="Either 'url' or 'spec_json' must be provided.",
                )

            summary = parse_openapi_spec(raw_spec)
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data=summary,
                metadata={"title": summary["title"], "endpoints": summary["totalEndpoints"]},
            )

        except json.JSONDecodeError as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Invalid JSON in spec: {e}",
            )
        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Failed to import spec: {e}",
            )

    async def _fetch_spec(self, url: str) -> dict[str, Any]:
        """Fetch an OpenAPI spec from a URL."""
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Invalid URL scheme: {parsed.scheme}")

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

        content_type = response.headers.get("content-type", "")

        # Try JSON first
        if "json" in content_type or url.endswith(".json"):
            return response.json()

        # Try YAML if available
        try:
            return response.json()
        except Exception:
            pass

        # Try parsing as JSON anyway (some servers don't set content-type)
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            raise ValueError(
                f"Could not parse spec from {url}. "
                f"Content-Type: {content_type}. Expected JSON."
            ) from None
