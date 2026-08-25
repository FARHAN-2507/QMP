"""TEST 05 — Content-Type."""

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


class ContentTypeRule(SmokeTestRule):
    @property
    def test_id(self) -> str:
        return "SMOKE-05"

    @property
    def test_name(self) -> str:
        return "Content-Type"

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
                expected="Reasonable Content-Type",
                actual="N/A",
                message="No response headers",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        ct = ""
        for k, v in exchange.response_headers.items():
            if k.lower() == "content-type":
                ct = v
                break

        duration = int((time.monotonic() - start) * 1000)
        if not ct:
            # Empty body 204 — OK
            if exchange.status_code == 204:
                return SmokeTestResult(
                    test_id=self.test_id,
                    test_name=self.test_name,
                    status=SmokeTestStatus.PASS,
                    severity=Severity.LOW,
                    expected="Optional for 204",
                    actual="(none)",
                    message="No Content-Type on 204 — acceptable",
                    duration_ms=duration,
                )
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.WARNING,
                severity=Severity.LOW,
                expected="Content-Type present",
                actual="(missing)",
                message="Response missing Content-Type header",
                duration_ms=duration,
            )

        known = ("json", "xml", "text", "html", "javascript", "form", "octet-stream", "multipart")
        reasonable = any(k in ct.lower() for k in known) or "/" in ct

        # Infer JSON expectation from Accept / request content-type
        expect_json = False
        accept = ""
        for k, v in request.headers.items():
            if k.lower() == "accept" and "json" in v.lower():
                expect_json = True
                accept = v
            if k.lower() == "content-type" and "json" in v.lower():
                expect_json = True

        if expect_json and "json" not in ct.lower():
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.WARNING,
                severity=Severity.MEDIUM,
                expected="application/json (inferred)",
                actual=ct,
                message="Expected JSON Content-Type based on request headers",
                duration_ms=duration,
                details={"accept": accept},
            )

        if reasonable:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.PASS,
                severity=Severity.MEDIUM,
                expected="Recognizable media type",
                actual=ct,
                message="Content-Type looks reasonable",
                duration_ms=duration,
            )

        return SmokeTestResult(
            test_id=self.test_id,
            test_name=self.test_name,
            status=SmokeTestStatus.WARNING,
            severity=Severity.LOW,
            expected="Recognizable media type",
            actual=ct,
            message="Unusual Content-Type",
            duration_ms=duration,
        )
