"""Unit tests for authentication models, storage, and provider."""

import pytest

from querymind.security.models import AuthConfig, AuthType
from querymind.security.provider import AuthProvider
from querymind.security.storage import AuthStorage


class TestAuthType:
    """Tests for AuthType enum."""

    def test_auth_types(self):
        assert AuthType.API_KEY == "api_key"
        assert AuthType.BEARER == "bearer"
        assert AuthType.BASIC == "basic"
        assert AuthType.OAUTH2 == "oauth2"

    def test_auth_type_from_string(self):
        assert AuthType("api_key") == AuthType.API_KEY
        assert AuthType("bearer") == AuthType.BEARER
        assert AuthType("basic") == AuthType.BASIC
        assert AuthType("oauth2") == AuthType.OAUTH2


class TestAuthConfig:
    """Tests for AuthConfig model."""

    def test_api_key_config(self):
        config = AuthConfig(
            type=AuthType.API_KEY,
            key_name="X-API-Key",
            key_value="test-key-123",
            key_location="header",
        )
        assert config.type == AuthType.API_KEY
        assert config.key_name == "X-API-Key"
        assert config.key_value == "test-key-123"

    def test_api_key_query_location(self):
        config = AuthConfig(
            type=AuthType.API_KEY,
            key_name="api_key",
            key_value="test-key",
            key_location="query",
        )
        # API key in query location still returns header (for compatibility)
        # but the main auth is via query params
        params = config.get_auth_query_params()
        assert params == {"api_key": "test-key"}

    def test_bearer_config(self):
        config = AuthConfig(
            type=AuthType.BEARER,
            token="eyJhbGciOiJIUzI1NiJ9.test",
        )
        headers = config.get_auth_headers()
        assert headers == {"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.test"}

    def test_basic_auth_config(self):
        config = AuthConfig(
            type=AuthType.BASIC,
            username="user",
            password="pass",
        )
        headers = config.get_auth_headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")

        import base64
        encoded = headers["Authorization"].split(" ", 1)[1]
        decoded = base64.b64decode(encoded).decode()
        assert decoded == "user:pass"

    def test_oauth2_config(self):
        config = AuthConfig(
            type=AuthType.OAUTH2,
            client_id="my-client",
            client_secret="my-secret",
            token_url="https://auth.example.com/token",
            access_token="eyJhbGciOiJIUzI1NiJ9.oauth",
            scopes=["read", "write"],
        )
        headers = config.get_auth_headers()
        assert headers == {"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.oauth"}

    def test_mask_sensitive_api_key(self):
        config = AuthConfig(
            type=AuthType.API_KEY,
            key_value="1234567890",
        )
        masked = config.mask_sensitive()
        # Mask shows first 4 + *** + last 4
        assert "***" in masked["key_value"]
        assert masked["key_value"].startswith("1234")
        assert masked["key_value"].endswith("7890")

    def test_mask_sensitive_bearer(self):
        config = AuthConfig(
            type=AuthType.BEARER,
            token="eyJhbGciOiJIUzI1NiJ9.test",
        )
        masked = config.mask_sensitive()
        assert "***" in masked["token"]

    def test_mask_sensitive_basic(self):
        config = AuthConfig(
            type=AuthType.BASIC,
            password="secret123",
        )
        masked = config.mask_sensitive()
        # Mask shows first 4 + *** + last 4
        assert "***" in masked["password"]
        assert masked["password"].startswith("secr")
        assert masked["password"].endswith("t123")

    def test_mask_short_value(self):
        config = AuthConfig(
            type=AuthType.API_KEY,
            key_value="abc",
        )
        masked = config.mask_sensitive()
        assert masked["key_value"] == "***"

    def test_mask_empty_value(self):
        config = AuthConfig(
            type=AuthType.API_KEY,
            key_value="",
        )
        masked = config.mask_sensitive()
        assert masked["key_value"] == ""


class TestAuthStorage:
    """Tests for AuthStorage."""

    def test_save_and_load(self, tmp_path):
        storage = AuthStorage(tmp_path)
        config = AuthConfig(
            type=AuthType.BEARER,
            token="test-token",
            base_url="https://api.example.com",
        )

        storage.save("https://api.example.com", config)
        loaded = storage.load("https://api.example.com")

        assert loaded is not None
        assert loaded.type == AuthType.BEARER
        assert loaded.token == "test-token"

    def test_load_nonexistent(self, tmp_path):
        storage = AuthStorage(tmp_path)
        loaded = storage.load("https://nonexistent.com")
        assert loaded is None

    def test_delete(self, tmp_path):
        storage = AuthStorage(tmp_path)
        config = AuthConfig(type=AuthType.BEARER, token="test")
        storage.save("https://api.example.com", config)

        deleted = storage.delete("https://api.example.com")
        assert deleted is True

        loaded = storage.load("https://api.example.com")
        assert loaded is None

    def test_delete_nonexistent(self, tmp_path):
        storage = AuthStorage(tmp_path)
        deleted = storage.delete("https://nonexistent.com")
        assert deleted is False

    def test_list_configs(self, tmp_path):
        storage = AuthStorage(tmp_path)
        config1 = AuthConfig(type=AuthType.BEARER, token="token1")
        config2 = AuthConfig(type=AuthType.API_KEY, key_value="key1")

        storage.save("https://api1.example.com", config1)
        storage.save("https://api2.example.com", config2)

        configs = storage.list_configs()
        assert len(configs) == 2

    def test_clear(self, tmp_path):
        storage = AuthStorage(tmp_path)
        config = AuthConfig(type=AuthType.BEARER, token="test")
        storage.save("https://api.example.com", config)

        count = storage.clear()
        assert count == 1

        configs = storage.list_configs()
        assert len(configs) == 0

    def test_normalize_url(self, tmp_path):
        storage = AuthStorage(tmp_path)
        normalized = storage.normalize_url("api.example.com")
        assert normalized == "https://api.example.com"

        normalized = storage.normalize_url("https://api.example.com/")
        assert normalized == "https://api.example.com"


