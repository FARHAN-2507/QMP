"""QueryMind configuration settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = {"env_prefix": "QUERYMIND_", "env_file": ".env", "env_file_encoding": "utf-8"}

    environment: str = "development"
    max_agent_iterations: int = 20
    http_timeout_seconds: int = 30

    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"

    mongodb_connection_string: str = ""
    mongodb_database_name: str = "QueryMind"


settings = Settings()
