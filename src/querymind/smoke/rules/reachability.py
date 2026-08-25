"""TEST 02 — API Reachability."""

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


class ReachabilityRule(SmokeTestRule):
    @property
    def test_id(self) -> str:
        return "SMOKE-02"

    @property
    def test_name(self) -> str:
        return "API Reachability"

    def evaluate(
        self,
        request: ApiRequest,
        exchange: HttpExchange | None,
        settings: SmokeSettings,
    ) -> SmokeTestResult:
        start = time.monotonic()
        duration = 0
        if exchange is None:
            duration = int((time.monotonic() - start) * 1000)
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.SKIPPED,
                severity=Severity.HIGH,
                expected="DNS + connection succeed",
                actual="No exchange",
                message="Request was not executed",
                duration_ms=duration,
            )

        if exchange.executed or exchange.connected:
            duration = int((time.monotonic() - start) * 1000)
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.PASS,
                severity=Severity.HIGH,
                expected="DNS resolution and connection",
                actual=f"dns={exchange.dns_ok} connected={exchange.connected}",
                message="API reached successfully",
                duration_ms=duration or exchange.elapsed_ms,
            )

        duration = int((time.monotonic() - start) * 1000)
        return SmokeTestResult(
            test_id=self.test_id,
            test_name=self.test_name,
            status=SmokeTestStatus.FAIL,
            severity=Severity.CRITICAL,
            expected="Reachable host",
            actual=exchange.error or "Unreachable",
            message=exchange.error or "API could not be reached",
            duration_ms=duration,
            details={"dns_ok": exchange.dns_ok},
        )
