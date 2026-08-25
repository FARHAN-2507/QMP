"""TEST 03 — HTTP Status Code."""

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


def classify_status(code: int) -> str:
    if 200 <= code < 300:
        return "2xx Success"
    if 300 <= code < 400:
        return "3xx Redirect"
    if 400 <= code < 500:
        return "4xx Client Error"
    if 500 <= code < 600:
        return "5xx Server Error"
    return "Unknown"


class StatusCodeRule(SmokeTestRule):
    @property
    def test_id(self) -> str:
        return "SMOKE-03"

    @property
    def test_name(self) -> str:
        return "HTTP Status Code"

    def evaluate(
        self,
        request: ApiRequest,
        exchange: HttpExchange | None,
        settings: SmokeSettings,
    ) -> SmokeTestResult:
        start = time.monotonic()
        if exchange is None or exchange.status_code is None:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.SKIPPED,
                severity=Severity.HIGH,
                expected="HTTP status received",
                actual="No status",
                message="Skipped — no response status",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        code = exchange.status_code
        expected = settings.expected_status_code_list
        class_label = classify_status(code)
        ok = code in expected if expected else 200 <= code < 300

        duration = int((time.monotonic() - start) * 1000)
        if ok:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.PASS,
                severity=Severity.HIGH,
                expected=f"One of {expected}" if expected else "2xx",
                actual=f"{code} {exchange.reason_phrase} ({class_label})",
                message="Status code within expected set",
                duration_ms=duration or exchange.elapsed_ms,
            )

        # 4xx/5xx are FAIL; unexpected 3xx WARNING if not in list
        if 300 <= code < 400:
            status = SmokeTestStatus.WARNING
            severity = Severity.MEDIUM
        else:
            status = SmokeTestStatus.FAIL
            severity = Severity.HIGH

        return SmokeTestResult(
            test_id=self.test_id,
            test_name=self.test_name,
            status=status,
            severity=severity,
            expected=f"One of {expected}" if expected else "2xx",
            actual=f"{code} {exchange.reason_phrase} ({class_label})",
            message=f"Unexpected status: {code}",
            duration_ms=duration or exchange.elapsed_ms,
        )
