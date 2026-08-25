"""HTTP API for ApiSmokeTesting — binds the web dashboard."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from querymind.smoke.config import smoke_settings
from querymind.smoke.curl_parser import parse_curl
from querymind.smoke.engine import SmokeTestEngine
from querymind.smoke.masking import mask_request_preview, mask_text
from querymind.smoke.reporting.writer import SmokeReportWriter

logger = logging.getLogger(__name__)

router = APIRouter()

_RUN_ID_RE = re.compile(r"^API-Smoke-Test-[\w.\-]+$")


def reports_root() -> Path:
    root = Path("~/.querymind/smoke-reports").expanduser()
    root.mkdir(parents=True, exist_ok=True)
    return root


class ParseRequest(BaseModel):
    curl: str = Field(..., min_length=1, description="Raw cURL command text")


class ParseResponse(BaseModel):
    valid: bool
    destructive: bool
    endpoint: str
    preview: dict[str, Any]
    errors: list[str]


class RunRequest(BaseModel):
    curl: str = Field(..., min_length=1)
    confirm_destructive: bool = False
    output_label: str | None = Field(
        default=None,
        description="Optional label stored with the run (folder still auto-named).",
    )


class RunResponse(BaseModel):
    run_id: str
    overall_status: str
    health_score: int
    summary: dict[str, Any]
    endpoint: str
    results: list[dict[str, Any]]
    report_urls: dict[str, str]
    directory: str


@router.get("/health")
def smoke_health() -> dict[str, object]:
    return {
        "status": "ok",
        "module": "ApiSmokeTesting",
        "timeout_seconds": smoke_settings.timeout_seconds,
        "reports_root": str(reports_root()),
    }


@router.post("/parse", response_model=ParseResponse)
def parse_curl_endpoint(body: ParseRequest) -> ParseResponse:
    """Parse cURL into a masked request preview (no HTTP execution)."""
    request = parse_curl(body.curl)
    preview = mask_request_preview(request)
    return ParseResponse(
        valid=request.is_valid,
        destructive=request.is_destructive,
        endpoint=request.endpoint_label() if request.url else "",
        preview=preview,
        errors=list(request.parse_errors),
    )


@router.post("/run", response_model=RunResponse)
def run_smoke_endpoint(body: RunRequest) -> RunResponse:
    """Execute smoke tests once and persist HTML/PDF/JSON reports."""
    request = parse_curl(body.curl)
    if not request.url and request.parse_errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Unable to parse cURL. Please verify the request.",
                "errors": request.parse_errors,
            },
        )

    if request.is_destructive and not body.confirm_destructive:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    f"This API may modify data ({request.method}). "
                    "Set confirm_destructive=true to run once."
                ),
                "destructive": True,
                "method": request.method,
            },
        )

    logger.info("SmokeTestStarted via=api method=%s", request.method)
    engine = SmokeTestEngine()
    report = engine.run(request)
    writer = SmokeReportWriter()
    paths = writer.write(report, reports_root())
    run_id = paths["directory"].name

    results = [
        {
            "test_id": r.test_id,
            "test_name": r.test_name,
            "status": r.status.value,
            "severity": r.severity.value,
            "expected": r.expected,
            "actual": mask_text(r.actual),
            "message": mask_text(r.message),
            "duration_ms": r.duration_ms,
        }
        for r in report.results
    ]

    s = report.summary
    return RunResponse(
        run_id=run_id,
        overall_status=s.overall_status.value,
        health_score=s.health_score,
        summary={
            "total": s.total,
            "passed": s.passed,
            "failed": s.failed,
            "warnings": s.warnings,
            "skipped": s.skipped,
            "info": s.info,
            "duration_ms": s.duration_ms,
            "overall_status": s.overall_status.value,
            "health_score": s.health_score,
        },
        endpoint=report.endpoint,
        results=results,
        report_urls={
            "html": f"/api/smoke/reports/{run_id}/html",
            "pdf": f"/api/smoke/reports/{run_id}/pdf",
            "json": f"/api/smoke/reports/{run_id}/json",
        },
        directory=str(paths["directory"]),
    )


def _resolve_run_dir(run_id: str) -> Path:
    if not _RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=400, detail="Invalid run id")
    path = reports_root() / run_id
    if not path.is_dir():
        raise HTTPException(status_code=404, detail="Report run not found")
    return path


@router.get("/reports/{run_id}/html")
def get_html_report(run_id: str) -> FileResponse:
    path = _resolve_run_dir(run_id) / "API-Smoke-Test-Report.html"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="HTML report not found")
    return FileResponse(path, media_type="text/html", filename=path.name)


@router.get("/reports/{run_id}/pdf")
def get_pdf_report(run_id: str) -> FileResponse:
    path = _resolve_run_dir(run_id) / "API-Smoke-Test-Report.pdf"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="PDF report not found")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@router.get("/reports/{run_id}/json")
def get_json_report(run_id: str) -> FileResponse:
    path = _resolve_run_dir(run_id) / "test-results.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="JSON report not found")
    return FileResponse(path, media_type="application/json", filename=path.name)


@router.get("/reports")
def list_reports(limit: int = 20) -> dict[str, Any]:
    root = reports_root()
    runs = sorted(
        [p for p in root.iterdir() if p.is_dir() and p.name.startswith("API-Smoke-Test-")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[: max(1, min(limit, 100))]
    return {
        "reports_root": str(root),
        "runs": [
            {
                "run_id": p.name,
                "html": f"/api/smoke/reports/{p.name}/html",
                "pdf": f"/api/smoke/reports/{p.name}/pdf",
                "json": f"/api/smoke/reports/{p.name}/json",
            }
            for p in runs
        ],
    }
