"""TEST 13 — Authentication, TEST 14 — Duplicate Execution Safety."""

from __future__ import annotations

import time

from querymind.smoke.config import SmokeSettings
from querymind.smoke.masking import is_sensitive_header
from querymind.smoke.models import (
    ApiRequest,
    HttpExchange,
    Severity,
    SmokeTestResult,
    SmokeTestStatus,
)
from querymind.smoke.rules.base import SmokeTestRule


class AuthenticationRule(SmokeTestRule):
    @property
    def test_id(self) -> str:
        return "SMOKE-13"

    @property
    def test_name(self) -> str:
        return "Authentication"

    def evaluate(
        self,
        request: ApiRequest,
        exchange: HttpExchange | None,
        settings: SmokeSettings,
    ) -> SmokeTestResult:
        start = time.monotonic()
        auth_headers = [k for k in request.headers if is_sensitive_header(k)]
        has_auth = bool(auth_headers) or bool(request.authentication) or bool(request.cookies)
        duration = int((time.monotonic() - start) * 1000)

        if not has_auth:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.INFO,
                severity=Severity.LOW,
                expected="Auth present when required by API",
                actual="No auth in cURL",
                message="No authentication detected in request",
                duration_ms=duration,
            )

        # Auth present — check response for obvious auth failure
        code = exchange.status_code if exchange else None
        if code in {401, 403}:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.FAIL,
                severity=Severity.HIGH,
                expected="Successful authentication (not 401/403)",
                actual=str(code),
                message="Authentication appears to have failed",
                duration_ms=duration,
                details={"auth_headers_present": True, "masked": True},
            )

        return SmokeTestResult(
            test_id=self.test_id,
            test_name=self.test_name,
            status=SmokeTestStatus.PASS,
            severity=Severity.HIGH,
            expected="Auth material present; secrets masked in reports",
            actual="Auth headers present (masked)",
            message="Authentication information present; secrets will not be displayed",
            duration_ms=duration,
            details={"auth_headers_present": True, "masked": True},
        )


class DestructiveSafetyRule(SmokeTestRule):
    """Documents destructive-method awareness. Single execution is enforced by engine."""

    @property
    def test_id(self) -> str:
        return "SMOKE-14"

    @property
    def test_name(self) -> str:
        return "Duplicate Execution Safety"

    def evaluate(
        self,
        request: ApiRequest,
        exchange: HttpExchange | None,
        settings: SmokeSettings,
    ) -> SmokeTestResult:
        start = time.monotonic()
        duration = int((time.monotonic() - start) * 1000)
        method = request.method.upper()

        if method in {"POST", "PUT", "PATCH", "DELETE"}:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.WARNING,
                severity=Severity.HIGH,
                expected="Run once for state-changing methods",
                actual=f"{method} — potentially state-changing",
                message=(
                    "This API may modify data. Executed at most once per run "
                    "(no automatic retries)."
                ),
                duration_ms=duration,
                details={"destructive": True, "method": method},
            )

        return SmokeTestResult(
            test_id=self.test_id,
            test_name=self.test_name,
            status=SmokeTestStatus.PASS,
            severity=Severity.LOW,
            expected="Safe method or confirmed single run",
            actual=f"{method} generally safe",
            message="Method is generally safe for repeated reads",
            duration_ms=duration,
            details={"destructive": False, "method": method},
        )
