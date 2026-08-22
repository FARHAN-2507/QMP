"""QueryMind CLI entry point."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
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


def step_printer(iteration: int, tool_name: str, result: ToolResult) -> None:
    """Print tool activity as it happens."""
    status_icon = "[green]✓[/green]" if result.is_success else "[red]✗[/red]"
    console.print(f"  [dim]⚙[/dim] {tool_name} {status_icon}")


async def run_agent(runtime: AgentRuntime, user_input: str) -> None:
    """Run the agent on user input and display results."""
    console.print("\n[dim]QueryMind is analyzing...[/dim]\n")

    state = await runtime.run(user_input)

    if state.status == AgentStatus.COMPLETED and state.final_response:
        console.print()
        console.print(Panel(state.final_response, title="Agent", border_style="cyan"))
    elif state.status == AgentStatus.ERROR:
        console.print(f"\n[red]Error:[/red] {state.error}")
    elif state.status == AgentStatus.MAX_ITERATIONS:
        console.print(f"\n[yellow]{state.final_response}[/yellow]")
    else:
        console.print(f"\n[dim]Agent stopped with status: {state.status}[/dim]")


def run_interactive() -> None:
    """Run the interactive CLI session."""
    console.print(Panel(BANNER, border_style="cyan", padding=(1, 2)))

    if not settings.groq_api_key_list:
        console.print(
            "[yellow]Warning: GROQ_API_KEYS is not set. "
            "The agent will not work without it.[/yellow]\n"
        )

    runtime = make_runtime(on_step=step_printer)
    console.print(f"[dim]{runtime.get_tools_summary()}[/dim]\n")
    console.print("QueryMind is ready. Type your request or 'exit' to quit.\n")

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
                "\n"
                "Or type a request to test an API.\n"
            )
            continue

        asyncio.run(run_agent(runtime, command))


@app.command()
def main() -> None:
    """Launch QueryMind interactive session."""
    run_interactive()


if __name__ == "__main__":
    app()
