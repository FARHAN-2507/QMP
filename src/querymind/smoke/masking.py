"""Sensitive value masking for UI, reports, and logs."""

from __future__ import annotations

import re
from typing import Any

from querymind.smoke.config import smoke_settings
from querymind.smoke.models import ApiRequest

DEFAULT_SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "api-key",
        "client-secret",
        "x-auth-token",
    }
)

_MASK = "********"
_BEARER_RE = re.compile(r"(?i)(bearer\s+)\S+")
_BASIC_RE = re.compile(r"(?i)(basic\s+)\S+")
_TOKEN_KV_RE = re.compile(
    r'(?i)((?:api[_-]?key|token|password|secret|client_secret)\s*[=:]\s*)([^\s&,;"]+)'
)


def sensitive_header_names() -> set[str]:
    configured = {h.lower() for h in smoke_settings.sensitive_header_list}
    return set(DEFAULT_SENSITIVE_HEADERS) | configured


def is_sensitive_header(name: str) -> bool:
    return name.lower() in sensitive_header_names()


def mask_header_value(name: str, value: str) -> str:
    if not is_sensitive_header(name):
        return value
    lower = value.lower().strip()
    if lower.startswith("bearer "):
        return f"Bearer {_MASK}"
    if lower.startswith("basic "):
        return f"Basic {_MASK}"
    if len(value) <= 8:
        return _MASK
    return value[:4] + _MASK


def mask_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k: mask_header_value(k, v) for k, v in headers.items()}


def mask_text(text: str) -> str:
    """Mask common secret patterns in free-form text."""
    if not text:
        return text
    out = _BEARER_RE.sub(rf"\1{_MASK}", text)
    out = _BASIC_RE.sub(rf"\1{_MASK}", out)
    out = _TOKEN_KV_RE.sub(rf"\1{_MASK}", out)
    return out


def mask_request_preview(request: ApiRequest) -> dict[str, Any]:
    """Build a UI/report-safe preview of the normalized request."""
    return {
        "method": request.method,
        "url": request.url,
        "headers": mask_headers(request.headers),
        "query_parameters": dict(request.query_parameters),
        "body": mask_text(request.body) if request.body else None,
        "content_type": request.content_type,
        "cookies": {k: _MASK for k in request.cookies},
        "follow_redirects": request.follow_redirects,
        "authentication": {k: _MASK for k in request.authentication},
    }


def safe_log_headers(headers: dict[str, str]) -> dict[str, str]:
    return mask_headers(headers)
