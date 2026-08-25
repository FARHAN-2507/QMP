"""CLI entry for ApiSmokeTesting (`querymind smoke`)."""

from __future__ import annotations

from pathlib import Path

import typer

from querymind.smoke.dashboard import run_dashboard

smoke_app = typer.Typer(
    name="smoke",
    help="API Smoke Test Automation — paste cURL, run generic smoke tests, get reports.",
    no_args_is_help=False,
    add_completion=False,
)


@smoke_app.callback(invoke_without_command=True)
def smoke_main(  # noqa: B008 — Typer Option defaults are idiomatic
    ctx: typer.Context,
    curl_file: Path | None = typer.Option(  # noqa: B008
        None,
        "--curl-file",
        "-f",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Read cURL from a file (non-interactive).",
    ),
    output_dir: Path | None = typer.Option(  # noqa: B008
        None,
        "--output-dir",
        "-o",
        help="Output folder for reports (skips folder dialog).",
    ),
    yes: bool = typer.Option(  # noqa: B008
        False,
        "--yes",
        "-y",
        help="Skip destructive-method confirmation.",
    ),
) -> None:
    """Launch the terminal smoke dashboard (default)."""
    if ctx.invoked_subcommand is not None:
        return

    curl_text: str | None = None
    if curl_file is not None:
        curl_text = curl_file.read_text(encoding="utf-8")

    run_dashboard(curl_text=curl_text, output_dir=output_dir, assume_yes=yes)


@smoke_app.command("serve")
def smoke_serve(  # noqa: B008
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host"),
    port: int = typer.Option(8787, "--port", "-p", help="Bind port"),
    open_browser: bool = typer.Option(
        True,
        "--open/--no-open",
        help="Open the dashboard in a browser",
    ),
) -> None:
    """Start the one-page web dashboard + smoke API (FastAPI)."""
    import threading
    import time
    import webbrowser

    import uvicorn

    from querymind.api.app import app

    url = f"http://{host}:{port}/"
    typer.echo(f"QueryMind Smoke Dashboard → {url}")
    typer.echo("API base → /api/smoke  (parse, run, reports)")

    if open_browser:

        def _open() -> None:
            time.sleep(0.8)
            webbrowser.open(url)

        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(app, host=host, port=port, log_level="info")
