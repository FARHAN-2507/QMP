"""Auth models — types and configurations for API authentication."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AuthType(StrEnum):
    """Supported authentication types."""

    API_KEY = "api_key"
    BEARER = "bearer"
    BASIC = "basic"
    OAUTH2 = "oauth2"


class AuthConfig(BaseModel):
    """Configuration for authenticating to a target API.

    Supports API keys, Bearer tokens, Basic auth, and OAuth 2.0.
    """

    type: AuthType
    base_url: str = ""

    # API Key
    key_name: str = Field(default="X-API-Key", description="Header or query param name")
    key_value: str = Field(default="", description="API key value")
    key_location: str = Field(
        default="header", description="Where to put the key: 'header' or 'query'"
    )

    # Bearer Token
    token: str = Field(default="", description="Bearer token value")

    # Basic Auth
    username: str = Field(default="", description="Basic auth username")
    password: str = Field(default="", description="Basic auth password")

    # OAuth 2.0
    client_id: str = Field(default="", description="OAuth2 client ID")
    client_secret: str = Field(default="", description="OAuth2 client secret")
    token_url: str = Field(default="", description="OAuth2 token endpoint URL")
    access_token: str = Field(default="", description="OAuth2 access token")
    refresh_token: str = Field(default="", description="OAuth2 refresh token")
    scopes: list[str] = Field(default_factory=list, description="OAuth2 scopes")

    def get_auth_headers(self) -> dict[str, str]:
        """Return headers needed for this auth type."""
        if self.type == AuthType.API_KEY:
            return {self.key_name: self.key_value}
        elif self.type == AuthType.BEARER:
            return {"Authorization": f"Bearer {self.token}"}
        elif self.type == AuthType.BASIC:
            import base64
            credentials = f"{self.username}:{self.password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        elif self.type == AuthType.OAUTH2:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}

    def get_auth_query_params(self) -> dict[str, str]:
        """Return query parameters needed for this auth type."""
        if self.type == AuthType.API_KEY and self.key_location == "query":
            return {self.key_name: self.key_value}
        return {}

    def mask_sensitive(self) -> dict[str, Any]:
        """Return a masked version of the config for display."""
        data = self.model_dump()
        if self.type == AuthType.API_KEY:
            data["key_value"] = self._mask(self.key_value)
        elif self.type == AuthType.BEARER:
            data["token"] = self._mask(self.token)
        elif self.type == AuthType.BASIC:
            data["password"] = self._mask(self.password)
        elif self.type == AuthType.OAUTH2:
            data["client_secret"] = self._mask(self.client_secret)
            data["access_token"] = self._mask(self.access_token)
            data["refresh_token"] = self._mask(self.refresh_token)
        return data

    @staticmethod
    def _mask(value: str) -> str:
        """Mask a sensitive value."""
        if not value:
            return ""
        if len(value) <= 8:
            return "***"
        return value[:4] + "***" + value[-4:]
