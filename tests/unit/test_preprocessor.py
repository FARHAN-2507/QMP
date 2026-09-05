"""Tests for preprocessor — curl and PowerShell parsing."""

import pytest

from querymind.agent.preprocessor import (
    detect_request_type,
    parse_curl,
    parse_powershell,
)


class TestDetectRequestType:
    """Test request type detection."""

    def test_curl_detection(self) -> None:
        result = detect_request_type('curl https://api.com/data')
        assert result["type"] == "curl"

    def test_powershell_detection(self) -> None:
        cmd = 'Invoke-WebRequest -Uri "https://api.com/data"'
        result = detect_request_type(cmd)
        assert result["type"] == "powershell"

    def test_powershell_restmethod_detection(self) -> None:
        cmd = 'Invoke-RestMethod -Uri "https://api.com/data"'
        result = detect_request_type(cmd)
        assert result["type"] == "powershell"

    def test_simple_url_detection(self) -> None:
        result = detect_request_type("https://api.com/data")
        assert result["type"] == "simple_url"
        assert result["details"]["url"] == "https://api.com/data"

    def test_other_detection(self) -> None:
        result = detect_request_type("test all endpoints")
        assert result["type"] == "other"


class TestParseCurl:
    """Test curl command parsing."""

    def test_simple_get(self) -> None:
        result = parse_curl("curl https://api.com/data")
        assert result["url"] == "https://api.com/data"
        assert result["method"] == "GET"

    def test_with_bearer_auth(self) -> None:
        cmd = 'curl -H "Authorization: Bearer tok123" https://api.com/data'
        result = parse_curl(cmd)
        assert result["url"] == "https://api.com/data"
        assert result["auth_type"] == "bearer"
        assert result["auth_value"] == "tok123"

    def test_with_method(self) -> None:
        cmd = 'curl -X POST https://api.com/data'
        result = parse_curl(cmd)
        assert result["method"] == "POST"

    def test_with_multiple_headers(self) -> None:
        cmd = '''curl -H "Authorization: Bearer tok123" -H "Content-Type: application/json" https://api.com/data'''
        result = parse_curl(cmd)
        assert "Authorization" in result["headers"]
        assert "Content-Type" in result["headers"]


class TestParsePowerShell:
    """Test PowerShell command parsing."""

    def test_simple_get(self) -> None:
        cmd = 'Invoke-WebRequest -Uri "https://api.com/data"'
        result = parse_powershell(cmd)
        assert result["url"] == "https://api.com/data"
        assert result["method"] == "GET"

    def test_with_bearer_auth(self) -> None:
        cmd = '''Invoke-WebRequest -Uri "https://api.com/data" -Headers @{
"Authorization" = "Bearer eyJhbGciOiJIUzI1NiJ9.test"
}'''
        result = parse_powershell(cmd)
        assert result["url"] == "https://api.com/data"
        assert result["auth_type"] == "bearer"
        assert result["auth_value"] == "eyJhbGciOiJIUzI1NiJ9.test"

    def test_with_multiple_headers(self) -> None:
        cmd = '''Invoke-WebRequest -Uri "https://api.com/data" -Headers @{
"Authorization" = "Bearer token123"
"Accept" = "application/json"
"Content-Type" = "application/json"
}'''
        result = parse_powershell(cmd)
        assert result["url"] == "https://api.com/data"
        assert result["headers"]["Authorization"] == "Bearer token123"
        assert result["headers"]["Accept"] == "application/json"
        assert result["headers"]["Content-Type"] == "application/json"

    def test_with_method_post(self) -> None:
        cmd = '''Invoke-WebRequest -Uri "https://api.com/data" -Method Post -Body '{"key": "value"}' '''
        result = parse_powershell(cmd)
        assert result["method"] == "POST"
        assert result["body"] == {"key": "value"}

    def test_full_example(self) -> None:
        cmd = '''Invoke-WebRequest -UseBasicParsing -Uri "https://devapi.taiservices.info/management/api/AllAnalystList" -Headers @{
"Accept" = "application/json, text/plain, */*"
"Authorization" = "Bearer eyJhbGciOiJIUzI1NiJ9.token"
"LoginUserId" = "156"
}'''
        result = parse_powershell(cmd)
        assert result["url"] == "https://devapi.taiservices.info/management/api/AllAnalystList"
        assert result["auth_type"] == "bearer"
        assert result["auth_value"] == "eyJhbGciOiJIUzI1NiJ9.token"
        assert result["headers"]["LoginUserId"] == "156"
