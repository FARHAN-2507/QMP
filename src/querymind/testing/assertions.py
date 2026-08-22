"""Assertion engine — evaluates test assertions against HTTP responses.

This is the deterministic core of QueryMind's testing. No AI involved
in evaluation — pure logic.
"""

from __future__ import annotations

from typing import Any

from querymind.testing.models import (
    Assertion,
    AssertionResult,
    AssertionType,
)


def evaluate_assertion(
    assertion: Assertion,
    status_code: int,
    headers: dict[str, str],
    body: Any,
    elapsed_ms: int,
) -> AssertionResult:
    """Evaluate a single assertion against a response.

    Returns an AssertionResult with passed=True/False and details.
    """
    evaluator = _EVALUATORS.get(assertion.type)
    if evaluator is None:
        return AssertionResult(
            assertion=assertion,
            passed=False,
            message=f"Unknown assertion type: {assertion.type}",
        )

    return evaluator(assertion, status_code, headers, body, elapsed_ms)


def _eval_status_code(
    assertion: Assertion, status_code: int, headers: dict[str, str],
    body: Any, elapsed_ms: int,
) -> AssertionResult:
    expected = assertion.expected
    passed = status_code == expected
    return AssertionResult(
        assertion=assertion,
        passed=passed,
        actual=status_code,
        message=f"Expected status {expected}, got {status_code}" if not passed else "",
    )


def _eval_status_code_range(
    assertion: Assertion, status_code: int, headers: dict[str, str],
    body: Any, elapsed_ms: int,
) -> AssertionResult:
    expected = assertion.expected  # e.g. [200, 299]
    if isinstance(expected, list) and len(expected) == 2:  # pyright: ignore[reportUnknownArgumentType]
        passed = expected[0] <= status_code <= expected[1]  # pyright: ignore[reportUnknownVariableType]
        msg = f"Expected status {expected[0]}-{expected[1]}, got {status_code}"
    else:
        passed = False
        msg = f"Invalid range format: {expected}"
    return AssertionResult(
        assertion=assertion, passed=passed, actual=status_code, message=msg if not passed else "",  # pyright: ignore[reportUnknownArgumentType]
    )


def _eval_header_exists(
    assertion: Assertion, status_code: int, headers: dict[str, str],
    body: Any, elapsed_ms: int,
) -> AssertionResult:
    header_name = str(assertion.expected).lower()
    passed = header_name in {k.lower() for k in headers}
    return AssertionResult(
        assertion=assertion, passed=passed,
        message=f"Header '{header_name}' not found" if not passed else "",
    )


def _eval_header_equals(
    assertion: Assertion, status_code: int, headers: dict[str, str],
    body: Any, elapsed_ms: int,
) -> AssertionResult:
    path = assertion.path or ""
    expected = assertion.expected
    actual = headers.get(path)
    passed = actual == expected
    return AssertionResult(
        assertion=assertion, passed=passed, actual=actual,
        message=f"Header '{path}': expected '{expected}', got '{actual}'" if not passed else "",
    )


def _eval_json_property_exists(
    assertion: Assertion, status_code: int, headers: dict[str, str],
    body: Any, elapsed_ms: int,
) -> AssertionResult:
    path = assertion.path or ""
    value = _get_json_path(body, path)
    passed = value is not _MISSING
    return AssertionResult(
        assertion=assertion, passed=passed,
        message=f"Property '{path}' not found" if not passed else "",
    )


def _eval_json_property_equals(
    assertion: Assertion, status_code: int, headers: dict[str, str],
    body: Any, elapsed_ms: int,
) -> AssertionResult:
    path = assertion.path or ""
    expected = assertion.expected
    value = _get_json_path(body, path)
    passed = value == expected
    return AssertionResult(
        assertion=assertion, passed=passed, actual=value,
        message=f"Property '{path}': expected {expected!r}, got {value!r}" if not passed else "",
    )


def _eval_json_property_type(
    assertion: Assertion, status_code: int, headers: dict[str, str],
    body: Any, elapsed_ms: int,
) -> AssertionResult:
    path = assertion.path or ""
    expected_type = str(assertion.expected)
    value = _get_json_path(body, path)
    if value is _MISSING:
        return AssertionResult(
            assertion=assertion, passed=False,
            message=f"Property '{path}' not found",
        )
    type_map = {
        "string": str, "integer": int, "number": (int, float),
        "boolean": bool, "list": list, "dict": dict,
    }
    expected_cls = type_map.get(expected_type)
    if expected_cls is None:
        return AssertionResult(
            assertion=assertion, passed=False,
            message=f"Unknown type: {expected_type}",
        )
    passed = isinstance(value, expected_cls)
    return AssertionResult(
        assertion=assertion, passed=passed, actual=type(value).__name__,
        message=f"Property '{path}': expected type {expected_type}, got {type(value).__name__}"
        if not passed else "",
    )


