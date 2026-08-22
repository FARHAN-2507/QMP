"""Test engine models — structured representations of test cases and results.

The test engine is deterministic: AI generates or selects tests,
but the engine executes and evaluates them. No guessing.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AssertionType(StrEnum):
    """Types of assertions the engine supports."""

    STATUS_CODE = "status_code"
    STATUS_CODE_RANGE = "status_code_range"
    HEADER_EXISTS = "header_exists"
    HEADER_EQUALS = "header_equals"
    JSON_PROPERTY_EXISTS = "json_property_exists"
    JSON_PROPERTY_EQUALS = "json_property_equals"
    JSON_PROPERTY_TYPE = "json_property_type"
    JSON_SCHEMA = "json_schema"
    BODY_CONTAINS = "body_contains"
    RESPONSE_TIME_MS = "response_time_ms"
    BODY_NOT_EMPTY = "body_not_empty"


class Assertion(BaseModel):
    """A single assertion to evaluate against a response."""

    type: AssertionType
    expected: Any = None
    path: str | None = None  # JSON path for property assertions
    description: str = ""


class ApiTestRequest(BaseModel):
    """HTTP request definition for a test case."""

    method: str = "GET"
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict[str, Any] | None = None
    timeout: int = 30


class ApiTestCase(BaseModel):
    """A complete test case with request and expected assertions."""

    name: str
    description: str = ""
    request: ApiTestRequest
    assertions: list[Assertion] = Field(default_factory=list)  # pyright: ignore[reportUnknownVariableType]


class AssertionResult(BaseModel):
    """Result of evaluating a single assertion."""

    assertion: Assertion
    passed: bool
    actual: Any = None
    message: str = ""


class TestStatus(StrEnum):
    """Overall test result status."""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class ApiTestResult(BaseModel):
    """Complete result of running a test case."""

    test_name: str
    status: TestStatus
    assertion_results: list[AssertionResult] = Field(default_factory=list)  # pyright: ignore[reportUnknownVariableType]
    response_status_code: int | None = None
    response_headers: dict[str, str] = Field(default_factory=dict)
    response_body: Any = None
    elapsed_ms: int = 0
    error: str | None = None

    @property
    def passed_count(self) -> int:
        return sum(1 for a in self.assertion_results if a.passed)

    @property
    def failed_count(self) -> int:
        return sum(1 for a in self.assertion_results if not a.passed)

    def summary(self) -> str:
        """Human-readable summary."""
        if self.status == TestStatus.ERROR:
            return f"ERROR: {self.error}"
        failed = [a for a in self.assertion_results if not a.passed]
        if not failed:
            return f"PASSED ({self.passed_count} assertions)"
        lines = [f"FAILED ({self.failed_count} of {len(self.assertion_results)} assertions):"]
        for a in failed:
            lines.append(f"  - {a.assertion.description or a.assertion.type}: {a.message}")
        return "\n".join(lines)
