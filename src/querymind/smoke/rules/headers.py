"""TEST 09 — Response Headers, TEST 10 — Security Headers."""

from __future__ import annotations

import time

from querymind.smoke.config import SmokeSettings
from querymind.smoke.models import (
    ApiRequest,
    HttpExchange,
    Severity,
    SmokeTestResult,
    SmokeTestStatus,
)
from querymind.smoke.rules.base import SmokeTestRule

_RECOMMENDED = ("content-type", "cache-control", "content-length", "etag", "location")
_SECURITY = (
    "strict-transport-security",
    "x-content-type-options",
    "content-security-policy",
    "x-frame-options",
)


class ResponseHeadersRule(SmokeTestRule):
    @property
    def test_id(self) -> str:
        return "SMOKE-09"

    @property
    def test_name(self) -> str:
        return "Response Headers"

    def evaluate(
        self,
        request: ApiRequest,
        exchange: HttpExchange | None,
        settings: SmokeSettings,
    ) -> SmokeTestResult:
        start = time.monotonic()
        if exchange is None or not exchange.executed:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.SKIPPED,
                severity=Severity.LOW,
                expected="Basic response headers",
                actual="N/A",
                message="No headers",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        lower = {k.lower(): v for k, v in exchange.response_headers.items()}
        present = [h for h in _RECOMMENDED if h in lower]
        missing = [h for h in _RECOMMENDED if h not in lower]
        duration = int((time.monotonic() - start) * 1000)

        # Content-Type is the only soft "required" for non-204
        required_ok = "content-type" in lower or exchange.status_code == 204

        if not required_ok:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.WARNING,
                severity=Severity.MEDIUM,
                expected="Content-Type (required-ish)",
                actual=f"present={present}",
                message="Missing Content-Type header",
                duration_ms=duration,
                details={"recommended_missing": missing, "recommended_present": present},
            )

        return SmokeTestResult(
            test_id=self.test_id,
            test_name=self.test_name,
            status=SmokeTestStatus.PASS if present else SmokeTestStatus.INFO,
            severity=Severity.LOW,
            expected="Informational/recommended headers",
            actual=f"{len(present)} recommended present",
            message="Response headers inspected",
            duration_ms=duration,
            details={
                "recommended_present": present,
                "recommended_missing": missing,
                "informational": list(lower.keys())[:20],
            },
        )


class SecurityHeadersRule(SmokeTestRule):
    @property
    def test_id(self) -> str:
        return "SMOKE-10"

    @property
    def test_name(self) -> str:
        return "Security Headers"

    def evaluate(
        self,
        request: ApiRequest,
        exchange: HttpExchange | None,
        settings: SmokeSettings,
    ) -> SmokeTestResult:
        start = time.monotonic()
        if not settings.enable_security_header_checks:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.SKIPPED,
                severity=Severity.LOW,
                expected="Optional security headers",
                actual="Disabled",
                message="Security header checks disabled",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        if exchange is None or not exchange.executed:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.SKIPPED,
                severity=Severity.LOW,
                expected="Optional security headers",
                actual="N/A",
                message="No response",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        lower = {k.lower() for k in exchange.response_headers}
        found = [h for h in _SECURITY if h in lower]
        missing = [h for h in _SECURITY if h not in lower]
        duration = int((time.monotonic() - start) * 1000)

        if not found:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.WARNING,
                severity=Severity.LOW,
                expected="Common security headers when applicable",
                actual="None found",
                message="No common security headers present (may not apply to all APIs)",
                duration_ms=duration,
                details={"missing": missing},
            )

        return SmokeTestResult(
            test_id=self.test_id,
            test_name=self.test_name,
            status=SmokeTestStatus.INFO if missing else SmokeTestStatus.PASS,
            severity=Severity.LOW,
            expected="Security headers when applicable",
            actual=f"Found: {', '.join(found)}",
            message="Security headers inspected",
            duration_ms=duration,
            details={"found": found, "missing": missing},
        )
