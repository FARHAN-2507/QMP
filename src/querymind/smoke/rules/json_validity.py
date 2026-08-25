"""TEST 06 — JSON Validation."""

from __future__ import annotations

import json
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


class JsonValidityRule(SmokeTestRule):
    @property
    def test_id(self) -> str:
        return "SMOKE-06"

    @property
    def test_name(self) -> str:
        return "JSON Validation"

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
                expected="Valid JSON when Content-Type is JSON",
                actual="N/A",
                message="No response body",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        ct = ""
        for k, v in exchange.response_headers.items():
            if k.lower() == "content-type":
                ct = v.lower()
                break

        body = exchange.response_body or ""
        is_json_ct = "json" in ct
        looks_json = body.lstrip().startswith(("{", "["))

        duration = int((time.monotonic() - start) * 1000)

        if not is_json_ct and not looks_json:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.SKIPPED,
                severity=Severity.LOW,
                expected="N/A for non-JSON",
                actual=ct or "(no content-type)",
                message="Response is not JSON — skipped",
                duration_ms=duration,
            )

        if not body.strip():
            if exchange.status_code == 204:
                return SmokeTestResult(
                    test_id=self.test_id,
                    test_name=self.test_name,
                    status=SmokeTestStatus.PASS,
                    severity=Severity.LOW,
                    expected="Empty body for 204",
                    actual="(empty)",
                    message="Empty JSON body acceptable for 204",
                    duration_ms=duration,
                )
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.WARNING,
                severity=Severity.MEDIUM,
                expected="Parseable JSON body",
                actual="(empty)",
                message="JSON Content-Type with empty body",
                duration_ms=duration,
            )

        try:
            json.loads(body)
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.PASS,
                severity=Severity.MEDIUM,
                expected="Parseable JSON",
                actual="Valid JSON",
                message="JSON parsed successfully",
                duration_ms=duration,
            )
        except json.JSONDecodeError as e:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.FAIL,
                severity=Severity.MEDIUM,
                expected="Parseable JSON",
                actual=str(e),
                message="Malformed JSON response",
                duration_ms=duration,
            )
