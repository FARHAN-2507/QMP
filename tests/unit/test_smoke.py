"""Unit tests for smoke testing."""

import pytest

from querymind.testing.smoke import (
    SmokeTestConfig,
    generate_endpoint_tests,
    generate_health_tests,
    generate_openapi_tests,
)


class TestSmokeTestConfig:
    """Tests for SmokeTestConfig."""

    def test_config_defaults(self):
        config = SmokeTestConfig(base_url="http://localhost:3000")
        assert config.base_url == "http://localhost:3000"
        assert config.timeout_ms == 5000
        assert config.timeout_s == 5.0
        assert config.include_write_tests is False
        assert config.auth_provider is None

    def test_config_custom(self):
        config = SmokeTestConfig(
            base_url="https://api.example.com",
            timeout_ms=3000,
            include_write_tests=True,
        )
        assert config.base_url == "https://api.example.com"
        assert config.timeout_ms == 3000
        assert config.timeout_s == 3.0
        assert config.include_write_tests is True

    def test_config_strips_trailing_slash(self):
        config = SmokeTestConfig(base_url="http://localhost:3000/")
        assert config.base_url == "http://localhost:3000"


class TestGenerateHealthTests:
    """Tests for generate_health_tests."""

    def test_generates_health_tests(self):
        config = SmokeTestConfig(base_url="http://localhost:3000")
        tests = generate_health_tests(config)

        assert len(tests) > 0
        assert all(t.request.method == "GET" for t in tests)
        assert all(t.request.url.startswith("http://localhost:3000") for t in tests)

    def test_includes_common_health_endpoints(self):
        config = SmokeTestConfig(base_url="http://localhost:3000")
        tests = generate_health_tests(config)
        test_names = [t.name for t in tests]

        assert any("/health" in name for name in test_names)
        assert any("/status" in name for name in test_names)

    def test_has_timeout_assertion(self):
        config = SmokeTestConfig(base_url="http://localhost:3000", timeout_ms=3000)
        tests = generate_health_tests(config)

        for test in tests:
            timeout_assertions = [
                a for a in test.assertions
                if a.type.value == "response_time_ms"
            ]
            assert len(timeout_assertions) == 1
            assert timeout_assertions[0].expected == 3000


class TestGenerateEndpointTests:
    """Tests for generate_endpoint_tests."""

    def test_generates_endpoint_tests(self):
        config = SmokeTestConfig(base_url="http://localhost:3000")
        endpoints = [
            {
                "path": "/api/users", "method": "GET",
                "status_code": 200, "content_type": "application/json",
            },
            {
                "path": "/api/posts", "method": "GET",
                "status_code": 200, "content_type": "application/json",
            },
        ]
        tests = generate_endpoint_tests(config, endpoints)

        assert len(tests) == 2
        assert tests[0].name == "GET /api/users"
        assert tests[1].name == "GET /api/posts"

    def test_skips_non_get_by_default(self):
        config = SmokeTestConfig(base_url="http://localhost:3000")
        endpoints = [
            {"path": "/api/users", "method": "GET", "status_code": 200},
            {"path": "/api/users", "method": "POST", "status_code": 201},
            {"path": "/api/users", "method": "DELETE", "status_code": 204},
        ]
        tests = generate_endpoint_tests(config, endpoints)

        assert len(tests) == 1  # Only GET
        assert tests[0].request.method == "GET"

    def test_includes_write_tests_when_enabled(self):
        config = SmokeTestConfig(base_url="http://localhost:3000", include_write_tests=True)
        endpoints = [
            {"path": "/api/users", "method": "GET", "status_code": 200},
            {"path": "/api/users", "method": "POST", "status_code": 201},
        ]
        tests = generate_endpoint_tests(config, endpoints)

        assert len(tests) == 2

    def test_adds_json_assertions(self):
        config = SmokeTestConfig(base_url="http://localhost:3000")
        endpoints = [
            {
                "path": "/api/users", "method": "GET",
                "status_code": 200, "content_type": "application/json",
            },
        ]
        tests = generate_endpoint_tests(config, endpoints)

        assert len(tests) == 1
        # Should have status code, response time, body not empty, and header assertions
        assert len(tests[0].assertions) >= 3


class TestGenerateOpenAPITests:
    """Tests for generate_openapi_tests."""

    def test_generates_from_spec(self):
        config = SmokeTestConfig(base_url="http://localhost:3000")
        spec = {
            "paths": {
                "/api/users": {
                    "get": {
                        "summary": "List users",
                        "responses": {"200": {"description": "Success"}},
                    }
                }
            }
        }
        tests = generate_openapi_tests(config, spec)

        assert len(tests) == 1
        assert tests[0].name == "GET /api/users"
        assert tests[0].description == "List users"

    def test_skips_non_get_by_default(self):
        config = SmokeTestConfig(base_url="http://localhost:3000")
        spec = {
            "paths": {
                "/api/users": {
                    "get": {"responses": {"200": {"description": "Success"}}},
                    "post": {"responses": {"201": {"description": "Created"}}},
                }
            }
        }
        tests = generate_openapi_tests(config, spec)

        assert len(tests) == 1  # Only GET
        assert tests[0].request.method == "GET"

    def test_includes_write_tests_when_enabled(self):
        config = SmokeTestConfig(base_url="http://localhost:3000", include_write_tests=True)
        spec = {
            "paths": {
                "/api/users": {
                    "get": {"responses": {"200": {"description": "Success"}}},
                    "post": {"responses": {"201": {"description": "Created"}}},
                }
            }
        }
        tests = generate_openapi_tests(config, spec)

        assert len(tests) == 2

    def test_uses_spec_response_codes(self):
        config = SmokeTestConfig(base_url="http://localhost:3000")
        spec = {
            "paths": {
                "/api/users": {
                    "get": {
                        "responses": {
                            "200": {"description": "Success"},
                            "401": {"description": "Unauthorized"},
                        }
                    }
                }
            }
        }
        tests = generate_openapi_tests(config, spec)

        assert len(tests) == 1
        # Should have status code range assertion
        status_assertions = [
            a for a in tests[0].assertions
            if a.type.value == "status_code_range"
        ]
        assert len(status_assertions) == 1
        assert status_assertions[0].expected == [200, 200]


class TestSmokeTestTool:
    """Tests for RunSmokeTests tool."""

    @pytest.mark.asyncio
    async def test_tool_schema(self):
        from querymind.tools.smoke import RunSmokeTests

        tool = RunSmokeTests()
        assert tool.name == "run_smoke_tests"
        assert "base_url" in tool.input_schema["properties"]
        assert "base_url" in tool.input_schema["required"]
