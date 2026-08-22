"""QueryMind configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    environment: str = Field(default="development", alias="QUERYMIND_ENVIRONMENT")
    max_agent_iterations: int = Field(default=20, alias="QUERYMIND_MAX_AGENT_ITERATIONS")
    http_timeout_seconds: int = Field(default=30, alias="QUERYMIND_HTTP_TIMEOUT_SECONDS")

    groq_api_keys: str = Field(default="", alias="GROQ_API_KEYS")
    groq_model: str = Field(default="openai/gpt-oss-20b", alias="GROQ_MODEL")

    mongodb_connection_string: str = Field(default="", alias="MONGODB_CONNECTION_STRING")
    mongodb_database_name: str = Field(default="QueryMind", alias="MONGODB_DATABASE_NAME")

    @property
    def groq_api_key_list(self) -> list[str]:
        """Parse comma-separated API keys into a list."""
        if not self.groq_api_keys:
            return []
        return [k.strip() for k in self.groq_api_keys.split(",") if k.strip()]


settings = Settings()
