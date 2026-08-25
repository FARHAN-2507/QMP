"""Tests for smoke cURL parser."""

from __future__ import annotations

from querymind.smoke.curl_parser import parse_curl


def test_parse_get_simple() -> None:
    req = parse_curl("curl https://example.com/api/health")
    assert req.method == "GET"
    assert req.url == "https://example.com/api/health"
    assert req.is_valid


def test_parse_post_json_multiline() -> None:
    curl = r"""curl --location 'https://example.com/api/users' \
--header 'Authorization: Bearer TOKEN123' \
--header 'Content-Type: application/json' \
--data '{
  "name": "John"
}'"""
    req = parse_curl(curl)
    assert req.method == "POST"
    assert req.url == "https://example.com/api/users"
    assert req.headers["Authorization"] == "Bearer TOKEN123"
    assert "John" in (req.body or "")
    assert req.content_type and "json" in req.content_type.lower()


def test_parse_put_patch_delete() -> None:
    assert parse_curl("curl -X PUT https://example.com/a").method == "PUT"
    assert parse_curl("curl -X PATCH https://example.com/a").method == "PATCH"
    assert parse_curl("curl -X DELETE https://example.com/a").method == "DELETE"


def test_parse_short_header_flag() -> None:
    req = parse_curl("curl -H 'X-Api-Key: secret' https://example.com/")
    assert req.headers["X-Api-Key"] == "secret"


def test_parse_query_parameters() -> None:
    req = parse_curl("curl 'https://example.com/search?q=test&page=1'")
    assert req.query_parameters.get("q") == "test"
    assert req.query_parameters.get("page") == "1"


def test_parse_data_raw() -> None:
    req = parse_curl("curl --data-raw '{\"a\":1}' https://example.com/x")
    assert req.method == "POST"
    assert req.body == '{"a":1}'


def test_parse_missing_url() -> None:
    req = parse_curl("curl -X GET")
    assert not req.url
    assert req.parse_errors
    assert not req.is_valid


def test_parse_empty() -> None:
    req = parse_curl("   ")
    assert req.parse_errors
    assert not req.is_valid


def test_parse_head() -> None:
    req = parse_curl("curl -I https://example.com/")
    assert req.method == "HEAD"


def test_parse_escaped_quotes() -> None:
    req = parse_curl("""curl -H "Authorization: Bearer abc" https://example.com""")
    assert "Bearer abc" in req.headers.get("Authorization", "")
