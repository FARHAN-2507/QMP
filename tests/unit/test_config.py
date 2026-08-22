"""Tests for QueryMind configuration."""

from querymind.config.settings import Settings


def test_default_settings() -> None:
    s = Settings(
        _env_file=None,
        GROQ_API_KEY="",
        MONGODB_CONNECTION_STRING="",
    )
    assert s.environment == "development"
    assert s.max_agent_iterations == 20
    assert s.http_timeout_seconds == 30
    assert s.groq_model == "llama-3.1-8b-instant"
    assert s.mongodb_database_name == "QueryMind"
