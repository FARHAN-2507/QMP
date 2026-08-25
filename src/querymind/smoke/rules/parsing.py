"""TEST 01 — Request Parsing, TEST 15 — Request Validation."""

from __future__ import annotations

import time
from urllib.parse import urlparse

from querymind.smoke.config import SmokeSettings
from querymind.smoke.models import (
    ApiRequest,
    HttpExchange,
    Severity,
    SmokeTestResult,
    SmokeTestStatus,
)
from querymind.smoke.rules.base import SmokeTestRule


class RequestParsingRule(SmokeTestRule):
    @property
    def test_id(self) -> str:
        return "SMOKE-01"

    @property
    def test_name(self) -> str:
        return "Request Parsing"

    def evaluate(
        self,
        request: ApiRequest,
        exchange: HttpExchange | None,
        settings: SmokeSettings,
    ) -> SmokeTestResult:
        start = time.monotonic()
        ok = (
            bool(request.method)
            and bool(request.url)
            and not request.parse_errors
        )
        duration = int((time.monotonic() - start) * 1000)
        if ok:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.PASS,
                severity=Severity.HIGH,
                expected="Valid method, URL, headers, body",
                actual=f"{request.method} {request.url} ({len(request.headers)} headers)",
                message="cURL parsed successfully",
                duration_ms=duration,
            )
        return SmokeTestResult(
            test_id=self.test_id,
            test_name=self.test_name,
            status=SmokeTestStatus.FAIL,
            severity=Severity.CRITICAL,
            expected="Valid cURL with method and URL",
            actual="; ".join(request.parse_errors) or "Incomplete parse",
            message="Unable to parse cURL. Please verify the request.",
            duration_ms=duration,
            details={"errors": request.parse_errors},
        )


class RequestValidationRule(SmokeTestRule):
    @property
    def test_id(self) -> str:
        return "SMOKE-15"

    @property
    def test_name(self) -> str:
        return "Request Validation"

    def evaluate(
        self,
        request: ApiRequest,
        exchange: HttpExchange | None,
        settings: SmokeSettings,
    ) -> SmokeTestResult:
        start = time.monotonic()
        problems: list[str] = []
        if not request.method:
            problems.append("HTTP method missing")
        elif request.method.upper() not in {
            "GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"
        }:
            problems.append(f"Unsupported method: {request.method}")

        if not request.url:
            problems.append("URL missing")
        else:
            parsed = urlparse(request.url)
            if parsed.scheme not in {"http", "https"}:
                problems.append(f"Invalid URL scheme: {parsed.scheme or '(none)'}")
            if not parsed.netloc:
                problems.append(f"Invalid URL: {request.url}")

        for name, value in request.headers.items():
            if "\n" in name or "\n" in value:
                problems.append(f"Invalid header syntax: {name}")

        if request.body and request.content_type:
            ct = request.content_type.lower()
            body = request.body.lstrip()
            if "json" in ct and body and not (body.startswith("{") or body.startswith("[")):
                problems.append("Body is not compatible with Content-Type application/json")

        duration = int((time.monotonic() - start) * 1000)
        if problems:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.FAIL,
                severity=Severity.HIGH,
                expected="Valid URL, method, headers, body/content-type",
                actual="; ".join(problems),
                message=problems[0],
                duration_ms=duration,
                details={"problems": problems},
            )
        return SmokeTestResult(
            test_id=self.test_id,
            test_name=self.test_name,
            status=SmokeTestStatus.PASS,
            severity=Severity.HIGH,
            expected="Valid request shape",
            actual="OK",
            message="Request validation passed",
            duration_ms=duration,
        )
