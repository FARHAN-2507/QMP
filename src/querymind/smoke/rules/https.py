"""TEST 11 — HTTPS, TEST 12 — Redirects."""

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


class HttpsRule(SmokeTestRule):
    @property
    def test_id(self) -> str:
        return "SMOKE-11"

    @property
    def test_name(self) -> str:
        return "HTTPS"

    def evaluate(
        self,
        request: ApiRequest,
        exchange: HttpExchange | None,
        settings: SmokeSettings,
    ) -> SmokeTestResult:
        start = time.monotonic()
        if not settings.enable_https_check:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.SKIPPED,
                severity=Severity.LOW,
                expected="https preferred",
                actual="Disabled",
                message="HTTPS check disabled",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        parsed = urlparse(request.url)
        host = (parsed.hostname or "").lower()
        is_local = host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local")
        duration = int((time.monotonic() - start) * 1000)

        if parsed.scheme == "https":
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.PASS,
                severity=Severity.MEDIUM,
                expected="https://",
                actual=request.url.split("?", 1)[0],
                message="HTTPS in use",
                duration_ms=duration,
            )

        if parsed.scheme == "http" and is_local:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.INFO,
                severity=Severity.LOW,
                expected="https preferred (localhost exempt)",
                actual="http:// localhost/dev",
                message="HTTP on localhost/development — not failed",
                duration_ms=duration,
            )

        if parsed.scheme == "http":
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.WARNING,
                severity=Severity.MEDIUM,
                expected="https://",
                actual="http://",
                message="API uses HTTP instead of HTTPS",
                duration_ms=duration,
            )

        return SmokeTestResult(
            test_id=self.test_id,
            test_name=self.test_name,
            status=SmokeTestStatus.FAIL,
            severity=Severity.HIGH,
            expected="http or https",
            actual=parsed.scheme or "(none)",
            message="Unsupported URL scheme",
            duration_ms=duration,
        )


class RedirectRule(SmokeTestRule):
    @property
    def test_id(self) -> str:
        return "SMOKE-12"

    @property
    def test_name(self) -> str:
        return "Redirect Handling"

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
                expected="Redirects captured",
                actual="N/A",
                message="No exchange",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        duration = int((time.monotonic() - start) * 1000)
        details = {
            "original_url": exchange.original_url,
            "final_url": exchange.final_url,
            "redirect_count": exchange.redirect_count,
            "history": exchange.redirect_history,
            "final_status": exchange.status_code,
        }

        if exchange.redirect_count == 0:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.PASS,
                severity=Severity.LOW,
                expected="No unexpected redirects",
                actual="0 redirects",
                message="No redirects",
                duration_ms=duration,
                details=details,
            )

        if exchange.redirect_count > 5:
            return SmokeTestResult(
                test_id=self.test_id,
                test_name=self.test_name,
                status=SmokeTestStatus.WARNING,
                severity=Severity.MEDIUM,
                expected="<= 5 redirects",
                actual=str(exchange.redirect_count),
                message="Unexpectedly high redirect count",
                duration_ms=duration,
                details=details,
            )

        return SmokeTestResult(
            test_id=self.test_id,
            test_name=self.test_name,
            status=SmokeTestStatus.INFO,
            severity=Severity.LOW,
            expected="Redirects documented",
            actual=f"{exchange.redirect_count} redirect(s) → {exchange.final_url}",
            message="Redirects captured",
            duration_ms=duration,
            details=details,
        )
