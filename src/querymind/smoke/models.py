"""Domain models for ApiSmokeTesting."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SmokeTestStatus(StrEnum):
    """Outcome of a single smoke rule."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"
    INFO = "INFO"


class Severity(StrEnum):
    """Severity classification for a smoke result."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class OverallStatus(StrEnum):
    """Aggregate run status."""

    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS WITH WARNINGS"
    FAIL = "FAIL"


class ApiRequest(BaseModel):
    """Normalized HTTP request derived from a cURL command."""

    method: str = "GET"
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    query_parameters: dict[str, str] = Field(default_factory=dict)
    body: str | None = None
    content_type: str | None = None
    cookies: dict[str, str] = Field(default_factory=dict)
    authentication: dict[str, str] = Field(default_factory=dict)
    follow_redirects: bool = True
    parse_errors: list[str] = Field(default_factory=list)
    raw_curl: str = ""

    @property
    def is_valid(self) -> bool:
        return bool(self.url) and bool(self.method) and not self.parse_errors

    @property
    def is_destructive(self) -> bool:
        return self.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}

    def endpoint_label(self) -> str:
        """Short label for reports, e.g. POST /api/users."""
        from urllib.parse import urlparse

        path = urlparse(self.url).path or "/"
        return f"{self.method.upper()} {path}"


class HttpExchange(BaseModel):
    """Captured request/response from a single HTTP execution."""

    request: ApiRequest
    status_code: int | None = None
    reason_phrase: str = ""
    response_headers: dict[str, str] = Field(default_factory=dict)
    response_body: str = ""
    elapsed_ms: int = 0
    error: str | None = None
    dns_ok: bool = False
    connected: bool = False
    redirect_count: int = 0
    original_url: str = ""
    final_url: str = ""
    redirect_history: list[str] = Field(default_factory=list)
    executed: bool = False


class SmokeTestResult(BaseModel):
    """Result of one smoke-test rule."""

    test_id: str
    test_name: str
    category: str = "generic"
    status: SmokeTestStatus
    severity: Severity = Severity.MEDIUM
    expected: str = ""
    actual: str = ""
    message: str = ""
    duration_ms: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, Any] = Field(default_factory=dict)


class ReportSummary(BaseModel):
    """Aggregate counters for a smoke run."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    skipped: int = 0
    info: int = 0
    duration_ms: int = 0
    overall_status: OverallStatus = OverallStatus.PASS
    health_score: int = 0


class SmokeTestReport(BaseModel):
    """Full smoke-test report payload."""

    title: str = "API Smoke Test Report"
    endpoint: str = ""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request: ApiRequest | None = None
    exchange: HttpExchange | None = None
    results: list[SmokeTestResult] = Field(default_factory=list)
    summary: ReportSummary = Field(default_factory=ReportSummary)
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
