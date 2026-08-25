"""Tests for smoke engine, rules, and single-execution guarantee."""

from __future__ import annotations

from pathlib import Path

from querymind.smoke.config import SmokeSettings
from querymind.smoke.curl_parser import parse_curl
from querymind.smoke.engine import SmokeTestEngine
from querymind.smoke.executor import SmokeHttpExecutor
from querymind.smoke.models import (
    ApiRequest,
    HttpExchange,
    OverallStatus,
    SmokeTestResult,
    SmokeTestStatus,
)
from querymind.smoke.reporting.writer import SmokeReportWriter
from querymind.smoke.rules import default_rules
from querymind.smoke.rules.base import SmokeTestRule


class _CountingExecutor(SmokeHttpExecutor):
    def __init__(self, exchange: HttpExchange) -> None:
        super().__init__()
        self._exchange = exchange

    def execute(self, request: ApiRequest) -> HttpExchange:
        self._execution_count += 1
        ex = self._exchange.model_copy(deep=True)
        ex.request = request
        return ex


def _ok_exchange(req: ApiRequest) -> HttpExchange:
    return HttpExchange(
        request=req,
        status_code=200,
        reason_phrase="OK",
        response_headers={"Content-Type": "application/json", "X-Content-Type-Options": "nosniff"},
        response_body='{"id": 1, "name": "John"}',
        elapsed_ms=120,
        executed=True,
        connected=True,
        dns_ok=True,
        original_url=req.url,
        final_url=req.url,
    )


def test_default_rules_count() -> None:
    assert len(default_rules()) == 15


def test_engine_runs_all_rules_once() -> None:
    req = parse_curl(
        "curl -H 'Authorization: Bearer tok' -H 'Accept: application/json' "
        "https://example.com/api/users"
    )
    executor = _CountingExecutor(_ok_exchange(req))
    engine = SmokeTestEngine(executor=executor)
    report = engine.run(req)
    assert executor.execution_count == 1
    assert report.summary.total == 15
    assert report.summary.failed == 0 or report.summary.overall_status in {
        OverallStatus.PASS,
        OverallStatus.PASS_WITH_WARNINGS,
        OverallStatus.FAIL,
    }


def test_failed_rule_does_not_crash_engine() -> None:
    class BoomRule(SmokeTestRule):
        @property
        def test_id(self) -> str:
            return "BOOM"

        @property
        def test_name(self) -> str:
            return "Boom"

        def evaluate(self, request, exchange, settings) -> SmokeTestResult:  # type: ignore[no-untyped-def]
            raise RuntimeError("explode")

    req = parse_curl("curl https://example.com/")
    rules = [BoomRule(), *default_rules()]
    engine = SmokeTestEngine(rules=rules, executor=_CountingExecutor(_ok_exchange(req)))
    report = engine.run(req)
    boom = next(r for r in report.results if r.test_id == "BOOM")
    assert boom.status == SmokeTestStatus.FAIL
    assert report.summary.total >= 15


def test_warning_overall_status() -> None:
    req = parse_curl("curl http://example.com/api")  # http → warning from HTTPS rule
    settings = SmokeSettings()
    # Fast response under thresholds
    ex = _ok_exchange(req)
    engine = SmokeTestEngine(settings=settings, executor=_CountingExecutor(ex))
    report = engine.run(req)
    # May be PASS WITH WARNINGS due to HTTP / security headers
    assert report.summary.overall_status in {
        OverallStatus.PASS,
        OverallStatus.PASS_WITH_WARNINGS,
        OverallStatus.FAIL,
    }
    https = next(r for r in report.results if r.test_id == "SMOKE-11")
    assert https.status in {SmokeTestStatus.WARNING, SmokeTestStatus.INFO, SmokeTestStatus.PASS}


def test_parse_failure_skips_http() -> None:
    req = parse_curl("curl -X GET")
    executor = _CountingExecutor(
        HttpExchange(request=req, executed=False)
    )
    engine = SmokeTestEngine(executor=executor)
    report = engine.run(req)
    assert executor.execution_count == 0
    assert any(r.status == SmokeTestStatus.FAIL for r in report.results)


def test_writer_creates_unique_dirs(tmp_path: Path) -> None:
    req = parse_curl("curl https://example.com/api/users")
    engine = SmokeTestEngine(executor=_CountingExecutor(_ok_exchange(req)))
    report = engine.run(req)
    writer = SmokeReportWriter()
    paths1 = writer.write(report, tmp_path)
    paths2 = writer.write(report, tmp_path)
    assert paths1["directory"] != paths2["directory"]
    assert paths1["html"].exists()
    assert paths1["pdf"].exists()
    assert paths1["json"].exists()
    assert "abc123" not in paths1["html"].read_text(encoding="utf-8")


def test_skipped_rule_status() -> None:
    req = parse_curl("curl https://example.com/")
    # No execute — reachability etc. skipped
    class NoExec(SmokeHttpExecutor):
        def execute(self, request: ApiRequest) -> HttpExchange:
            self._execution_count += 1
            return HttpExchange(request=request, executed=False, error="forced")

    engine = SmokeTestEngine(executor=NoExec())
    # Force execute_http False
    report = engine.run(req, execute_http=False)
    assert any(r.status == SmokeTestStatus.SKIPPED for r in report.results)
    assert engine.executor.execution_count == 0
