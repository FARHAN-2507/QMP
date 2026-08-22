"""Auth storage — file-based persistence for auth configurations."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from querymind.security.models import AuthConfig

logger = logging.getLogger(__name__)


class AuthStorage:
    """File-based storage for auth configurations.

    Stores auth configs in ~/.querymind/.auth.json keyed by base URL.
    """

    def __init__(self, data_dir: str | Path) -> None:
        self._data_dir = Path(data_dir).expanduser()
        self._auth_file = self._data_dir / ".auth.json"
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Create the data directory if it doesn't exist."""
        self._data_dir.mkdir(parents=True, exist_ok=True)

    def _load_all(self) -> dict[str, Any]:
        """Load all auth configs from disk."""
        if not self._auth_file.exists():
            return {}
        try:
            with open(self._auth_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load auth file: %s", e)
            return {}

    def _save_all(self, data: dict[str, Any]) -> None:
        """Save all auth configs to disk."""
        try:
            with open(self._auth_file, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error("Failed to save auth file: %s", e)

    def save(self, base_url: str, config: AuthConfig) -> None:
        """Save an auth config for a base URL."""
        data = self._load_all()
        normalized = self.normalize_url(base_url)
        config.base_url = normalized
        data[normalized] = config.model_dump()
        self._save_all(data)
        logger.info("Saved auth config for %s", normalized)

    def load(self, base_url: str) -> AuthConfig | None:
        """Load auth config for a base URL."""
        data = self._load_all()
        normalized = self.normalize_url(base_url)
        if normalized not in data:
            return None
        try:
            return AuthConfig(**data[normalized])
        except Exception as e:
            logger.warning("Failed to load auth for %s: %s", normalized, e)
            return None

    def delete(self, base_url: str) -> bool:
        """Delete auth config for a base URL. Returns True if deleted."""
        data = self._load_all()
        normalized = self.normalize_url(base_url)
        if normalized in data:
            del data[normalized]
            self._save_all(data)
            logger.info("Deleted auth config for %s", normalized)
            return True
        return False

    def list_configs(self) -> list[dict[str, Any]]:
        """List all saved auth configs (with sensitive data masked)."""
        data = self._load_all()
        result: list[dict[str, Any]] = []
        for url, config_data in data.items():
            try:
                config = AuthConfig(**config_data)
                masked = config.mask_sensitive()
                masked["base_url"] = url
                result.append(masked)
            except Exception:
                continue
        return result

    def clear(self) -> int:
        """Clear all auth configs. Returns number of configs deleted."""
        count = len(self._load_all())
        self._save_all({})
        return count

    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalize URL for consistent storage keys."""
        normalized = url.rstrip("/")
        # Ensure scheme
        if not normalized.startswith(("http://", "https://")):
            normalized = "https://" + normalized
        return normalized
