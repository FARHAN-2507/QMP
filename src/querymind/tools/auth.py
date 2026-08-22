"""Auth tool — lets the agent configure authentication for target APIs."""

from __future__ import annotations

from typing import Any

from querymind.security.models import AuthConfig, AuthType
from querymind.security.provider import AuthProvider
from querymind.tools.base import Tool, ToolResult, ToolStatus


class ConfigureAuth(Tool):
    """Configure authentication for a target API."""

    def __init__(self, auth_provider: AuthProvider) -> None:
        self._auth_provider = auth_provider

    @property
    def name(self) -> str:
        return "configure_auth"

    @property
    def description(self) -> str:
        return (
            "Configure authentication for a target API. Supports API keys, "
            "Bearer tokens, Basic auth, and OAuth 2.0. Once configured, "
            "auth headers are automatically added to all requests to that API."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "base_url": {
                    "type": "string",
                    "description": "Base URL of the API to configure auth for",
                },
                "auth_type": {
                    "type": "string",
                    "enum": ["api_key", "bearer", "basic", "oauth2"],
                    "description": "Type of authentication",
                },
                "key_name": {
                    "type": "string",
                    "description": "Header/query param name for API key (default: X-API-Key)",
                },
                "key_value": {
                    "type": "string",
                    "description": "API key value",
                },
                "key_location": {
                    "type": "string",
                    "enum": ["header", "query"],
                    "description": "Where to put API key (default: header)",
                },
                "token": {
                    "type": "string",
                    "description": "Bearer token value",
                },
                "username": {
                    "type": "string",
                    "description": "Basic auth username",
                },
                "password": {
                    "type": "string",
                    "description": "Basic auth password",
                },
                "client_id": {
                    "type": "string",
                    "description": "OAuth2 client ID",
                },
                "client_secret": {
                    "type": "string",
                    "description": "OAuth2 client secret",
                },
                "token_url": {
                    "type": "string",
                    "description": "OAuth2 token endpoint URL",
                },
                "access_token": {
                    "type": "string",
                    "description": "OAuth2 access token",
                },
                "scopes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "OAuth2 scopes",
                },
            },
            "required": ["base_url", "auth_type"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        try:
            base_url = arguments["base_url"]
            auth_type_str = arguments["auth_type"]
            auth_type = AuthType(auth_type_str)

            config = AuthConfig(type=auth_type, base_url=base_url)

            if auth_type == AuthType.API_KEY:
                config.key_name = arguments.get("key_name", "X-API-Key")
                config.key_value = arguments.get("key_value", "")
                config.key_location = arguments.get("key_location", "header")

            elif auth_type == AuthType.BEARER:
                config.token = arguments.get("token", "")

            elif auth_type == AuthType.BASIC:
                config.username = arguments.get("username", "")
                config.password = arguments.get("password", "")

            elif auth_type == AuthType.OAUTH2:
                config.client_id = arguments.get("client_id", "")
                config.client_secret = arguments.get("client_secret", "")
                config.token_url = arguments.get("token_url", "")
                config.access_token = arguments.get("access_token", "")
                config.scopes = arguments.get("scopes", [])

            self._auth_provider.set_auth(base_url, config)

            masked = config.mask_sensitive()
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={
                    "message": f"Auth configured for {base_url}",
                    "auth_type": auth_type_str,
                    "config": masked,
                },
                metadata={"base_url": base_url, "auth_type": auth_type_str},
            )

        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Failed to configure auth: {e}",
            )


class ListAuth(Tool):
    """List all configured authentication for target APIs."""

    def __init__(self, auth_provider: AuthProvider) -> None:
        self._auth_provider = auth_provider

    @property
    def name(self) -> str:
        return "list_auth"

    @property
    def description(self) -> str:
        return (
            "List all configured authentication for target APIs. "
            "Shows which APIs have auth configured and the auth type."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        configs = self._auth_provider.list_auth()

        if not configs:
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={"message": "No authentication configured."},
            )

        return ToolResult(
            status=ToolStatus.SUCCESS,
            data={
                "message": f"{len(configs)} API(s) have auth configured",
                "configs": configs,
            },
        )


class ClearAuth(Tool):
    """Remove authentication for a target API."""

    def __init__(self, auth_provider: AuthProvider) -> None:
        self._auth_provider = auth_provider

    @property
    def name(self) -> str:
        return "clear_auth"

    @property
    def description(self) -> str:
        return (
            "Remove authentication configuration for a target API. "
            "After clearing, requests to that API will no longer have auth headers."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "base_url": {
                    "type": "string",
                    "description": "Base URL of the API to clear auth for",
                },
            },
            "required": ["base_url"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        base_url = arguments["base_url"]
        deleted = self._auth_provider.remove_auth(base_url)

        if deleted:
            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={"message": f"Auth cleared for {base_url}"},
            )
        return ToolResult(
            status=ToolStatus.SUCCESS,
            data={"message": f"No auth found for {base_url}"},
        )
