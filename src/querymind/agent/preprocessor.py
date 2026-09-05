"""Request pre-processor — handles common patterns without LLM.

Detects curl commands, PowerShell commands, URLs with auth, and simple requests
and processes them directly, saving tokens.
"""

from __future__ import annotations

import re
from typing import Any


def detect_request_type(user_input: str) -> dict[str, Any]:
    """Detect what type of request the user is making.

    Returns dict with:
    - type: "curl", "powershell", "simple_url", "other"
    - details: parsed components
    """
    text = user_input.strip()

    # Check for curl command
    if text.lower().startswith("curl ") or "curl -" in text.lower():
        return {"type": "curl", "details": text}

    # Check for PowerShell Invoke-WebRequest or Invoke-RestMethod
    if re.search(r"invoke-(?:webrequest|restmethod)", text, re.IGNORECASE):
        return {"type": "powershell", "details": text}

    # Check for URL with auth header
    url_match = re.search(r"(https?://[^\s\"'`]+)", text)
    if url_match:
        url = url_match.group(1)

        # Check for auth in the message
        has_auth = bool(re.search(
            r"(bearer|api.?key|authorization|token)",
            text,
            re.IGNORECASE,
        ))

        if has_auth:
            return {"type": "url_with_auth", "details": {"url": url, "full_text": text}}

        # Simple URL
        return {"type": "simple_url", "details": {"url": url}}

    return {"type": "other", "details": text}


def parse_powershell(text: str) -> dict[str, Any]:
    """Parse PowerShell Invoke-WebRequest command.

    Extracts URL, method, headers, and body from PowerShell syntax.
    """
    result: dict[str, Any] = {
        "url": "",
        "method": "GET",
        "headers": {},
        "body": None,
        "auth_type": "",
        "auth_value": "",
    }

    # Extract URL from -Uri parameter
    url_match = re.search(
        r'-Uri\s+["\']([^"\']+)["\']',
        text,
        re.IGNORECASE,
    )
    if url_match:
        result["url"] = url_match.group(1)

    # Detect method
    if re.search(r"-Method\s+(?:Post|Put|Patch|Delete)", text, re.IGNORECASE):
        method_match = re.search(r"-Method\s+(\w+)", text, re.IGNORECASE)
        if method_match:
            result["method"] = method_match.group(1).upper()

    # Check for -Body parameter (JSON body)
    body_match = re.search(
        r"-Body\s+['\"]({.+})['\"]",
        text,
        re.IGNORECASE,
    )
    if body_match:
        import json
        try:
            result["body"] = json.loads(body_match.group(1))
        except Exception:
            pass

    # Extract headers from -Headers @{...} block
    headers_match = re.search(
        r"-Headers\s+@\{([^}]+)\}",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if headers_match:
        headers_block = headers_match.group(1)
        # Parse each "Key" = "Value" line
        for line in headers_block.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Match "Key" = "Value" pattern
            kv_match = re.match(
                r'["\']?([^"\'=]+)["\']?\s*=\s*["\']([^"\']*)["\']',
                line,
            )
            if kv_match:
                key = kv_match.group(1).strip()
                value = kv_match.group(2).strip()
                result["headers"][key] = value

    # Extract auth from headers
    auth_header = result["headers"].get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        result["auth_type"] = "bearer"
        result["auth_value"] = auth_header[7:]
    elif auth_header.lower().startswith("basic "):
        result["auth_type"] = "basic"
        result["auth_value"] = auth_header[6:]

    # Extract method from -Method if not already set
    if result["method"] == "GET":
        if re.search(r"-Body\s+", text, re.IGNORECASE):
            result["method"] = "POST"

    return result


def parse_curl(text: str) -> dict[str, Any]:
    """Parse curl command into components."""
    result: dict[str, Any] = {
        "url": "",
        "method": "GET",
        "headers": {},
        "body": None,
        "auth_type": "",
        "auth_value": "",
    }

    # Remove line continuations
    text = text.replace("\\\n", " ").replace("\\\r\n", " ")

    # Extract URL (last argument or after -url)
    url_match = re.search(
        r'(?:curl\s+|(?<!\w)-[url]+\s+)(["\']?)(https?://[^\s"\']+)\1',
        text,
        re.IGNORECASE,
    )
    if url_match:
        result["url"] = url_match.group(2)
    else:
        # Try to find any URL
        url_match = re.search(r'(https?://[^\s"\']+)', text)
        if url_match:
            result["url"] = url_match.group(1)

    # Extract method
    method_match = re.search(r'-X\s+(\w+)', text, re.IGNORECASE)
    if method_match:
        result["method"] = method_match.group(1).upper()

    # Extract headers (-H or --header)
    header_pattern = re.compile(
        r'(?:-[Hh]|--header)\s+["\']([^"\':]+):\s*([^"\']+)["\']',
        re.IGNORECASE,
    )
    for match in header_pattern.finditer(text):
        key = match.group(1).strip()
        value = match.group(2).strip()
        result["headers"][key] = value

    # Extract auth
    auth = result["headers"].get("Authorization", "")
    if auth.lower().startswith("bearer "):
        result["auth_type"] = "bearer"
        result["auth_value"] = auth[7:]
    elif auth.lower().startswith("basic "):
        result["auth_type"] = "basic"
        result["auth_value"] = auth[6:]

    # Extract body (-d or --data)
    body_match = re.search(
        r'(?:-[Dd]|--data(?:-raw)?)\s+["\'](.+?)["\']',
        text,
        re.DOTALL,
    )
    if body_match:
        import json
        try:
            result["body"] = json.loads(body_match.group(1))
        except Exception:
            result["body"] = body_match.group(1)

    return result


def extract_auth_from_text(text: str) -> dict[str, str] | None:
    """Extract auth credentials from user text."""
    # Bearer token
    bearer_match = re.search(
        r"(?:Bearer|bearer)\s+([A-Za-z0-9._-]+)",
        text,
    )
    if bearer_match:
        return {"type": "bearer", "value": bearer_match.group(1)}

    # Token in various formats
    token_match = re.search(
        r"(?:token|api.?key|authorization)[=:]\s*['\"]?([A-Za-z0-9._-]+)['\"]?",
        text,
        re.IGNORECASE,
    )
    if token_match:
        return {"type": "bearer", "value": token_match.group(1)}

    return None
