"""CLI for running smoke tests without LLM."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from querymind.testing.models import ApiTestResult, TestStatus
from querymind.testing.smoke import SmokeTestConfig, run_smoke_tests

console = Console()


def print_results(results: list[ApiTestResult]) -> None:
    """Print smoke test results in a nice table."""
    if not results:
        console.print("[red]No results returned.[/red]")
        return

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r.status == TestStatus.PASSED)
    failed = sum(1 for r in results if r.status == TestStatus.FAILED)
    errors = sum(1 for r in results if r.status == TestStatus.ERROR)

    # Summary panel
    summary = Text()
    summary.append(f"Total: {total}  ", style="bold")
    summary.append(f"Passed: {passed}  ", style="green")
    summary.append(f"Failed: {failed}  ", style="red" if failed else "dim")
    summary.append(f"Errors: {errors}", style="yellow" if errors else "dim")

    console.print(Panel(summary, title="[bold]Smoke Test Results[/bold]", border_style="cyan"))

    # Results table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Test", style="cyan")
    table.add_column("Status")
    table.add_column("Time", justify="right")
    table.add_column("Code", justify="right")
    table.add_column("Details")

    for r in results:
        # Status icon
        if r.status == TestStatus.PASSED:
            status = "[green]✓ PASS[/green]"
        elif r.status == TestStatus.FAILED:
            status = "[red]✗ FAIL[/red]"
        else:
            status = "[yellow]⚠ ERROR[/yellow]"

        # Time
        time_str = f"{r.elapsed_ms}ms" if r.elapsed_ms else "N/A"

        # Status code
        code_str = str(r.response_status_code) if r.response_status_code else "N/A"

        # Details
        details = ""
        if r.error:
            details = r.error[:50]
        elif r.failed_count > 0:
            failed_assertions = [a for a in r.assertion_results if not a.passed]
            if failed_assertions:
                details = failed_assertions[0].message[:50]

        table.add_row(r.test_name, status, time_str, code_str, details)

    console.print(table)

    # Final verdict
    console.print()
    if failed == 0 and errors == 0:
        console.print("[bold green]✓ All smoke tests passed![/bold green]")
    else:
        console.print(f"[bold red]✗ {failed + errors} test(s) failed[/bold red]")


def smoke_command(
    url: str = typer.Argument(..., help="API base URL to smoke test"),
    openapi_url: str = typer.Option(None, "--openapi", "-o", help="OpenAPI spec URL"),
    timeout: int = typer.Option(5000, "--timeout", "-t", help="Max response time in ms"),
    include_write: bool = typer.Option(
        False, "--include-write", "-w", help="Include POST/PUT/DELETE tests"
    ),
    report: bool = typer.Option(False, "--report", "-r", help="Generate HTML report"),
) -> None:
    """Run smoke tests against an API (no LLM required)."""
    console.print()
    console.print(Panel(
        Text.from_markup(f"[bold]Smoke Testing:[/bold] {url}"),
        border_style="cyan",
    ))

    config = SmokeTestConfig(
        base_url=url,
        timeout_ms=timeout,
        include_write_tests=include_write,
    )

    console.print("[dim]Discovering endpoints and running tests...[/dim]\n")

    # Run smoke tests
    results = asyncio.run(run_smoke_tests(config))

    # Print results
    print_results(results)

    # Generate report if requested
    if report:
        from querymind.report.generator import ReportGenerator

        generator = ReportGenerator()
        html = generator.generate(
            results,  # pyright: ignore[reportUnknownArgumentType]
            title=f"Smoke Test Report — {url}",
            target=url,
        )
        path = generator.save(html)
        console.print(f"\n[dim]Report saved to: {path}[/dim]")

    console.print()


if __name__ == "__main__":
    typer.run(smoke_command)
