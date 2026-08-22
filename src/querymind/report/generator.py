"""Report generator — creates HTML test reports from results.

Generates self-contained HTML files with inline CSS.
No external dependencies required.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from querymind.config.settings import settings
from querymind.testing.models import ApiTestResult, TestStatus

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate HTML test reports."""

    def generate(
        self,
        results: list[ApiTestResult],
        title: str = "API Test Report",
        target: str = "",
    ) -> str:
        """Generate a self-contained HTML report."""
        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        total = len(results)
        passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestStatus.FAILED)
        errors = sum(1 for r in results if r.status == TestStatus.ERROR)
        total_time = sum(r.elapsed_ms for r in results)

        # Build test rows
        test_rows = "\n".join(self._build_test_row(r) for r in results)

        return _HTML_TEMPLATE.format(
            title=_escape(title),
            target=_escape(target) if target else "N/A",
            date=now,
            total=total,
            passed=passed,
            failed=failed,
            errors=errors,
            total_time=total_time,
            test_rows=test_rows,
        )

    def save(
        self,
        html: str,
        output_path: Path | str | None = None,
        filename: str | None = None,
    ) -> Path:
        """Save HTML report to file. Returns saved path."""
        if output_path:
            path = Path(output_path)
            if path.is_dir():
                # It's a directory, generate filename
                if filename is None:
                    filename = self._default_filename()
                path = path / filename
        else:
            # Use default directory
            output_dir = Path(settings.report_output_dir).expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            if filename is None:
                filename = self._default_filename()
            path = output_dir / filename

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        logger.info("Report saved to %s", path)
        return path

    def _build_test_row(self, result: ApiTestResult) -> str:
        """Build HTML for a single test result."""
        status_class = result.status.value
        status_icon = {
            TestStatus.PASSED: "✅",
            TestStatus.FAILED: "❌",
            TestStatus.ERROR: "⚠️",
        }.get(result.status, "❓")

        status_code = str(result.response_status_code) if result.response_status_code else "N/A"
        time_str = f"{result.elapsed_ms}ms" if result.elapsed_ms else "N/A"

        # Build assertion details
        assertion_html = ""
        for ar in result.assertion_results:
            check = "✓" if ar.passed else "✗"
            css = "pass" if ar.passed else "fail"
            desc = ar.assertion.description or ar.assertion.type.value
            msg = f" — {ar.message}" if ar.message else ""
            assertion_html += f'<li class="{css}">{check} {_escape(desc)}{msg}</li>\n'

        # Error message if present
        error_html = ""
        if result.error:
            error_html = f'<div class="error-msg">Error: {_escape(result.error)}</div>'

        return _TEST_ROW_TEMPLATE.format(
            status_class=status_class,
            status_icon=status_icon,
            test_name=_escape(result.test_name),
            status_code=status_code,
            time_str=time_str,
            assertion_html=assertion_html,
            error_html=error_html,
        )

    def _default_filename(self) -> str:
        """Generate a default filename with timestamp."""
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        return f"report_{ts}.html"


def _escape(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


# HTML Template — self-contained with inline CSS
# ruff: noqa: E501
_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; padding: 20px; }}
.container {{ max-width: 900px; margin: 0 auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden; }}
header {{ background: #2c3e50; color: #fff; padding: 20px 30px; }}
header h1 {{ font-size: 1.5em; margin-bottom: 5px; }}
header p {{ opacity: 0.8; font-size: 0.9em; }}
.summary {{ display: flex; gap: 15px; padding: 20px 30px; background: #fafafa; border-bottom: 1px solid #eee; flex-wrap: wrap; }}
.stat {{ padding: 15px 20px; border-radius: 6px; text-align: center; min-width: 100px; }}
.stat .number {{ font-size: 1.8em; font-weight: bold; }}
.stat .label {{ font-size: 0.8em; opacity: 0.7; }}
.stat.total {{ background: #ecf0f1; color: #2c3e50; }}
.stat.passed {{ background: #d4edda; color: #155724; }}
.stat.failed {{ background: #f8d7da; color: #721c24; }}
.stat.errors {{ background: #fff3cd; color: #856404; }}
.stat.time {{ background: #d1ecf1; color: #0c5460; }}
.results {{ padding: 20px 30px; }}
.results h2 {{ margin-bottom: 15px; font-size: 1.2em; color: #2c3e50; }}
.test {{ border: 1px solid #ddd; border-radius: 6px; margin-bottom: 12px; overflow: hidden; }}
.test-header {{ padding: 12px 15px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; }}
.test-header:hover {{ background: #f8f9fa; }}
.test.passed .test-header {{ border-left: 4px solid #28a745; }}
.test.failed .test-header {{ border-left: 4px solid #dc3545; }}
.test.error .test-header {{ border-left: 4px solid #ffc107; }}
.test-name {{ font-weight: 600; }}
.test-meta {{ font-size: 0.85em; color: #666; }}
.test-details {{ padding: 0 15px 15px; display: none; }}
.test.open .test-details {{ display: block; }}
.test-details ul {{ list-style: none; padding: 0; }}
.test-details li {{ padding: 4px 0; font-size: 0.9em; }}
.test-details li.pass {{ color: #28a745; }}
.test-details li.fail {{ color: #dc3545; }}
.error-msg {{ background: #fff3cd; color: #856404; padding: 8px 12px; border-radius: 4px; margin-top: 8px; font-size: 0.9em; }}
footer {{ text-align: center; padding: 15px; color: #999; font-size: 0.8em; border-top: 1px solid #eee; }}
</style>
</head>
<body>
<div class="container">
<header>
<h1>{title}</h1>
<p>Target: {target}</p>
<p>Date: {date}</p>
</header>
<div class="summary">
<div class="stat total"><div class="number">{total}</div><div class="label">Total</div></div>
<div class="stat passed"><div class="number">{passed}</div><div class="label">Passed</div></div>
<div class="stat failed"><div class="number">{failed}</div><div class="label">Failed</div></div>
<div class="stat errors"><div class="number">{errors}</div><div class="label">Errors</div></div>
<div class="stat time"><div class="number">{total_time}ms</div><div class="label">Duration</div></div>
</div>
<div class="results">
<h2>Test Results</h2>
{test_rows}
</div>
<footer>Generated by QueryMind</footer>
</div>
<script>
document.querySelectorAll('.test-header').forEach(h => {{
  h.addEventListener('click', () => h.parentElement.classList.toggle('open'));
}});
</script>
</body>
</html>
"""

_TEST_ROW_TEMPLATE = """\
<div class="test {status_class}">
<div class="test-header">
<span class="test-name">{status_icon} {test_name}</span>
<span class="test-meta">Status: {status_code} | Time: {time_str}</span>
</div>
<div class="test-details">
<ul>
{assertion_html}
</ul>
{error_html}
</div>
</div>
"""
