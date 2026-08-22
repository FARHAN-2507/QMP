"""Tests for report generator and tool."""

import tempfile
from pathlib import Path

import pytest

from querymind.report.generator import ReportGenerator
from querymind.testing.models import (
    ApiTestResult,
    Assertion,
    AssertionResult,
    AssertionType,
    TestStatus,
)
from querymind.tools.report import GenerateReport


def _make_result(
    name: str,
    status: TestStatus = TestStatus.PASSED,
    status_code: int = 200,
    elapsed_ms: int = 100,
) -> ApiTestResult:
    """Helper to create test results."""
    assertions = [
        AssertionResult(
            assertion=Assertion(type=AssertionType.STATUS_CODE, expected=200),
            passed=status == TestStatus.PASSED,
            actual=status_code,
            message="" if status == TestStatus.PASSED else f"Expected 200, got {status_code}",
        ),
    ]
    return ApiTestResult(
        test_name=name,
        status=status,
        assertion_results=assertions,
        response_status_code=status_code,
        elapsed_ms=elapsed_ms,
    )


def test_report_generator_creates_html() -> None:
    gen = ReportGenerator()
    results = [_make_result("GET /api")]
    html = gen.generate(results, title="Test Report", target="http://localhost")
    assert "<!DOCTYPE html>" in html
    assert "Test Report" in html
    assert "http://localhost" in html


def test_report_generator_shows_passed() -> None:
    gen = ReportGenerator()
    results = [_make_result("GET /api", TestStatus.PASSED)]
    html = gen.generate(results)
    assert "1" in html  # 1 passed
    assert "Passed" in html


def test_report_generator_shows_failed() -> None:
    gen = ReportGenerator()
    results = [_make_result("GET /api", TestStatus.FAILED, status_code=404)]
    html = gen.generate(results)
    assert "Failed" in html
    assert "❌" in html


def test_report_generator_shows_error() -> None:
    gen = ReportGenerator()
    results = [ApiTestResult(
        test_name="GET /api",
        status=TestStatus.ERROR,
        error="Connection refused",
    )]
    html = gen.generate(results)
    assert "Errors" in html
    assert "⚠️" in html


def test_report_generator_multiple_results() -> None:
    gen = ReportGenerator()
    results = [
        _make_result("GET /api", TestStatus.PASSED),
        _make_result("POST /api", TestStatus.FAILED, status_code=500),
        _make_result("DELETE /api", TestStatus.PASSED),
    ]
    html = gen.generate(results)
    assert "3" in html  # total
    assert "2" in html  # passed
    assert "1" in html  # failed


def test_report_save_to_file() -> None:
    gen = ReportGenerator()
    results = [_make_result("GET /api")]
    html = gen.generate(results)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = gen.save(html, output_path=tmpdir, filename="test.html")
        assert path.exists()
        assert path.name == "test.html"
        content = path.read_text()
        assert "<!DOCTYPE html>" in content


def test_report_save_with_full_path() -> None:
    gen = ReportGenerator()
    results = [_make_result("GET /api")]
    html = gen.generate(results)

    with tempfile.TemporaryDirectory() as tmpdir:
        full_path = Path(tmpdir) / "report.html"
        path = gen.save(html, output_path=full_path)
        assert path.exists()
        assert path == full_path


def test_report_auto_generates_filename() -> None:
    gen = ReportGenerator()
    results = [_make_result("GET /api")]
    html = gen.generate(results)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = gen.save(html, output_path=tmpdir)
        assert path.exists()
        assert path.name.startswith("report_")
        assert path.name.endswith(".html")


def test_report_tool_properties() -> None:
    tool = GenerateReport()
    assert tool.name == "generate_report"
    assert "results" in tool.input_schema["properties"]


@pytest.mark.asyncio
async def test_report_tool_generates_report() -> None:
    tool = GenerateReport()
    results = [
        {"test_name": "GET /api", "status": "passed", "status_code": 200, "elapsed_ms": 50},
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        result = await tool.execute({
            "results": results,
            "title": "My Report",
            "output_path": tmpdir,
        })
        assert result.is_success
        assert "path" in result.data
        assert result.data["total_tests"] == 1
        assert result.data["passed"] == 1


@pytest.mark.asyncio
async def test_report_tool_empty_results() -> None:
    tool = GenerateReport()
    result = await tool.execute({"results": []})
    assert not result.is_success
    assert "No test results" in result.error
