"""Tests for smoke masking and security of reports."""

from __future__ import annotations

from pathlib import Path

from querymind.smoke.curl_parser import parse_curl
from querymind.smoke.engine import SmokeTestEngine
from querymind.smoke.executor import SmokeHttpExecutor
from querymind.smoke.masking import mask_header_value, mask_request_preview, mask_text
from querymind.smoke.models import (
    ApiRequest,
    HttpExchange,
)
from querymind.smoke.reporting.html import generate_html_report
from querymind.smoke.reporting.pdf import generate_pdf_report
from querymind.smoke.reporting.writer import write_json_results


def test_mask_bearer() -> None:
    masked = mask_header_value("Authorization", "Bearer abc123secret")
    assert "abc123secret" not in masked
    assert "Bearer" in masked
    assert "********" in masked


def test_mask_text_strips_bearer() -> None:
    text = "Authorization: Bearer abc123"
    out = mask_text(text)
    assert "abc123" not in out
    assert "********" in out


def test_preview_masks_auth() -> None:
    req = parse_curl(
        "curl -H 'Authorization: Bearer supersecret' https://example.com/api"
    )
    preview = mask_request_preview(req)
    headers = preview["headers"]
    assert "supersecret" not in str(headers)
    assert "********" in str(headers.get("Authorization", ""))


def test_html_and_json_and_pdf_mask_secrets(tmp_path: Path) -> None:
    req = parse_curl(
        "curl -H 'Authorization: Bearer abc123token' "
        "-H 'Content-Type: application/json' "
        "https://httpbin.org/get"
    )
    exchange = HttpExchange(
        request=req,
        status_code=200,
        response_headers={"Content-Type": "application/json"},
        response_body='{"ok": true}',
        elapsed_ms=50,
        executed=True,
        connected=True,
        dns_ok=True,
        original_url=req.url,
        final_url=req.url,
    )
    # Build report without live HTTP
    engine = SmokeTestEngine(executor=_FakeExecutor(exchange))
    report = engine.run(req, execute_http=True)

    html = generate_html_report(report)
    assert "abc123token" not in html
    assert "Bearer ********" in html or "********" in html

    json_path = write_json_results(report, tmp_path / "test-results.json")
    json_text = json_path.read_text(encoding="utf-8")
    assert "abc123token" not in json_text

    pdf_path = generate_pdf_report(report, tmp_path / "API-Smoke-Test-Report.pdf")
    assert pdf_path.exists()
    # PDF is binary; ensure secret bytes not present
    raw = pdf_path.read_bytes()
    assert b"abc123token" not in raw


class _FakeExecutor(SmokeHttpExecutor):
    def __init__(self, exchange: HttpExchange) -> None:
        super().__init__()
        self._exchange = exchange
        self._execution_count = 0

    def execute(self, request: ApiRequest) -> HttpExchange:
        self._execution_count += 1
        self._exchange.request = request
        return self._exchange
