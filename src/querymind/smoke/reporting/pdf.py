"""PDF report generation via fpdf2."""

from __future__ import annotations

import logging
from pathlib import Path

from fpdf import FPDF

from querymind.smoke.masking import mask_headers, mask_request_preview, mask_text
from querymind.smoke.models import SmokeTestReport, SmokeTestStatus

logger = logging.getLogger(__name__)


class SmokePdf(FPDF):
    def footer(self) -> None:  # noqa: N802 — fpdf API
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def generate_pdf_report(report: SmokeTestReport, path: Path) -> Path:
    """Write a professional PDF summary to path."""
    pdf = SmokePdf(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    width = pdf.epw

    def line(text: str, *, bold: bool = False, size: int = 10) -> None:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B" if bold else "", size)
        pdf.multi_cell(width, 5, _safe(text))

    pdf.set_text_color(0, 0, 0)
    line("API Smoke Test Report", bold=True, size=18)
    pdf.ln(2)
    line(f"Endpoint: {report.endpoint}", size=11)
    line(f"Generated: {report.generated_at.strftime('%d %b %Y %I:%M %p UTC')}", size=11)

    s = report.summary
    pdf.ln(2)
    line(f"Overall Status: {s.overall_status.value}", bold=True, size=12)
    line(f"Health Score: {s.health_score}%", bold=True, size=12)

    pdf.ln(2)
    line("Summary", bold=True, size=11)
    for label, val in [
        ("Total Tests", s.total),
        ("Passed", s.passed),
        ("Failed", s.failed),
        ("Warnings", s.warnings),
        ("Skipped", s.skipped),
        ("Duration (ms)", s.duration_ms),
    ]:
        line(f"  {label}: {val}", size=10)

    pdf.ln(3)
    line("Test Results", bold=True, size=11)
    for r in report.results:
        line(
            f"{r.test_id} | {r.test_name} | {r.status.value} | "
            f"{r.duration_ms} ms | {r.severity.value}",
            size=9,
        )

    failed = [r for r in report.results if r.status == SmokeTestStatus.FAIL]
    warnings = [r for r in report.results if r.status == SmokeTestStatus.WARNING]

    if failed:
        pdf.ln(3)
        line("Failed Tests", bold=True, size=11)
        for r in failed:
            line(f"- {r.test_name}: {mask_text(r.message)}", size=9)
            line(f"  Expected: {r.expected}", size=9)
            line(f"  Actual: {mask_text(r.actual)}", size=9)

    if warnings:
        pdf.ln(2)
        line("Warnings", bold=True, size=11)
        for r in warnings:
            line(f"- {r.test_name}: {mask_text(r.message)}", size=9)

    pdf.ln(3)
    line("Request Summary", bold=True, size=11)
    if report.request:
        preview = mask_request_preview(report.request)
        line(f"Method: {preview.get('method')}", size=9)
        line(f"URL: {preview.get('url')}", size=9)
        headers = preview.get("headers") or {}
        for hk, hv in headers.items():
            line(f"Header {hk}: {hv}", size=9)
        body = preview.get("body")
        if body:
            line(f"Body: {str(body)[:1500]}", size=9)

    pdf.ln(2)
    line("Response Summary", bold=True, size=11)
    if report.exchange:
        ex = report.exchange
        line(f"Status: {ex.status_code} {ex.reason_phrase}", size=9)
        line(f"Response Time: {ex.elapsed_ms} ms", size=9)
        line(f"Final URL: {ex.final_url}", size=9)
        line(f"Redirects: {ex.redirect_count}", size=9)
        hdrs = mask_headers(dict(ex.response_headers))
        for hk, hv in list(hdrs.items())[:30]:
            line(f"Header {hk}: {hv}", size=9)
        body = mask_text(ex.response_body or "")[:2000]
        line(f"Body: {body or '(empty)'}", size=9)
        if ex.error:
            line(f"Error: {mask_text(ex.error)}", size=9)

    pdf.ln(2)
    line("Execution Details", bold=True, size=11)
    line(f"Config: {report.config_snapshot}", size=9)

    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))
    logger.info("ReportGenerated type=pdf path=%s", path)
    return path


def save_pdf_report(report: SmokeTestReport, directory: Path) -> Path:
    path = directory / "API-Smoke-Test-Report.pdf"
    return generate_pdf_report(report, path)


def _safe(text: str) -> str:
    """FPDF core fonts are latin-1; strip unsupported chars."""
    cleaned = str(text).replace("\t", " ").replace("\r", "")
    return cleaned.encode("latin-1", errors="replace").decode("latin-1")
