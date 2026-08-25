"""Parse cURL command strings into normalized ApiRequest models.

Never executes shell — tokenization only.
"""

from __future__ import annotations

import logging
import re
import shlex
from urllib.parse import parse_qsl, urlparse, urlunparse

from querymind.smoke.models import ApiRequest

logger = logging.getLogger(__name__)

_METHOD_FLAGS = {"-X", "--request"}
_HEADER_FLAGS = {"-H", "--header"}
_DATA_FLAGS = {"-d", "--data", "--data-raw", "--data-binary", "--data-ascii"}
_URL_FLAGS = {"--url"}
_LOCATION_FLAGS = {"-L", "--location"}
_FORM_FLAGS = {"-F", "--form"}
_COOKIE_FLAGS = {"-b", "--cookie"}
_USER_FLAGS = {"-u", "--user"}
_HEAD_FLAGS = {"-I", "--head"}


class CurlParseError(ValueError):
    """Raised when cURL cannot be parsed into a valid request."""


def parse_curl(curl_text: str) -> ApiRequest:
    """Convert a cURL command into an ApiRequest."""
    raw = curl_text.strip()
    if not raw:
        return ApiRequest(parse_errors=["Empty cURL input"], raw_curl=curl_text)

    # Normalize line continuations
    normalized = re.sub(r"\\\s*\n", " ", raw)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse newlines that are not escaped (already handled) into spaces for shlex
    normalized = " ".join(line.strip() for line in normalized.split("\n") if line.strip())

    errors: list[str] = []
    try:
        tokens = shlex.split(normalized, posix=True)
    except ValueError as e:
        return ApiRequest(
            parse_errors=[f"Unable to parse cURL: {e}"],
            raw_curl=curl_text,
        )

    if not tokens:
        return ApiRequest(parse_errors=["Empty cURL input"], raw_curl=curl_text)

    # Drop leading 'curl'
    if tokens[0].lower() == "curl":
        tokens = tokens[1:]

    method: str | None = None
    url: str | None = None
    headers: dict[str, str] = {}
    cookies: dict[str, str] = {}
    body_parts: list[str] = []
    follow_redirects = False
    authentication: dict[str, str] = {}
    content_type: str | None = None
    i = 0

    while i < len(tokens):
        tok = tokens[i]

        if tok in _LOCATION_FLAGS:
            follow_redirects = True
            i += 1
            continue

        if tok in _HEAD_FLAGS:
            method = "HEAD"
            i += 1
            continue

        if tok in _METHOD_FLAGS:
            if i + 1 >= len(tokens):
                errors.append(f"Flag {tok} requires a method argument")
                break
            method = tokens[i + 1].upper()
            i += 2
            continue

        if tok in _URL_FLAGS:
            if i + 1 >= len(tokens):
                errors.append(f"Flag {tok} requires a URL argument")
                break
            url = tokens[i + 1]
            i += 2
            continue

        if tok in _HEADER_FLAGS:
            if i + 1 >= len(tokens):
                errors.append(f"Flag {tok} requires a header argument")
                break
            name, value = _split_header(tokens[i + 1])
            if name:
                headers[name] = value
                if name.lower() == "content-type":
                    content_type = value
                if name.lower() == "authorization":
                    authentication["header"] = "Authorization"
                    authentication["scheme"] = value.split(" ", 1)[0] if value else ""
                if name.lower() in {"cookie"}:
                    cookies.update(_parse_cookie_string(value))
            i += 2
            continue

        if tok in _DATA_FLAGS or tok in _FORM_FLAGS:
            if i + 1 >= len(tokens):
                errors.append(f"Flag {tok} requires a data argument")
                break
            body_parts.append(tokens[i + 1])
            if method is None:
                method = "POST"
            if tok in _FORM_FLAGS and content_type is None:
                content_type = "multipart/form-data"
            elif content_type is None and "Content-Type" not in headers and "content-type" not in {
                k.lower() for k in headers
            }:
                content_type = "application/x-www-form-urlencoded"
                # Only set form-urlencoded if body looks like form; JSON detection below
            i += 2
            continue

        if tok in _COOKIE_FLAGS:
            if i + 1 >= len(tokens):
                errors.append(f"Flag {tok} requires a cookie argument")
                break
            cookies.update(_parse_cookie_string(tokens[i + 1]))
            i += 2
            continue

        if tok in _USER_FLAGS:
            if i + 1 >= len(tokens):
                errors.append(f"Flag {tok} requires user:password")
                break
            user_pass = tokens[i + 1]
            authentication["type"] = "basic"
            authentication["user"] = user_pass.split(":", 1)[0]
            # Do not store password in plaintext fields used for display —
            # still needed for execution; kept under authentication with masking later
            if ":" in user_pass:
                authentication["password"] = user_pass.split(":", 1)[1]
            import base64

            encoded = base64.b64encode(user_pass.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
            i += 2
            continue

        # Boolean / ignored flags with optional args we skip carefully
        if tok.startswith("-") and tok not in {"-"}:
            # Unknown flag: skip optional value if next token doesn't look like URL/flag
            if (
                i + 1 < len(tokens)
                and not tokens[i + 1].startswith("-")
                and "://" not in tokens[i + 1]
            ):
                # Could be flag with arg — skip both for safety on unknown flags
                # But if next is clearly a URL, treat as URL
                nxt = tokens[i + 1]
                if nxt.startswith("http://") or nxt.startswith("https://"):
                    url = nxt
                    i += 2
                    continue
                i += 2
                continue
            i += 1
            continue

        # Bare URL or positional
        if "://" in tok or tok.startswith("/") or tok.startswith("localhost"):
            url = tok
            i += 1
            continue

        # Unrecognized positional
        if url is None and not tok.startswith("-"):
            url = tok
        i += 1

    body = "\n".join(body_parts) if body_parts else None
    if body and content_type is None:
        stripped = body.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            content_type = "application/json"
            # Ensure Content-Type header if missing
            if not any(k.lower() == "content-type" for k in headers):
                headers["Content-Type"] = "application/json"
        else:
            content_type = "application/x-www-form-urlencoded"
            if not any(k.lower() == "content-type" for k in headers):
                headers["Content-Type"] = content_type

    if method is None:
        method = "GET"

    query_parameters: dict[str, str] = {}
    if url:
        parsed = urlparse(url)
        query_parameters = dict(parse_qsl(parsed.query, keep_blank_values=True))
        if not parsed.scheme:
            errors.append(f"Invalid URL scheme: {url}")
        if not parsed.netloc and parsed.scheme not in {"",}:
            # file:// etc.
            pass
        if parsed.scheme and not parsed.netloc:
            errors.append(f"Invalid URL: {url}")

    if not url:
        errors.append("URL could not be determined from cURL")

    if not method:
        errors.append("HTTP method could not be determined")

    req = ApiRequest(
        method=method.upper(),
        url=url or "",
        headers=headers,
        query_parameters=query_parameters,
        body=body,
        content_type=content_type,
        cookies=cookies,
        authentication=authentication,
        follow_redirects=follow_redirects or True,  # default follow for smoke
        parse_errors=errors,
        raw_curl=curl_text,
    )
    # Prefer explicit --location; still default follow_redirects True for smoke UX
    if not follow_redirects:
        req.follow_redirects = True

    logger.info(
        "CurlParsed method=%s url=%s headers=%d errors=%d",
        req.method,
        urlparse(req.url).netloc if req.url else "",
        len(req.headers),
        len(req.parse_errors),
    )
    return req


def _split_header(raw: str) -> tuple[str, str]:
    if ":" not in raw:
        return raw.strip(), ""
    name, value = raw.split(":", 1)
    return name.strip(), value.strip()


def _parse_cookie_string(raw: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            cookies[k.strip()] = v.strip()
        else:
            cookies[part] = ""
    return cookies


def build_url_with_query(request: ApiRequest) -> str:
    """Return request URL (query already embedded if parsed from URL)."""
    if not request.url:
        return ""
    if not request.query_parameters:
        return request.url
    parsed = urlparse(request.url)
    if parsed.query:
        return request.url
    from urllib.parse import urlencode

    query = urlencode(request.query_parameters)
    return urlunparse(parsed._replace(query=query))
