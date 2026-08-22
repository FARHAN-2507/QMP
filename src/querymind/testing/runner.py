"""Test runner — executes test cases and returns results.

The runner sends HTTP requests and evaluates assertions.
It's deterministic: same input → same output.
"""

from __future__ import annotations

import time

import httpx

from querymind.testing.assertions import evaluate_assertion
from querymind.testing.models import (
    ApiTestCase,
    ApiTestResult,
    AssertionResult,
    TestStatus,
)


async def run_test(test_case: ApiTestCase) -> ApiTestResult:
    """Execute a single test case.

    Sends the HTTP request, evaluates all assertions, and returns
    a structured ApiTestResult.
    """
    req = test_case.request
    try:
        start = time.monotonic()
        async with httpx.AsyncClient(
            timeout=req.timeout, follow_redirects=True, verify=False,
        ) as client:
            response = await client.request(
                method=req.method,
                url=req.url,
                headers=req.headers,
                json=req.body,
            )
        elapsed_ms = int((time.monotonic() - start) * 1000)

        # Parse response
        try:
            resp_body = response.json()
        except Exception:
            resp_body = response.text

        resp_headers = {k.lower(): v for k, v in response.headers.items()}

        # Evaluate assertions
        assertion_results: list[AssertionResult] = []
        for assertion in test_case.assertions:
            result = evaluate_assertion(
                assertion=assertion,
                status_code=response.status_code,
                headers=resp_headers,
                body=resp_body,
                elapsed_ms=elapsed_ms,
            )
            assertion_results.append(result)

        # Determine overall status
        if any(not a.passed for a in assertion_results):
            status = TestStatus.FAILED
        else:
            status = TestStatus.PASSED

        return ApiTestResult(
            test_name=test_case.name,
            status=status,
            assertion_results=assertion_results,
            response_status_code=response.status_code,
            response_headers=resp_headers,
            response_body=resp_body,
            elapsed_ms=elapsed_ms,
        )

    except httpx.TimeoutException:
        return ApiTestResult(
            test_name=test_case.name,
            status=TestStatus.ERROR,
            error=f"Request timed out after {req.timeout}s",
        )
    except httpx.RequestError as e:
        return ApiTestResult(
            test_name=test_case.name,
            status=TestStatus.ERROR,
            error=f"Request failed: {e}",
        )
    except Exception as e:
        return ApiTestResult(
            test_name=test_case.name,
            status=TestStatus.ERROR,
            error=f"Unexpected error: {e}",
        )


async def run_test_suite(test_cases: list[ApiTestCase]) -> list[ApiTestResult]:
    """Execute a list of test cases and return all results."""
    results: list[ApiTestResult] = []
    for tc in test_cases:
        result = await run_test(tc)
        results.append(result)
    return results