def _eval_json_schema(
    assertion: Assertion, status_code: int, headers: dict[str, str],
    body: Any, elapsed_ms: int,
) -> AssertionResult:
    schema = assertion.expected
    if not isinstance(schema, dict):
        return AssertionResult(
            assertion=assertion, passed=False, message="Schema must be a dict",
        )
    errors = _validate_schema(body, schema)  # pyright: ignore[reportUnknownArgumentType]
    passed = len(errors) == 0
    return AssertionResult(
        assertion=assertion, passed=passed, actual=body,
        message="; ".join(errors) if errors else "",
    )


def _eval_body_contains(
    assertion: Assertion, status_code: int, headers: dict[str, str],
    body: Any, elapsed_ms: int,
) -> AssertionResult:
    expected = str(assertion.expected)
    body_str = str(body)
    passed = expected in body_str
    return AssertionResult(
        assertion=assertion, passed=passed,
        message=f"Body does not contain '{expected}'" if not passed else "",
    )


def _eval_response_time_ms(
    assertion: Assertion, status_code: int, headers: dict[str, str],
    body: Any, elapsed_ms: int,
) -> AssertionResult:
    max_ms = int(assertion.expected)
    passed = elapsed_ms <= max_ms
    return AssertionResult(
        assertion=assertion, passed=passed, actual=elapsed_ms,
        message=f"Response took {elapsed_ms}ms, expected <= {max_ms}ms" if not passed else "",
    )


def _eval_body_not_empty(
    assertion: Assertion, status_code: int, headers: dict[str, str],
    body: Any, elapsed_ms: int,
) -> AssertionResult:
    passed = body is not None and body != "" and body != {}
    return AssertionResult(
        assertion=assertion, passed=passed,
        message="Response body is empty" if not passed else "",
    )


_EVALUATORS = {
    AssertionType.STATUS_CODE: _eval_status_code,
    AssertionType.STATUS_CODE_RANGE: _eval_status_code_range,
    AssertionType.HEADER_EXISTS: _eval_header_exists,
    AssertionType.HEADER_EQUALS: _eval_header_equals,
    AssertionType.JSON_PROPERTY_EXISTS: _eval_json_property_exists,
    AssertionType.JSON_PROPERTY_EQUALS: _eval_json_property_equals,
    AssertionType.JSON_PROPERTY_TYPE: _eval_json_property_type,
    AssertionType.JSON_SCHEMA: _eval_json_schema,
    AssertionType.BODY_CONTAINS: _eval_body_contains,
    AssertionType.RESPONSE_TIME_MS: _eval_response_time_ms,
    AssertionType.BODY_NOT_EMPTY: _eval_body_not_empty,
}


# Sentinel for missing values
_MISSING = object()


def _get_json_path(data: Any, path: str) -> Any:
    """Navigate a JSON structure using dot notation.

    Example: "user.name" → data["user"]["name"]
    """
    if not path:
        return data

    parts = path.split(".")
    current = data  # pyright: ignore[reportUnknownVariableType]
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]  # pyright: ignore[reportUnknownVariableType]
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            if idx < len(current):  # pyright: ignore[reportUnknownArgumentType]
                current = current[idx]  # pyright: ignore[reportUnknownVariableType]
            else:
                return _MISSING
        else:
            return _MISSING
    return current  # pyright: ignore[reportUnknownVariableType]


def _validate_schema(data: Any, schema: dict[str, Any]) -> list[str]:
    """Basic JSON Schema validation (subset)."""
    errors: list[str] = []

    schema_type = schema.get("type")
    if schema_type:
        type_map = {
            "string": str, "integer": int, "number": (int, float),
            "boolean": bool, "array": list, "object": dict,
        }
        expected_cls = type_map.get(schema_type)
        if expected_cls and not isinstance(data, expected_cls):
            errors.append(f"Expected type {schema_type}, got {type(data).__name__}")

    if "properties" in schema and isinstance(data, dict):
        for prop_name, prop_schema in schema["properties"].items():
            if prop_name in data:
                errors.extend(_validate_schema(data[prop_name], prop_schema))
            elif schema.get("required") and prop_name in schema.get("required", []):
                errors.append(f"Missing required property: {prop_name}")

    return errors
