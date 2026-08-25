"""Smoke-test engine — runs rules against a single HTTP exchange."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from querymind.smoke.config import SmokeSettings, smoke_settings
from querymind.smoke.executor import SmokeHttpExecutor
from querymind.smoke.models import (
    ApiRequest,
    HttpExchange,
    OverallStatus,
    ReportSummary,
    SmokeTestReport,
    SmokeTestResult,
    SmokeTestStatus,
)
from querymind.smoke.rules import default_rules
from querymind.smoke.rules.base import SmokeTestRule

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, SmokeTestResult | None], None]


class SmokeTestEngine:
    """Orchestrates parse → single execute → rule evaluation → report model."""

    def __init__(
        self,
        settings: SmokeSettings | None = None,
        rules: list[SmokeTestRule] | None = None,
        executor: SmokeHttpExecutor | None = None,
    ) -> None:
        self._settings = settings or smoke_settings
        self._rules = rules if rules is not None else default_rules()
        self._executor = executor or SmokeHttpExecutor(self._settings)

    @property
    def rules(self) -> list[SmokeTestRule]:
        return list(self._rules)

    @property
    def executor(self) -> SmokeHttpExecutor:
        return self._executor

    def run(
        self,
        request: ApiRequest,
        *,
        execute_http: bool = True,
        on_progress: ProgressCallback | None = None,
    ) -> SmokeTestReport:
        """Run smoke tests. HTTP is executed at most once when execute_http is True."""
        logger.info("SmokeTestStarted method=%s", request.method)
        started = time.monotonic()
        results: list[SmokeTestResult] = []
        exchange: HttpExchange | None = None

        # Pre-flight rules that do not need HTTP (parsing + validation + https + safety)
        pre_ids = {"SMOKE-01", "SMOKE-15", "SMOKE-11", "SMOKE-14"}

        for rule in self._rules:
            if rule.test_id in pre_ids:
                if on_progress:
                    on_progress(rule.test_name, None)
                result = self._safe_evaluate(rule, request, None)
                results.append(result)
                if on_progress:
                    on_progress(rule.test_name, result)
                logger.info(
                    "SmokeRuleCompleted id=%s status=%s", rule.test_id, result.status.value
                )

        # Abort HTTP if parsing/validation critically failed
        parse_failed = any(
            r.test_id in {"SMOKE-01", "SMOKE-15"} and r.status == SmokeTestStatus.FAIL
            for r in results
        )

        if execute_http and not parse_failed and request.is_valid:
            exchange = self._executor.execute(request)
        else:
            exchange = None

        # Remaining rules
        for rule in self._rules:
            if rule.test_id in pre_ids:
                continue
            if on_progress:
                on_progress(rule.test_name, None)
            result = self._safe_evaluate(rule, request, exchange)
            results.append(result)
            if on_progress:
                on_progress(rule.test_name, result)
            logger.info("SmokeRuleCompleted id=%s status=%s", rule.test_id, result.status.value)

        # Preserve declaration order by test_id order from rules list
        order = {r.test_id: i for i, r in enumerate(self._rules)}
        results.sort(key=lambda r: order.get(r.test_id, 999))

        elapsed = int((time.monotonic() - started) * 1000)
        summary = self._summarize(results, elapsed)
        report = SmokeTestReport(
            title="API Smoke Test Report",
            endpoint=request.endpoint_label(),
            request=request,
            exchange=exchange,
            results=results,
            summary=summary,
            config_snapshot=self._settings.snapshot(),
        )
        logger.info(
            "SmokeTestCompleted overall=%s total=%s",
            summary.overall_status.value,
            summary.total,
        )
        return report

    def _safe_evaluate(
        self,
        rule: SmokeTestRule,
        request: ApiRequest,
        exchange: HttpExchange | None,
    ) -> SmokeTestResult:
        logger.info("SmokeRuleStarted id=%s", rule.test_id)
        try:
            return rule.evaluate(request, exchange, self._settings)
        except Exception as e:
            logger.exception("Smoke rule %s crashed", rule.test_id)
            return SmokeTestResult(
                test_id=rule.test_id,
                test_name=rule.test_name,
                status=SmokeTestStatus.FAIL,
                expected="Rule completes without error",
                actual=str(e),
                message=f"Rule error (engine continued): {e}",
            )

    def _summarize(self, results: list[SmokeTestResult], duration_ms: int) -> ReportSummary:
        passed = sum(1 for r in results if r.status == SmokeTestStatus.PASS)
        failed = sum(1 for r in results if r.status == SmokeTestStatus.FAIL)
        warnings = sum(1 for r in results if r.status == SmokeTestStatus.WARNING)
        skipped = sum(1 for r in results if r.status == SmokeTestStatus.SKIPPED)
        info = sum(1 for r in results if r.status == SmokeTestStatus.INFO)
        total = len(results)

        critical_fail = any(
            r.status == SmokeTestStatus.FAIL
            and r.severity.value in {"CRITICAL", "HIGH"}
            for r in results
        ) or failed > 0

        if critical_fail or failed > 0:
            overall = OverallStatus.FAIL
        elif warnings > 0:
            overall = OverallStatus.PASS_WITH_WARNINGS
        else:
            overall = OverallStatus.PASS

        score = self._health_score(results)
        return ReportSummary(
            total=total,
            passed=passed,
            failed=failed,
            warnings=warnings,
            skipped=skipped,
            info=info,
            duration_ms=duration_ms,
            overall_status=overall,
            health_score=score,
        )

    def _health_score(self, results: list[SmokeTestResult]) -> int:
        if not results:
            return 0
        s = self._settings
        weights = {
            SmokeTestStatus.PASS: s.health_pass_weight,
            SmokeTestStatus.WARNING: s.health_warning_weight,
            SmokeTestStatus.FAIL: s.health_fail_weight,
            SmokeTestStatus.SKIPPED: s.health_skip_weight,
            SmokeTestStatus.INFO: s.health_info_weight,
        }
        total = sum(weights.get(r.status, 50) for r in results)
        return int(round(total / len(results)))