class TestAuthProvider:
    """Tests for AuthProvider."""

    def test_set_and_get_auth(self, tmp_path):
        provider = AuthProvider(tmp_path)
        config = AuthConfig(type=AuthType.BEARER, token="test-token")
        provider.set_auth("https://api.example.com", config)

        retrieved = provider.get_auth("https://api.example.com/users")
        assert retrieved is not None
        assert retrieved.type == AuthType.BEARER

    def test_get_auth_no_match(self, tmp_path):
        provider = AuthProvider(tmp_path)
        retrieved = provider.get_auth("https://nonexistent.com")
        assert retrieved is None

    def test_apply_auth_headers(self, tmp_path):
        provider = AuthProvider(tmp_path)
        config = AuthConfig(type=AuthType.BEARER, token="test-token")
        provider.set_auth("https://api.example.com", config)

        headers = {"Content-Type": "application/json"}
        merged = provider.apply_auth(headers, "https://api.example.com/users")

        assert merged["Content-Type"] == "application/json"
        assert merged["Authorization"] == "Bearer test-token"

    def test_apply_auth_no_config(self, tmp_path):
        provider = AuthProvider(tmp_path)
        headers = {"Content-Type": "application/json"}
        merged = provider.apply_auth(headers, "https://nonexistent.com")

        assert merged == {"Content-Type": "application/json"}

    def test_has_auth(self, tmp_path):
        provider = AuthProvider(tmp_path)
        assert provider.has_auth("https://api.example.com") is False

        config = AuthConfig(type=AuthType.BEARER, token="test")
        provider.set_auth("https://api.example.com", config)

        assert provider.has_auth("https://api.example.com") is True

    def test_remove_auth(self, tmp_path):
        provider = AuthProvider(tmp_path)
        config = AuthConfig(type=AuthType.BEARER, token="test")
        provider.set_auth("https://api.example.com", config)

        deleted = provider.remove_auth("https://api.example.com")
        assert deleted is True
        assert provider.has_auth("https://api.example.com") is False

    def test_clear_all(self, tmp_path):
        provider = AuthProvider(tmp_path)
        config1 = AuthConfig(type=AuthType.BEARER, token="token1")
        config2 = AuthConfig(type=AuthType.API_KEY, key_value="key1")

        provider.set_auth("https://api1.example.com", config1)
        provider.set_auth("https://api2.example.com", config2)

        count = provider.clear_all()
        assert count == 2
        assert provider.list_auth() == []

    def test_get_auth_summary(self, tmp_path):
        provider = AuthProvider(tmp_path)
        summary = provider.get_auth_summary()
        assert "No authentication configured" in summary

        config = AuthConfig(type=AuthType.BEARER, token="test")
        provider.set_auth("https://api.example.com", config)

        summary = provider.get_auth_summary()
        assert "https://api.example.com" in summary
        assert "bearer" in summary


class TestAuthTools:
    """Tests for auth tools."""

    @pytest.mark.asyncio
    async def test_configure_auth_tool(self, tmp_path):
        from querymind.tools.auth import ConfigureAuth

        provider = AuthProvider(tmp_path)
        tool = ConfigureAuth(auth_provider=provider)

        result = await tool.execute({
            "base_url": "https://api.example.com",
            "auth_type": "bearer",
            "token": "test-token",
        })

        assert result.is_success
        assert "configured" in result.data["message"].lower()

        # Verify it was saved
        config = provider.get_auth("https://api.example.com")
        assert config is not None
        assert config.token == "test-token"

    @pytest.mark.asyncio
    async def test_list_auth_tool(self, tmp_path):
        from querymind.tools.auth import ListAuth

        provider = AuthProvider(tmp_path)
        tool = ListAuth(auth_provider=provider)

        result = await tool.execute({})
        assert result.is_success
        assert "No authentication" in result.data["message"]

        # Add a config
        config = AuthConfig(type=AuthType.BEARER, token="test")
        provider.set_auth("https://api.example.com", config)

        result = await tool.execute({})
        assert result.is_success
        assert len(result.data["configs"]) == 1

    @pytest.mark.asyncio
    async def test_clear_auth_tool(self, tmp_path):
        from querymind.tools.auth import ClearAuth

        provider = AuthProvider(tmp_path)
        config = AuthConfig(type=AuthType.BEARER, token="test")
        provider.set_auth("https://api.example.com", config)

        tool = ClearAuth(auth_provider=provider)
        result = await tool.execute({"base_url": "https://api.example.com"})

        assert result.is_success
        assert "cleared" in result.data["message"].lower()
        assert provider.has_auth("https://api.example.com") is False
