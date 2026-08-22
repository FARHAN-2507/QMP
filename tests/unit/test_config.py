"""Tests for QueryMind configuration."""

from querymind.config.settings import Settings


def test_default_settings() -> None:
    s = Settings(
        _env_file=None,
        GROQ_API_KEYS="",
        MONGODB_CONNECTION_STRING="",
    )
    assert s.environment == "development"
    assert s.max_agent_iterations == 20
    assert s.http_timeout_seconds == 30
    assert s.groq_model == "openai/gpt-oss-20b"
    assert s.mongodb_database_name == "QueryMind"


def test_groq_api_key_list_single() -> None:
    s = Settings(_env_file=None, GROQ_API_KEYS="gsk_key1")
    assert s.groq_api_key_list == ["gsk_key1"]


def test_groq_api_key_list_multiple() -> None:
    s = Settings(_env_file=None, GROQ_API_KEYS="gsk_key1,gsk_key2,gsk_key3")
    assert s.groq_api_key_list == ["gsk_key1", "gsk_key2", "gsk_key3"]


def test_groq_api_key_list_empty() -> None:
    s = Settings(_env_file=None, GROQ_API_KEYS="")
    assert s.groq_api_key_list == []


def test_groq_api_key_list_strips_whitespace() -> None:
    s = Settings(_env_file=None, GROQ_API_KEYS=" key1 , key2 , key3 ")
    assert s.groq_api_key_list == ["key1", "key2", "key3"]
