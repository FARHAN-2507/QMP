"""Generate report tool — lets the agent create HTML test reports.

The agent calls this tool after running tests to generate
a self-contained HTML report file.
"""

from __future__ import annotations

from typing import Any

from querymind.report.generator import ReportGenerator
from querymind.testing.models import ApiTestResult, TestStatus
from querymind.tools.base import Tool, ToolResult, ToolStatus


class GenerateReport(Tool):
    """Generate an HTML test report from test results."""

    @property
    def name(self) -> str:
        return "generate_report"

    @property
    def description(self) -> str:
        return (
            "Generate a self-contained HTML test report from test results. "
            "Provide the test results from run_test or generate_tests. "
            "Saves to a file and returns the path."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "description": "List of test result objects",
                },
                "title": {
                    "type": "string",
                    "description": "Report title (default: 'API Test Report')",
                },
                "target": {
                    "type": "string",
                    "description": "API URL that was tested",
                },
                "output_path": {
                    "type": "string",
                    "description": (
                        "Full path to save HTML file. "
                        "Can be a file path or directory. "
                        "Default: ~/Downloads/report_TIMESTAMP.html"
                    ),
                },
            },
            "required": ["results"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        try:
            raw_results = arguments.get("results", [])
            title = arguments.get("title", "API Test Report")
            target = arguments.get("target", "")
            output_path = arguments.get("output_path")

            # Convert raw dicts to ApiTestResult objects
            results = self._parse_results(raw_results)

            if not results:
                return ToolResult(
                    status=ToolStatus.VALIDATION_ERROR,
                    error="No test results provided",
                )

            # Generate HTML
            generator = ReportGenerator()
            html = generator.generate(results, title=title, target=target)

            # Save to file
            path = generator.save(html, output_path=output_path)

            return ToolResult(
                status=ToolStatus.SUCCESS,
                data={
                    "path": str(path),
                    "title": title,
                    "total_tests": len(results),
                    "passed": sum(1 for r in results if r.status == TestStatus.PASSED),
                    "failed": sum(1 for r in results if r.status == TestStatus.FAILED),
                    "errors": sum(1 for r in results if r.status == TestStatus.ERROR),
                },
                metadata={"output_path": str(path)},
            )

        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Report generation failed: {e}",
            )

    def _parse_results(self, raw_results: list[Any]) -> list[ApiTestResult]:
        """Convert raw dicts to ApiTestResult objects."""
        results: list[ApiTestResult] = []
        for item in raw_results:
            if isinstance(item, ApiTestResult):
                results.append(item)
            elif isinstance(item, dict):
                try:
                    results.append(ApiTestResult(**item))  # pyright: ignore[reportUnknownArgumentType]
                except Exception:
                    # Try to build from partial data
                    try:
                        data: dict[str, Any] = item  # pyright: ignore[reportUnknownVariableType]
                        status_str = str(data.get("status", "passed"))
                        status = TestStatus(status_str)
                        test_name = str(data.get("test_name", "Unknown"))
                        status_code = data.get("status_code")
                        elapsed_ms = int(data.get("elapsed_ms", 0))
                        error_msg = data.get("error")
                        results.append(ApiTestResult(
                            test_name=test_name,
                            status=status,
                            response_status_code=(
                                status_code if isinstance(status_code, int) else None
                            ),
                            elapsed_ms=elapsed_ms,
                            error=error_msg if isinstance(error_msg, str) else None,
                        ))
                    except Exception:
                        continue
        return results
