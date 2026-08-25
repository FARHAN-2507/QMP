"""Default smoke-test rule registry."""

from __future__ import annotations

from querymind.smoke.rules.authentication import AuthenticationRule, DestructiveSafetyRule
from querymind.smoke.rules.base import SmokeTestRule
from querymind.smoke.rules.content_type import ContentTypeRule
from querymind.smoke.rules.error_patterns import ErrorPatternRule
from querymind.smoke.rules.headers import ResponseHeadersRule, SecurityHeadersRule
from querymind.smoke.rules.https import HttpsRule, RedirectRule
from querymind.smoke.rules.json_validity import JsonValidityRule
from querymind.smoke.rules.parsing import RequestParsingRule, RequestValidationRule
from querymind.smoke.rules.reachability import ReachabilityRule
from querymind.smoke.rules.response_body import ResponseBodyRule
from querymind.smoke.rules.response_time import ResponseTimeRule
from querymind.smoke.rules.status import StatusCodeRule


def default_rules() -> list[SmokeTestRule]:
    """Return the built-in ordered rule set (extensible by appending)."""
    return [
        RequestParsingRule(),
        RequestValidationRule(),
        ReachabilityRule(),
        StatusCodeRule(),
        ResponseTimeRule(),
        ContentTypeRule(),
        JsonValidityRule(),
        ResponseBodyRule(),
        ErrorPatternRule(),
        ResponseHeadersRule(),
        SecurityHeadersRule(),
        HttpsRule(),
        RedirectRule(),
        AuthenticationRule(),
        DestructiveSafetyRule(),
    ]
