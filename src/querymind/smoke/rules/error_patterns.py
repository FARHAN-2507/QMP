"""TEST 08 — Error Response Consistency."""

from __future__ import annotations

import re
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

_ERROR_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"Internal Server Error",
        r"NullReferenceException",
        r"StackTrace",
        r"SQL Exception",
        r"SqlException",
        r"Database Error",
        r"Unhandled Exception",
        r"System\.\w+Exception",
        r"Traceback \(most recent call last\)",
    ]
]


class ErrorPatternRule(SmokeTestRule):
    @property
    def test_id(self) -> str:
        return "SMOKE-08"

    @property
    def test_name(self) -> str:
        return "Error Response Consistency"

    def evaluate(
        self,
        request: ApiRequest,
        exchange: HttpExchange | None,
        settings: SmokeSettings,
    ) -> SmokeTestResult:
        start = time.monotonic()
        if not settings.enable_error_pattern_detection:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.SKIPPED,
                severity=Severity.MEDIUM,
                expected="No obvious server error payloads",
                actual="Disabled",
                message="Error pattern detection disabled",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        if exchange is None or not exchange.executed:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.SKIPPED,
                severity=Severity.MEDIUM,
                expected="No error patterns in success responses",
                actual="N/A",
                message="No response body",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        body = exchange.response_body or ""
        duration = int((time.monotonic() - start) * 1000)
        matches = [p.pattern for p in _ERROR_PATTERNS if p.search(body)]

        # Only flag strongly on 2xx (server returned success with error payload)
        code = exchange.status_code or 0
        if matches and 200 <= code < 300:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.WARNING,
                severity=Severity.HIGH,
                expected="No server-error signatures in 2xx body",
                actual=", ".join(matches[:3]),
                message="Suspicious error content in successful response",
                duration_ms=duration,
                details={"patterns": matches},
            )

        if matches and code >= 500:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.INFO,
                severity=Severity.LOW,
                expected="Error body may describe failure",
                actual=", ".join(matches[:3]),
                message="Error patterns present (consistent with 5xx)",
                duration_ms=duration,
            )

        return SmokeTestResult(
            test_id=self.test_id,
            test_name=self.test_name,
            status=SmokeTestStatus.PASS,
            severity=Severity.MEDIUM,
            expected="No suspicious error signatures",
            actual="Clean",
            message="No obvious server-error patterns detected",
            duration_ms=duration,
        )
