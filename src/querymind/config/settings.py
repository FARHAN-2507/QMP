"""QueryMind configuration settings."""

import json
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    environment: str = Field(default="development", alias="QUERYMIND_ENVIRONMENT")
    max_agent_iterations: int = Field(default=50, alias="QUERYMIND_MAX_AGENT_ITERATIONS")
    max_history_messages: int = Field(default=50, alias="QUERYMIND_MAX_HISTORY_MESSAGES")
    http_timeout_seconds: int = Field(default=30, alias="QUERYMIND_HTTP_TIMEOUT_SECONDS")

    groq_api_keys: str = Field(default="", alias="GROQ_API_KEYS")
    groq_model: str = Field(default="openai/gpt-oss-20b", alias="GROQ_MODEL")

    # Ollama settings (local models)
    ollama_model: str = Field(default="qwen2.5:3b", alias="OLLAMA_MODEL")
    ollama_url: str = Field(default="http://localhost:11434", alias="OLLAMA_URL")

    mongodb_connection_string: str = Field(default="", alias="MONGODB_CONNECTION_STRING")
    mongodb_database_name: str = Field(default="QueryMind", alias="MONGODB_DATABASE_NAME")

    data_dir: str = Field(default="~/.querymind", alias="QUERYMIND_DATA_DIR")
    session_ttl_days: int = Field(default=30, alias="QUERYMIND_SESSION_TTL_DAYS")
    report_output_dir: str = Field(default="~/Downloads", alias="QUERYMIND_REPORT_OUTPUT_DIR")
    auth_config_path: str = Field(
        default="~/.querymind/.auth.json", alias="QUERYMIND_AUTH_CONFIG_PATH"
    )

    # Smoke test settings
    smoke_test_timeout_ms: int = Field(default=5000, alias="QUERYMIND_SMOKE_TEST_TIMEOUT_MS")
    smoke_test_include_write: bool = Field(
        default=False, alias="QUERYMIND_SMOKE_TEST_INCLUDE_WRITE"
    )

    def __init__(self, **kwargs: Any) -> None:  # pyright: ignore[reportUnknownParameterType]
        # Track if groq_api_keys was explicitly set before Pydantic processes it
        groq_keys_explicit = "GROQ_API_KEYS" in kwargs
        super().__init__(**kwargs)  # pyright: ignore[reportUnknownArgumentType]
        self._groq_api_keys_explicit = groq_keys_explicit
        self._load_user_config()

    def _load_user_config(self) -> None:
        """Load API keys from user config file if not in env."""
        config_path = Path(self.data_dir).expanduser() / "config.json"
        # Only load from config if groq_api_keys was not explicitly set
        if config_path.exists() and not self._groq_api_keys_explicit:
            try:
                with open(config_path) as f:
                    config = json.load(f)
                if "groq_api_keys" in config and config["groq_api_keys"]:
                    self.groq_api_keys = config["groq_api_keys"]
                if "groq_model" in config:
                    self.groq_model = config["groq_model"]
            except Exception:
                pass

    @property
    def groq_api_key_list(self) -> list[str]:
        """Parse comma-separated API keys into a list."""
        if not self.groq_api_keys:
            return []
        return [k.strip() for k in self.groq_api_keys.split(",") if k.strip()]

    def save_user_config(self) -> None:
        """Save current settings to user config file."""
        config_path = Path(self.data_dir).expanduser() / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config = {
            "groq_api_keys": self.groq_api_keys,
            "groq_model": self.groq_model,
        }
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)


settings = Settings()
