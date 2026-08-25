"""TEST 07 — Response Body."""

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


class ResponseBodyRule(SmokeTestRule):
    @property
    def test_id(self) -> str:
        return "SMOKE-07"

    @property
    def test_name(self) -> str:
        return "Response Body"

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
                severity=Severity.MEDIUM,
                expected="Body presence appropriate for method/status",
                actual="N/A",
                message="No response",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        body = exchange.response_body or ""
        empty = not body.strip()
        code = exchange.status_code
        duration = int((time.monotonic() - start) * 1000)

        if code == 204 or request.method.upper() == "HEAD":
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.PASS,
                severity=Severity.LOW,
                expected="Empty body acceptable",
                actual="(empty)" if empty else f"{len(body)} bytes",
                message="Empty body acceptable for this status/method",
                duration_ms=duration,
            )

        if (
            empty
            and request.method.upper() in {"GET", "POST"}
            and code is not None
            and 200 <= code < 300
        ):
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.WARNING,
                severity=Severity.MEDIUM,
                expected="Non-empty body for successful GET/POST",
                actual="(empty)",
                message="Response body unexpectedly empty",
                duration_ms=duration,
            )

        return SmokeTestResult(
            test_id=self.test_id,
            test_name=self.test_name,
            status=SmokeTestStatus.PASS,
            severity=Severity.LOW,
            expected="Body present or acceptable empty",
            actual=f"{len(body)} bytes",
            message="Response body check passed",
            duration_ms=duration,
        )
