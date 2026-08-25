"""Timestamped output writer for smoke reports."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from querymind.smoke.masking import mask_headers, mask_request_preview, mask_text
from querymind.smoke.models import SmokeTestReport

logger = logging.getLogger(__name__)


def sanitize_endpoint_slug(endpoint: str, max_len: int = 60) -> str:
    """Turn 'POST /api/users' into 'POST-api-users'."""
    slug = endpoint.strip().replace(" ", "-")
    slug = re.sub(r"[^\w\-]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return (slug or "request")[:max_len]


def build_run_directory(output_folder: Path | str, report: SmokeTestReport) -> Path:
    """Create a unique non-overwriting run directory under output_folder."""
    base = Path(output_folder).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    slug = sanitize_endpoint_slug(report.endpoint)
    method = report.request.method.upper() if report.request else ""
    name = f"API-Smoke-Test-{method}-{slug}-{stamp}" if method else f"API-Smoke-Test-{slug}-{stamp}"
    path = base / name
    counter = 1
    while path.exists():
        path = base / f"{name}-{counter}"
        counter += 1
    path.mkdir(parents=True, exist_ok=False)
    return path


def report_basenames(report: SmokeTestReport) -> tuple[str, str]:
    stamp = report.generated_at.strftime("%Y%m%d-%H%M%S")
    slug = sanitize_endpoint_slug(report.endpoint)
    method = report.request.method.upper() if report.request else "REQ"
    base = f"API-Smoke-Test-{method}-{slug}-{stamp}"
    return f"{base}.html", f"{base}.pdf"


def write_json_results(report: SmokeTestReport, path: Path) -> Path:
    """Write machine-readable results with secrets masked."""
    payload = _masked_report_dict(report)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    logger.info("ReportGenerated type=json path=%s", path)
    return path


def _masked_report_dict(report: SmokeTestReport) -> dict[str, object]:
    data = report.model_dump(mode="json")
    if report.request:
        data["request"] = mask_request_preview(report.request)
        data["request"]["raw_curl"] = mask_text(report.request.raw_curl)
    if report.exchange:
        exch = data.get("exchange")
        if isinstance(exch, dict):
            exch["response_headers"] = mask_headers(
                {k: str(v) for k, v in (report.exchange.response_headers or {}).items()}
            )
            exch["response_body"] = mask_text(report.exchange.response_body or "")
            if "request" in exch and report.request:
                exch["request"] = mask_request_preview(report.request)
    return data


class SmokeReportWriter:
    """Persist HTML, PDF, and JSON into a unique run folder."""

    def write(self, report: SmokeTestReport, output_folder: Path | str) -> dict[str, Path]:
        from querymind.smoke.reporting.html import save_html_report
        from querymind.smoke.reporting.pdf import save_pdf_report

        run_dir = build_run_directory(output_folder, report)
        html_path = save_html_report(report, run_dir)
        pdf_path = save_pdf_report(report, run_dir)
        json_path = write_json_results(report, run_dir / "test-results.json")
        logger.info("ReportGenerated dir=%s", run_dir)
        return {
            "directory": run_dir,
            "html": html_path,
            "pdf": pdf_path,
            "json": json_path,
        }
