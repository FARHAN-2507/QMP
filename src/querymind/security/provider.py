"""Auth provider — injects authentication headers into HTTP requests."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from querymind.security.models import AuthConfig
from querymind.security.storage import AuthStorage

logger = logging.getLogger(__name__)


class AuthProvider:
    """Centralized authentication provider.

    Manages auth configurations for different APIs and injects
    auth headers into HTTP requests automatically.
    """

    def __init__(self, data_dir: str | Path) -> None:
        self._storage = AuthStorage(data_dir)
        self._configs: dict[str, AuthConfig] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Load all configs from storage."""
        configs = self._storage.list_configs()
        for config_data in configs:
            url = config_data.get("base_url", "")
            if url:
                try:
                    self._configs[url] = AuthConfig(**config_data)
                except Exception:
                    continue

    def set_auth(self, base_url: str, config: AuthConfig) -> None:
        """Set auth config for a base URL."""
        normalized = self._storage.normalize_url(base_url)
        config.base_url = normalized
        self._configs[normalized] = config
        self._storage.save(base_url, config)
        logger.info("Auth configured for %s (%s)", normalized, config.type)

    def get_auth(self, url: str) -> AuthConfig | None:
        """Get auth config for a URL.

        Tries exact match first, then tries to match by base URL.
        """
        # Try exact match
        normalized = self._storage.normalize_url(url)
        if normalized in self._configs:
            return self._configs[normalized]

        # Try base URL match
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base in self._configs:
            return self._configs[base]

        # Try with trailing slash variations
        for stored_url in self._configs:
            if url.startswith(stored_url) or stored_url.startswith(base):
                return self._configs[stored_url]

        return None

    def apply_auth(self, headers: dict[str, str], url: str) -> dict[str, str]:
        """Apply auth headers to a request.

        Merges auth headers into the provided headers dict.
        Returns the merged headers.
        """
        config = self.get_auth(url)
        if config is None:
            return headers

        merged = dict(headers)
        auth_headers = config.get_auth_headers()
        merged.update(auth_headers)

        logger.debug("Applied %s auth to %s", config.type, url)
        return merged

    def apply_query_params(self, params: dict[str, str], url: str) -> dict[str, str]:
        """Apply auth query parameters to a request."""
        config = self.get_auth(url)
        if config is None:
            return params

        merged = dict(params)
        auth_params = config.get_auth_query_params()
        merged.update(auth_params)
        return merged

    def remove_auth(self, base_url: str) -> bool:
        """Remove auth config for a base URL."""
        normalized = self._storage.normalize_url(base_url)
        if normalized in self._configs:
            del self._configs[normalized]
        return self._storage.delete(base_url)

    def list_auth(self) -> list[dict[str, Any]]:
        """List all configured auth (with masked secrets)."""
        return self._storage.list_configs()

    def clear_all(self) -> int:
        """Clear all auth configs."""
        self._configs.clear()
        return self._storage.clear()

    def has_auth(self, url: str) -> bool:
        """Check if auth is configured for a URL."""
        return self.get_auth(url) is not None

    def get_auth_summary(self) -> str:
        """Return a summary of configured auth for the system prompt."""
        configs = self.list_auth()
        if not configs:
            return "No authentication configured."

        lines = ["Configured authentication:"]
        for config in configs:
            url = config.get("base_url", "unknown")
            auth_type = config.get("type", "unknown")
            lines.append(f"- {url}: {auth_type}")

        return "\n".join(lines)
