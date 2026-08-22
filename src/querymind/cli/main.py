"""QueryMind CLI entry point."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from querymind.agent.runtime import AgentRuntime
from querymind.agent.state import AgentStatus
from querymind.config.settings import settings
from querymind.llm.groq import GroqProvider
from querymind.tools.base import ToolResult

app = typer.Typer(
    name="querymind",
    help="QueryMind - AI API Testing Agent",
    no_args_is_help=False,
)
console = Console()

BANNER = """\
[bold cyan]QueryMind[/bold cyan]
[dim]AI API Testing Agent[/dim]"""


def make_runtime(on_step: object = None) -> AgentRuntime:
    """Create an AgentRuntime with the configured Groq provider."""
    llm = GroqProvider(api_keys=settings.groq_api_key_list, model=settings.groq_model)
    return AgentRuntime(llm=llm, on_step=on_step)  # type: ignore[arg-type]


def format_tool_call(tool_name: str, arguments: dict[str, object]) -> str:
    """Format a tool call for display."""
    if tool_name == "send_http_request":
        method = str(arguments.get("method", "?"))
        url = str(arguments.get("url", "?"))
        return f"{method} {url}"
    if tool_name == "get_current_test_environment":
        return "Checking environment..."
    return tool_name


def step_printer(iteration: int, tool_name: str, result: ToolResult) -> None:
    """Print tool activity with detail."""
    if tool_name == "send_http_request":
        meta = result.metadata
        status = meta.get("status", "?")
        url = meta.get("url", "")
        method = meta.get("method", "")
        icon = "[green]✓[/green]" if result.is_success else "[red]✗[/red]"
        console.print(f"  [dim]⚙[/dim] {method} {url} → {icon} {status}")
    else:
        icon = "[green]✓[/green]" if result.is_success else "[red]✗[/red]"
        console.print(f"  [dim]⚙[/dim] {tool_name} {icon}")


async def run_agent(runtime: AgentRuntime, user_input: str) -> None:
    """Run the agent on user input and display results."""
    console.print()
    state = await runtime.run(user_input)

    if state.status == AgentStatus.COMPLETED and state.final_response:
        console.print()
        # Render markdown if it contains markdown syntax
        text = state.final_response
        if any(c in text for c in ["#", "**", "`", "-"]):
            console.print(Markdown(text))
        else:
            console.print(Panel(text, border_style="cyan", padding=(0, 1)))
    elif state.status == AgentStatus.ERROR:
        console.print(f"\n[bold red]Error:[/bold red] {state.error}")
    elif state.status == AgentStatus.MAX_ITERATIONS:
        console.print(f"\n[yellow]{state.final_response}[/yellow]")
    else:
        console.print(f"\n[dim]Agent stopped with status: {state.status}[/dim]")

    # Show tool call summary if any
    if state.tool_calls:
        console.print(
            f"[dim]({len(state.tool_calls)} tool call"
            f"{'s' if len(state.tool_calls) > 1 else ''}, "
            f"{state.iteration} iterations)[/dim]"
        )


def run_interactive() -> None:
    """Run the interactive CLI session."""
    console.print()
    console.print(Panel(BANNER, border_style="cyan", padding=(1, 2)))

    if not settings.groq_api_key_list:
        console.print(
            "[bold yellow]No API keys configured.[/bold yellow]\n"
            "Set [cyan]GROQ_API_KEYS[/cyan] in your .env file.\n"
        )
        raise typer.Exit(1)

    runtime = make_runtime(on_step=step_printer)

    console.print(
        f"[dim]Model: {settings.groq_model} | "
        f"Keys: {len(settings.groq_api_key_list)}[/dim]\n"
    )

    console.print(
        "Type a request or [bold]exit[/bold] to quit.\n"
        "[dim]Example: test http://localhost:3000/api/health[/dim]\n"
    )

    while True:
        try:
            user_input = console.input("[bold green]>[/bold green] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        command = user_input.strip()
        if not command:
            continue
        if command in ("exit", "quit", "q"):
            console.print("[dim]Goodbye.[/dim]")
            break
        if command == "clear":
            console.clear()
            continue
        if command == "help":
            console.print(
                Panel(
                    "[bold]Commands[/bold]\n"
                    "  [cyan]help[/cyan]   — Show this message\n"
                    "  [cyan]clear[/cyan]  — Clear the screen\n"
                    "  [cyan]exit[/cyan]   — Exit QueryMind\n\n"
                    "[bold]Examples[/bold]\n"
                    "  [dim]test http://localhost:3000/api/login[/dim]\n"
                    "  [dim]what can you do?[/dim]\n"
                    "  [dim]check this API for security issues[/dim]",
                    title="Help",
                    border_style="dim",
                )
            )
            continue

        try:
            asyncio.run(run_agent(runtime, command))
        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted.[/dim]")
        except Exception as e:
            console.print(f"\n[bold red]Unexpected error:[/bold red] {e}")


@app.command()
def main() -> None:
    """Launch QueryMind interactive session."""
    run_interactive()


if __name__ == "__main__":
    app()
