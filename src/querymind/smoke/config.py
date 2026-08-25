"""Configuration for ApiSmokeTesting (isolated from agent settings)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class SmokeSettings(BaseSettings):
    """Smoke-test thresholds and feature toggles.

    Loaded from environment / .env with QUERYMIND_SMOKE_ prefix where applicable,
    plus nested-friendly flat aliases.
    """

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    timeout_seconds: int = Field(default=30, alias="QUERYMIND_SMOKE_TIMEOUT_SECONDS")
    response_time_warning_ms: int = Field(
        default=500, alias="QUERYMIND_SMOKE_RESPONSE_TIME_WARNING_MS"
    )
    response_time_failure_ms: int = Field(
        default=1000, alias="QUERYMIND_SMOKE_RESPONSE_TIME_FAILURE_MS"
    )
    expected_status_codes: str = Field(
        default="200,201,202,204",
        alias="QUERYMIND_SMOKE_EXPECTED_STATUS_CODES",
    )
    enable_security_header_checks: bool = Field(
        default=True, alias="QUERYMIND_SMOKE_ENABLE_SECURITY_HEADERS"
    )
    enable_https_check: bool = Field(default=True, alias="QUERYMIND_SMOKE_ENABLE_HTTPS_CHECK")
    enable_error_pattern_detection: bool = Field(
        default=True, alias="QUERYMIND_SMOKE_ENABLE_ERROR_PATTERNS"
    )
    sensitive_headers: str = Field(
        default=(
            "Authorization,Proxy-Authorization,Cookie,Set-Cookie,"
            "X-API-Key,Api-Key,Client-Secret,X-Auth-Token"
        ),
        alias="QUERYMIND_SMOKE_SENSITIVE_HEADERS",
    )
    health_pass_weight: int = Field(default=100, alias="QUERYMIND_SMOKE_HEALTH_PASS_WEIGHT")
    health_warning_weight: int = Field(default=70, alias="QUERYMIND_SMOKE_HEALTH_WARNING_WEIGHT")
    health_fail_weight: int = Field(default=0, alias="QUERYMIND_SMOKE_HEALTH_FAIL_WEIGHT")
    health_skip_weight: int = Field(default=50, alias="QUERYMIND_SMOKE_HEALTH_SKIP_WEIGHT")
    health_info_weight: int = Field(default=100, alias="QUERYMIND_SMOKE_HEALTH_INFO_WEIGHT")

    @property
    def expected_status_code_list(self) -> list[int]:
        codes: list[int] = []
        for part in self.expected_status_codes.split(","):
            part = part.strip()
            if part.isdigit():
                codes.append(int(part))
        return codes or [200, 201, 202, 204]

    @property
    def sensitive_header_list(self) -> list[str]:
        return [h.strip() for h in self.sensitive_headers.split(",") if h.strip()]

    def snapshot(self) -> dict[str, object]:
        return {
            "timeout_seconds": self.timeout_seconds,
            "response_time_warning_ms": self.response_time_warning_ms,
            "response_time_failure_ms": self.response_time_failure_ms,
            "expected_status_codes": self.expected_status_code_list,
            "enable_security_header_checks": self.enable_security_header_checks,
            "enable_https_check": self.enable_https_check,
            "enable_error_pattern_detection": self.enable_error_pattern_detection,
        }


smoke_settings = SmokeSettings()
