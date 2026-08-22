"""QueryMind CLI entry point."""

import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(
    name="querymind",
    help="QueryMind - AI API Testing Agent",
    no_args_is_help=False,
)
console = Console()

BANNER = """\
[bold cyan]QueryMind[/bold cyan]
[dim]AI API Testing Agent[/dim]"""


def run_interactive() -> None:
    """Run the interactive CLI session."""
    console.print(
        Panel(BANNER, border_style="cyan", padding=(1, 2))
    )
    console.print("QueryMind is ready.\n")

    while True:
        try:
            user_input = console.input("[bold green]>[/bold green] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\nGoodbye.")
            break

        command = user_input.strip()
        if not command:
            continue
        if command in ("exit", "quit"):
            console.print("Goodbye.")
            break
        if command == "clear":
            console.clear()
            continue
        if command == "help":
            console.print(
                "Commands:\n"
                "  help   - Show this message\n"
                "  clear  - Clear the screen\n"
                "  exit   - Exit QueryMind\n"
            )
            continue

        console.print(
            f"[dim]QueryMind received:[/dim] {command}\n"
            "[dim]Agent functionality coming in Phase 1+.[/dim]"
        )


@app.command()
def main() -> None:
    """Launch QueryMind interactive session."""
    run_interactive()


if __name__ == "__main__":
    app()
