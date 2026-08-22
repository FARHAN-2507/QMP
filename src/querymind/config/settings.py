"""QueryMind configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    environment: str = Field(default="development", alias="QUERYMIND_ENVIRONMENT")
    max_agent_iterations: int = Field(default=20, alias="QUERYMIND_MAX_AGENT_ITERATIONS")
    max_history_messages: int = Field(default=50, alias="QUERYMIND_MAX_HISTORY_MESSAGES")
    http_timeout_seconds: int = Field(default=30, alias="QUERYMIND_HTTP_TIMEOUT_SECONDS")

    groq_api_keys: str = Field(default="", alias="GROQ_API_KEYS")
    groq_model: str = Field(default="openai/gpt-oss-20b", alias="GROQ_MODEL")

    mongodb_connection_string: str = Field(default="", alias="MONGODB_CONNECTION_STRING")
    mongodb_database_name: str = Field(default="QueryMind", alias="MONGODB_DATABASE_NAME")

    data_dir: str = Field(default="~/.querymind", alias="QUERYMIND_DATA_DIR")
    session_ttl_days: int = Field(default=30, alias="QUERYMIND_SESSION_TTL_DAYS")
    report_output_dir: str = Field(default="~/Downloads", alias="QUERYMIND_REPORT_OUTPUT_DIR")
    auth_config_path: str = Field(
        default="~/.querymind/.auth.json", alias="QUERYMIND_AUTH_CONFIG_PATH"
    )

    @property
    def groq_api_key_list(self) -> list[str]:
        """Parse comma-separated API keys into a list."""
        if not self.groq_api_keys:
            return []
        return [k.strip() for k in self.groq_api_keys.split(",") if k.strip()]


settings = Settings()
