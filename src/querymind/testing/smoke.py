"""Smoke testing — fast, no-LLM API health checks.

Deterministic smoke tests that run without consuming tokens.
Tests core API functionality: health, availability, response times.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urljoin

import httpx

from querymind.testing.models import (
    ApiTestCase,
    ApiTestRequest,
    ApiTestResult,
    Assertion,
    AssertionType,
    TestStatus,
)
from querymind.testing.runner import run_test_suite

# Common health endpoints to probe
HEALTH_ENDPOINTS = [
    "/health",
    "/healthz",
    "/api/health",
    "/status",
    "/api/status",
    "/",
]


class SmokeTestConfig:
    """Configuration for smoke tests."""

    def __init__(
        self,
        base_url: str,
        timeout_ms: int = 5000,
        include_write_tests: bool = False,
        auth_provider: Any | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_ms = timeout_ms
        self.timeout_s = timeout_ms / 1000
        self.include_write_tests = include_write_tests
        self.auth_provider = auth_provider


async def discover_endpoints(base_url: str, timeout_s: float = 5.0) -> list[dict[str, Any]]:
    """Discover API endpoints by probing common paths.

    Returns list of endpoint dicts with path, method, status_code.
    """
    endpoints: list[dict[str, Any]] = []
    probe_paths = [
        "/",
        "/api",
        "/api/v1",
        "/api/v2",
        "/health",
        "/healthz",
        "/status",
        "/docs",
        "/swagger.json",
        "/openapi.json",
        "/api-docs",
        "/api/users",
        "/api/auth",
        "/api/products",
        "/api/items",
        "/api/posts",
    ]

    try:
        async with httpx.AsyncClient(
            timeout=timeout_s, follow_redirects=False, verify=False,
        ) as client:
            for path in probe_paths:
                url = urljoin(base_url + "/", path.lstrip("/"))
                try:
                    start = time.monotonic()
                    response = await client.request("GET", url)
                    elapsed_ms = int((time.monotonic() - start) * 1000)

                    if response.status_code not in (404, 405, 500, 502, 503):
                        endpoints.append({
                            "path": path,
                            "method": "GET",
                            "status_code": response.status_code,
                            "elapsed_ms": elapsed_ms,
                            "content_type": response.headers.get("content-type", ""),
                        })
                except httpx.RequestError:
                    continue
    except Exception:
        pass

    return endpoints


def generate_health_tests(config: SmokeTestConfig) -> list[ApiTestCase]:
    """Generate health check smoke tests."""
    tests: list[ApiTestCase] = []

    for path in HEALTH_ENDPOINTS:
        url = f"{config.base_url}{path}"
        tests.append(ApiTestCase(
            name=f"Health: {path}",
            description=f"Check if {path} is available",
            request=ApiTestRequest(
                method="GET",
                url=url,
                timeout=int(config.timeout_s),
            ),
            assertions=[
                Assertion(
                    type=AssertionType.STATUS_CODE_RANGE,
                    expected=[200, 399],
                    description=f"Returns 2xx/3xx for {path}",
                ),
                Assertion(
                    type=AssertionType.RESPONSE_TIME_MS,
                    expected=config.timeout_ms,
                    description=f"Responds within {config.timeout_ms}ms",
                ),
            ],
        ))

    return tests


def generate_endpoint_tests(
    config: SmokeTestConfig,
    endpoints: list[dict[str, Any]],
) -> list[ApiTestCase]:
    """Generate smoke tests for discovered endpoints."""
    tests: list[ApiTestCase] = []

    for ep in endpoints:
        path = ep.get("path", "/")
        method = ep.get("method", "GET").upper()

        # Skip non-GET methods unless write tests enabled
        if method != "GET" and not config.include_write_tests:
            continue

        url = f"{config.base_url}{path}"

        # Build assertions based on response
        assertions: list[Assertion] = [
            Assertion(
                type=AssertionType.RESPONSE_TIME_MS,
                expected=config.timeout_ms,
                description=f"Responds within {config.timeout_ms}ms",
            ),
        ]

        # For successful responses, add more checks
        status_code = ep.get("status_code", 200)
        if 200 <= status_code < 300:
            assertions.append(Assertion(
                type=AssertionType.STATUS_CODE,
                expected=200,
                description="Returns 200 OK",
            ))
            assertions.append(Assertion(
                type=AssertionType.BODY_NOT_EMPTY,
                description="Response body is not empty",
            ))

            # Check content-type for JSON endpoints
            content_type = ep.get("content_type", "")
            if "json" in content_type:
                assertions.append(Assertion(
                    type=AssertionType.HEADER_EXISTS,
                    expected="content-type",
                    description="Has content-type header",
                ))
        else:
            # For non-200, just check it responds
            assertions.append(Assertion(
                type=AssertionType.STATUS_CODE_RANGE,
                expected=[200, 499],
                description="Returns a valid status code",
            ))

        tests.append(ApiTestCase(
            name=f"{method} {path}",
            description=f"Smoke test {method} {path}",
            request=ApiTestRequest(
                method="GET",  # Always GET for smoke tests
                url=url,
                timeout=int(config.timeout_s),
            ),
            assertions=assertions,
        ))

    return tests


def generate_openapi_tests(
    config: SmokeTestConfig,
    spec: dict[str, Any],
) -> list[ApiTestCase]:
    """Generate smoke tests from an OpenAPI spec."""
    tests: list[ApiTestCase] = []

    # Extract paths from spec
    paths = spec.get("paths", {})
    for path, methods in paths.items():
        for method, details in methods.items():
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue

            # Skip non-GET unless write tests enabled
            if method.upper() != "GET" and not config.include_write_tests:
                continue

            url = f"{config.base_url}{path}"

            # Get expected response codes
            responses = details.get("responses", {})
            success_codes = [
                int(code) for code in responses
                if code.startswith("2")
            ]

            assertions: list[Assertion] = [
                Assertion(
                    type=AssertionType.RESPONSE_TIME_MS,
                    expected=config.timeout_ms,
                    description=f"Responds within {config.timeout_ms}ms",
                ),
            ]

            if success_codes:
                assertions.append(Assertion(
                    type=AssertionType.STATUS_CODE_RANGE,
                    expected=[min(success_codes), max(success_codes)],
                    description="Returns expected status code",
                ))
            else:
                assertions.append(Assertion(
                    type=AssertionType.STATUS_CODE_RANGE,
                    expected=[200, 299],
                    description="Returns 2xx success",
                ))

            tests.append(ApiTestCase(
                name=f"{method.upper()} {path}",
                description=details.get("summary", f"Smoke test {method.upper()} {path}"),
                request=ApiTestRequest(
                    method="GET",  # Always GET for smoke tests
                    url=url,
                    timeout=int(config.timeout_s),
                ),
                assertions=assertions,
            ))

    return tests


async def run_smoke_tests(
    config: SmokeTestConfig,
    spec: dict[str, Any] | None = None,
) -> list[ApiTestResult]:
    """Full smoke test pipeline: discover/generate -> run -> return results.

    This is the main entry point for smoke testing.
    """
    tests: list[ApiTestCase] = []

    # 1. Always add health checks
    tests.extend(generate_health_tests(config))

    # 2. If OpenAPI spec provided, use it
    if spec:
        tests.extend(generate_openapi_tests(config, spec))
    else:
        # 3. Otherwise, discover endpoints
        endpoints = await discover_endpoints(config.base_url, config.timeout_s)
        if endpoints:
            tests.extend(generate_endpoint_tests(config, endpoints))

    # 4. Run all tests
    if not tests:
        return [ApiTestResult(
            test_name="Smoke Test Setup",
            status=TestStatus.ERROR,
            error="No endpoints discovered and no OpenAPI spec provided",
        )]

    return await run_test_suite(tests, auth_provider=config.auth_provider)
