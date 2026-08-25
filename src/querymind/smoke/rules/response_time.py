"""TEST 04 — Response Time."""

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


class ResponseTimeRule(SmokeTestRule):
    @property
    def test_id(self) -> str:
        return "SMOKE-04"

    @property
    def test_name(self) -> str:
        return "Response Time"

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
                expected=f"<{settings.response_time_warning_ms} ms preferred",
                actual="N/A",
                message="No timing available",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        ms = exchange.elapsed_ms
        warn = settings.response_time_warning_ms
        fail = settings.response_time_failure_ms
        duration = int((time.monotonic() - start) * 1000)

        if ms > fail:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.FAIL,
                severity=Severity.MEDIUM,
                expected=f"<= {fail} ms",
                actual=f"{ms} ms",
                message=f"Response time {ms} ms exceeds failure threshold",
                duration_ms=duration,
            )
        if ms > warn:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.WARNING,
                severity=Severity.MEDIUM,
                expected=f"<= {warn} ms",
                actual=f"{ms} ms",
                message=f"Response time {ms} ms is slow",
                duration_ms=duration,
            )
        return SmokeTestResult(
            test_id=self.test_id,
            test_name=self.test_name,
            status=SmokeTestStatus.PASS,
            severity=Severity.MEDIUM,
            expected=f"<= {warn} ms",
            actual=f"{ms} ms",
            message=f"Response Time: {ms} ms",
            duration_ms=duration,
        )
