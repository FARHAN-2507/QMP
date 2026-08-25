"""Single-shot HTTP executor for ApiSmokeTesting.

Uses httpx with SSL verification enabled. Executes exactly one request per call.
"""

from __future__ import annotations

import logging
import socket
import time
from urllib.parse import urlparse

import httpx

from querymind.smoke.config import SmokeSettings, smoke_settings
from querymind.smoke.curl_parser import build_url_with_query
from querymind.smoke.masking import safe_log_headers
from querymind.smoke.models import ApiRequest, HttpExchange

logger = logging.getLogger(__name__)


class SmokeHttpExecutor:
    """Execute a normalized ApiRequest exactly once."""

    def __init__(self, settings: SmokeSettings | None = None) -> None:
        self._settings = settings or smoke_settings
        self._execution_count = 0

    @property
    def execution_count(self) -> int:
        return self._execution_count

    def execute(self, request: ApiRequest) -> HttpExchange:
        """Perform one HTTP request and capture diagnostics."""
        self._execution_count += 1
        url = build_url_with_query(request)
        exchange = HttpExchange(
            request=request,
            original_url=url,
            final_url=url,
        )

        if not url:
            exchange.error = "No URL to execute"
            return exchange

        host = urlparse(url).hostname
        if host:
            try:
                socket.getaddrinfo(host, None)
                exchange.dns_ok = True
            except OSError as e:
                exchange.error = f"DNS resolution failed for {host}: {e}"
                logger.info("ApiRequestStarted url_host=%s dns=fail", host)
                return exchange

        headers = dict(request.headers)
        if request.cookies and not any(k.lower() == "cookie" for k in headers):
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in request.cookies.items())

        logger.info(
            "ApiRequestStarted method=%s host=%s headers=%s",
            request.method,
            host,
            safe_log_headers(headers),
        )

        timeout = self._settings.timeout_seconds
        content: str | bytes | None = request.body
        try:
            start = time.monotonic()
            with httpx.Client(
                timeout=timeout,
                follow_redirects=request.follow_redirects,
                verify=True,
            ) as client:
                response = client.request(
                    method=request.method.upper(),
                    url=url,
                    headers=headers,
                    content=content.encode("utf-8") if isinstance(content, str) else content,
                )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            exchange.connected = True
            exchange.executed = True
            exchange.status_code = response.status_code
            exchange.reason_phrase = response.reason_phrase or ""
            exchange.response_headers = {k: v for k, v in response.headers.items()}
            exchange.response_body = response.text
            exchange.elapsed_ms = elapsed_ms
            exchange.final_url = str(response.url)
            exchange.redirect_history = [str(r.url) for r in response.history]
            exchange.redirect_count = len(response.history)

            logger.info(
                "ApiRequestCompleted status=%s elapsed_ms=%s redirects=%s",
                exchange.status_code,
                exchange.elapsed_ms,
                exchange.redirect_count,
            )
        except httpx.TimeoutException:
            exchange.error = f"Request timed out after {timeout} seconds"
            exchange.connected = exchange.dns_ok
            logger.info("ApiRequestCompleted error=timeout")
        except httpx.ConnectError as e:
            exchange.error = f"API could not be reached: {e}"
            exchange.dns_ok = exchange.dns_ok
            logger.info("ApiRequestCompleted error=connect")
        except httpx.HTTPError as e:
            exchange.error = f"HTTP error: {e}"
            logger.info("ApiRequestCompleted error=http")
        except OSError as e:
            # SSL and socket errors
            msg = str(e)
            if "CERTIFICATE" in msg.upper() or "SSL" in msg.upper():
                exchange.error = f"Invalid SSL certificate: {e}"
            else:
                exchange.error = f"Connection error: {e}"
            logger.info("ApiRequestCompleted error=os")

        return exchange
