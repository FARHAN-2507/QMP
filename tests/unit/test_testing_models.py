"""Tests for test engine models."""

from querymind.testing.models import (
    ApiTestCase,
    ApiTestRequest,
    ApiTestResult,
    Assertion,
    AssertionResult,
    AssertionType,
    TestStatus,
)


def test_test_request_defaults() -> None:
    req = ApiTestRequest(url="http://test.com")
    assert req.method == "GET"
    assert req.url == "http://test.com"
    assert req.headers == {}
    assert req.body is None
    assert req.timeout == 30


def test_test_case_creation() -> None:
    tc = ApiTestCase(
        name="test 1",
        request=ApiTestRequest(url="http://test.com"),
        assertions=[
            Assertion(type=AssertionType.STATUS_CODE, expected=200),
        ],
    )
    assert tc.name == "test 1"
    assert len(tc.assertions) == 1


def test_assertion_result_passed() -> None:
    a = Assertion(type=AssertionType.STATUS_CODE, expected=200)
    r = AssertionResult(assertion=a, passed=True, actual=200)
    assert r.passed
    assert r.message == ""


def test_assertion_result_failed() -> None:
    a = Assertion(type=AssertionType.STATUS_CODE, expected=200)
    r = AssertionResult(
        assertion=a, passed=False, actual=404,
        message="Expected 200, got 404",
    )
    assert not r.passed
    assert "404" in r.message


def test_test_result_passed() -> None:
    r = ApiTestResult(
        test_name="t",
        status=TestStatus.PASSED,
        assertion_results=[
            AssertionResult(
                assertion=Assertion(type=AssertionType.STATUS_CODE, expected=200),
                passed=True,
            ),
        ],
    )
    assert r.passed_count == 1
    assert r.failed_count == 0
    assert "PASSED" in r.summary()


def test_test_result_failed() -> None:
    r = ApiTestResult(
        test_name="t",
        status=TestStatus.FAILED,
        assertion_results=[
            AssertionResult(
                assertion=Assertion(type=AssertionType.STATUS_CODE, expected=200),
                passed=True,
            ),
            AssertionResult(
                assertion=Assertion(type=AssertionType.STATUS_CODE, expected=201),
                passed=False, actual=200, message="Expected 201",
            ),
        ],
    )
    assert r.passed_count == 1
    assert r.failed_count == 1
    assert "FAILED" in r.summary()


def test_test_result_error() -> None:
    r = ApiTestResult(test_name="t", status=TestStatus.ERROR, error="timeout")
    assert "ERROR" in r.summary()
    assert "timeout" in r.summary()
