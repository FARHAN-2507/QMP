"""Tests for assertion engine."""

from querymind.testing.assertions import evaluate_assertion
from querymind.testing.models import Assertion, AssertionType


def test_status_code_pass() -> None:
    a = Assertion(type=AssertionType.STATUS_CODE, expected=200)
    r = evaluate_assertion(a, 200, {}, None, 0)
    assert r.passed
    assert r.actual == 200


def test_status_code_fail() -> None:
    a = Assertion(type=AssertionType.STATUS_CODE, expected=200)
    r = evaluate_assertion(a, 404, {}, None, 0)
    assert not r.passed
    assert "404" in r.message


def test_status_code_range_pass() -> None:
    a = Assertion(type=AssertionType.STATUS_CODE_RANGE, expected=[200, 299])
    r = evaluate_assertion(a, 201, {}, None, 0)
    assert r.passed


def test_status_code_range_fail() -> None:
    a = Assertion(type=AssertionType.STATUS_CODE_RANGE, expected=[200, 299])
    r = evaluate_assertion(a, 400, {}, None, 0)
    assert not r.passed


def test_header_exists_pass() -> None:
    a = Assertion(type=AssertionType.HEADER_EXISTS, expected="content-type")
    r = evaluate_assertion(a, 200, {"content-type": "application/json"}, None, 0)
    assert r.passed


def test_header_exists_fail() -> None:
    a = Assertion(type=AssertionType.HEADER_EXISTS, expected="x-custom")
    r = evaluate_assertion(a, 200, {"content-type": "application/json"}, None, 0)
    assert not r.passed


def test_json_property_exists_pass() -> None:
    a = Assertion(type=AssertionType.JSON_PROPERTY_EXISTS, path="user.name")
    r = evaluate_assertion(a, 200, {}, {"user": {"name": "Alice"}}, 0)
    assert r.passed


def test_json_property_exists_fail() -> None:
    a = Assertion(type=AssertionType.JSON_PROPERTY_EXISTS, path="user.email")
    r = evaluate_assertion(a, 200, {}, {"user": {"name": "Alice"}}, 0)
    assert not r.passed


def test_json_property_equals_pass() -> None:
    a = Assertion(type=AssertionType.JSON_PROPERTY_EQUALS, path="status", expected="ok")
    r = evaluate_assertion(a, 200, {}, {"status": "ok"}, 0)
    assert r.passed


def test_json_property_equals_fail() -> None:
    a = Assertion(type=AssertionType.JSON_PROPERTY_EQUALS, path="status", expected="ok")
    r = evaluate_assertion(a, 200, {}, {"status": "error"}, 0)
    assert not r.passed


def test_json_property_type_pass() -> None:
    a = Assertion(type=AssertionType.JSON_PROPERTY_TYPE, path="count", expected="integer")
    r = evaluate_assertion(a, 200, {}, {"count": 42}, 0)
    assert r.passed


def test_json_property_type_fail() -> None:
    a = Assertion(type=AssertionType.JSON_PROPERTY_TYPE, path="count", expected="integer")
    r = evaluate_assertion(a, 200, {}, {"count": "forty-two"}, 0)
    assert not r.passed


def test_body_contains_pass() -> None:
    a = Assertion(type=AssertionType.BODY_CONTAINS, expected="hello")
    r = evaluate_assertion(a, 200, {}, "hello world", 0)
    assert r.passed


def test_body_contains_fail() -> None:
    a = Assertion(type=AssertionType.BODY_CONTAINS, expected="goodbye")
    r = evaluate_assertion(a, 200, {}, "hello world", 0)
    assert not r.passed


def test_response_time_pass() -> None:
    a = Assertion(type=AssertionType.RESPONSE_TIME_MS, expected=1000)
    r = evaluate_assertion(a, 200, {}, None, 500)
    assert r.passed


def test_response_time_fail() -> None:
    a = Assertion(type=AssertionType.RESPONSE_TIME_MS, expected=100)
    r = evaluate_assertion(a, 200, {}, None, 500)
    assert not r.passed


def test_body_not_empty_pass() -> None:
    a = Assertion(type=AssertionType.BODY_NOT_EMPTY)
    r = evaluate_assertion(a, 200, {}, {"data": "something"}, 0)
    assert r.passed


def test_body_not_empty_fail() -> None:
    a = Assertion(type=AssertionType.BODY_NOT_EMPTY)
    r = evaluate_assertion(a, 200, {}, None, 0)
    assert not r.passed


def test_json_schema_pass() -> None:
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        "required": ["name"],
    }
    a = Assertion(type=AssertionType.JSON_SCHEMA, expected=schema)
    r = evaluate_assertion(a, 200, {}, {"name": "Alice", "age": 30}, 0)
    assert r.passed


def test_json_schema_fail() -> None:
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    a = Assertion(type=AssertionType.JSON_SCHEMA, expected=schema)
    r = evaluate_assertion(a, 200, {}, {"age": 30}, 0)
    assert not r.passed
    assert "name" in r.message
