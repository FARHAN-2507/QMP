"""Rich interactive dashboard for ApiSmokeTesting."""

from __future__ import annotations

import logging
import platform
import subprocess
import webbrowser
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from querymind.smoke.curl_parser import parse_curl
from querymind.smoke.engine import SmokeTestEngine
from querymind.smoke.masking import mask_request_preview
from querymind.smoke.models import ApiRequest, OverallStatus, SmokeTestReport, SmokeTestStatus
from querymind.smoke.reporting.writer import SmokeReportWriter

logger = logging.getLogger(__name__)
console = Console()

BANNER = """\
[bold cyan]API SMOKE TEST AUTOMATION[/bold cyan]
[dim]Generic API Health & Smoke Verification[/dim]"""


def select_output_folder(initial: str | None = None) -> Path | None:
    """Open a native folder picker dialog. Returns None if cancelled."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(
            title="Select Output Folder for Smoke Reports",
            initialdir=initial or str(Path.home()),
        )
        root.destroy()
        if not path:
            return None
        return Path(path)
    except Exception as e:
        console.print(f"[yellow]Native folder dialog unavailable ({e}).[/yellow]")
        typed = Prompt.ask(
            "Enter output folder path",
            default=str(Path.home() / "API-Smoke-Reports"),
        )
        p = Path(typed).expanduser()
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except OSError:
            console.print("[red]Unable to write report to selected folder.[/red]")
            return None


def open_path(path: Path) -> None:
    """Reveal a folder or file with the platform file manager."""
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["open", str(path)], check=False)
        elif system == "Windows":
            subprocess.run(["explorer", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except OSError as e:
        console.print(f"[dim]Could not open path: {e}[/dim]")


def read_multiline_curl() -> str:
    """Read a multiline cURL until a blank line (or END)."""
    console.print(
        "[dim]Paste cURL request, then press Enter on an empty line (or type END):[/dim]"
    )
    lines: list[str] = []
    while True:
        try:
            line = console.input("")
        except (EOFError, KeyboardInterrupt):
            break
        if line.strip().upper() == "END":
            break
        if line.strip() == "" and lines:
            break
        lines.append(line)
    return "\n".join(lines).strip()


def show_request_preview(request: ApiRequest) -> None:
    preview = mask_request_preview(request)
    table = Table(title="Parsed Request", border_style="cyan", show_header=False)
    table.add_column("Field", style="dim")
    table.add_column("Value")
    table.add_row("Method", str(preview["method"]))
    table.add_row("URL", str(preview["url"]))
    headers = preview.get("headers") or {}
    table.add_row("Headers", f"{len(headers)}")
    for k, v in headers.items():
        table.add_row(f"  {k}", str(v))
    body = preview.get("body")
    table.add_row("Body", "JSON/text" if body else "(none)")
    if body:
        snippet = str(body)
        if len(snippet) > 400:
            snippet = snippet[:400] + "…"
        table.add_row("Body preview", snippet)
    if request.parse_errors:
        table.add_row("[red]Errors[/red]", "; ".join(request.parse_errors))
    console.print(table)


def run_dashboard(
    *,
    curl_text: str | None = None,
    output_dir: Path | str | None = None,
    assume_yes: bool = False,
) -> SmokeTestReport | None:
    """Interactive or scripted smoke-test dashboard."""
    console.print()
    console.print(Panel(BANNER, border_style="cyan", padding=(1, 2)))

    if curl_text is None:
        curl_text = read_multiline_curl()
    if not curl_text:
        console.print("[red]Unable to parse cURL. Please verify the request.[/red]")
        return None

    console.print("\n[bold]Parse cURL[/bold]")
    request = parse_curl(curl_text)
    show_request_preview(request)

    if request.parse_errors and not request.url:
        console.print("[red]Unable to parse cURL. Please verify the request.[/red]")
        return None

    out: Path | None
    if output_dir is not None:
        out = Path(output_dir).expanduser()
        try:
            out.mkdir(parents=True, exist_ok=True)
        except OSError:
            console.print("[red]Unable to write report to selected folder.[/red]")
            return None
    else:
        console.print()
        if assume_yes:
            out = Path.home() / "API-Smoke-Reports"
            out.mkdir(parents=True, exist_ok=True)
        else:
            console.print("[dim]Output Folder — click Select Folder in the dialog[/dim]")
            out = select_output_folder()
            if out is None:
                console.print("[yellow]Cancelled — no output folder selected.[/yellow]")
                return None

    console.print(f"[green]Selected folder:[/green] {out}")

    if request.is_destructive and not assume_yes:
        console.print(
            Panel(
                f"[yellow]This API may modify data[/yellow] ({request.method}).\n"
                "The smoke runner will execute the request [bold]exactly once[/bold].",
                title="Destructive method",
                border_style="yellow",
            )
        )
        if not Confirm.ask("Run once?", default=False):
            console.print("[dim]Cancelled.[/dim]")
            return None

    engine = SmokeTestEngine()
    completed: list[tuple[str, str]] = []

    console.print()
    console.print("[bold]Running API Smoke Tests...[/bold]")

    def on_progress(name: str, result: object) -> None:
        from querymind.smoke.models import SmokeTestResult

        if isinstance(result, SmokeTestResult):
            if result.status == SmokeTestStatus.PASS:
                icon = "[green]✓[/green]"
            elif result.status == SmokeTestStatus.FAIL:
                icon = "[red]✗[/red]"
            elif result.status == SmokeTestStatus.WARNING:
                icon = "[yellow]![/yellow]"
            elif result.status == SmokeTestStatus.SKIPPED:
                icon = "[dim]○[/dim]"
            else:
                icon = "[cyan]·[/cyan]"
            console.print(f"  {icon} {name}")
            completed.append((name, result.status.value))
        else:
            console.print(f"  [cyan]●[/cyan] {name}…")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Executing smoke suite…", total=None)
        report = engine.run(request, on_progress=on_progress)

    writer = SmokeReportWriter()
    try:
        paths = writer.write(report, out)
    except OSError:
        console.print("[red]Unable to write report to selected folder.[/red]")
        return report

    _show_completion(report, paths)
    return report


def _show_completion(report: SmokeTestReport, paths: dict[str, Path]) -> None:
    s = report.summary
    tone = "green"
    if s.overall_status == OverallStatus.FAIL:
        tone = "red"
    elif s.overall_status == OverallStatus.PASS_WITH_WARNINGS:
        tone = "yellow"

    console.print()
    console.print(
        Panel(
            f"[bold {tone}]SMOKE TEST COMPLETED[/bold {tone}]\n"
            f"[bold]{s.overall_status.value}[/bold]\n"
            f"Health Score: {s.health_score}%\n"
            f"{s.passed} Passed · {s.failed} Failed · {s.warnings} Warnings · "
            f"{s.skipped} Skipped\n"
            f"Duration: {s.duration_ms} ms\n\n"
            f"[dim]HTML:[/dim] {paths['html']}\n"
            f"[dim]PDF:[/dim]  {paths['pdf']}\n"
            f"[dim]JSON:[/dim] {paths['json']}",
            border_style=tone,
        )
    )

    console.print(
        "\n[cyan]v[/cyan] View Interactive Report  ·  "
        "[cyan]o[/cyan] Open Output Folder  ·  "
        "[cyan]r[/cyan] Run Again  ·  "
        "[cyan]q[/cyan] Quit"
    )
    try:
        choice = Prompt.ask("Next", choices=["v", "o", "r", "q"], default="v")
    except (EOFError, KeyboardInterrupt):
        return

    if choice == "v":
        webbrowser.open(paths["html"].as_uri())
    elif choice == "o":
        open_path(paths["directory"])
    elif choice == "r":
        run_dashboard()
