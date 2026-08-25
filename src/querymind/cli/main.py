"""QueryMind CLI entry point — modern TUI interface like OpenCode."""

from __future__ import annotations

import asyncio
from typing import Any

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

from querymind.agent.runtime import AgentRuntime
from querymind.agent.state import AgentStatus
from querymind.cli.tui import (
    create_auth_table,
    create_banner,
    create_help_panel,
    create_response_panel,
    create_sessions_table,
    create_status_bar,
    create_tool_activity,
)
from querymind.config.settings import settings
from querymind.llm.groq import GroqProvider
from querymind.security.models import AuthConfig, AuthType
from querymind.tools.base import ToolResult

# Custom theme
theme = Theme({
    "info": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "dim": "dim",
    "bold": "bold",
})

app = typer.Typer(
    name="querymind",
    help="QueryMind - AI API Testing Agent",
    no_args_is_help=False,
)
console = Console(theme=theme)


def make_runtime(on_step: object = None) -> AgentRuntime:
    """Create an AgentRuntime with the configured Groq provider."""
    llm = GroqProvider(api_keys=settings.groq_api_key_list, model=settings.groq_model)
    return AgentRuntime(llm=llm, on_step=on_step)  # type: ignore[arg-type]


def print_welcome(runtime: AgentRuntime | None = None) -> None:
    """Print welcome screen."""
    console.print()
    console.print(create_banner())

    # Status bar
    if runtime:
        status_bar = create_status_bar(
            model=settings.groq_model,
            session_id=runtime.session_id,
            message_count=runtime.get_message_count(),
            tool_count=10,
        )
        console.print(status_bar)
    else:
        console.print(
            Text.from_markup(
                f"[dim]Model: {settings.groq_model} | "
                f"Keys: {len(settings.groq_api_key_list)}[/dim]"
            )
        )
    console.print()

    # Quick help
    console.print(
        Text.from_markup(
            "[dim]Type a request or [bold]help[/bold] for commands. "
            "[bold]exit[/bold] to quit.[/dim]"
        )
    )
    console.print()


def print_tool_call(tool_name: str, arguments: dict[str, Any]) -> None:
    """Print tool call with animation."""
    if tool_name == "send_http_request":
        method = str(arguments.get("method", "?"))
        url = str(arguments.get("url", "?"))
        details = f"{method} {url}"
    elif tool_name == "generate_report":
        details = "Generating HTML report..."
    elif tool_name == "run_test":
        details = f"Running test: {arguments.get('name', 'unknown')}"
    elif tool_name == "generate_tests":
        details = "Generating test suite..."
    elif tool_name == "import_openapi":
        details = f"Importing: {arguments.get('url', 'unknown')}"
    elif tool_name == "discover_api":
        details = f"Discovering: {arguments.get('base_url', 'unknown')}"
    elif tool_name == "configure_auth":
        details = f"Configuring: {arguments.get('auth_type', 'unknown')} auth"
    else:
        details = ""

    console.print(create_tool_activity(tool_name, "running", details))


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

    # Show thinking
    with console.status("[bold cyan]Thinking...[/bold cyan]", spinner="dots"):
        state = await runtime.run(user_input)

    if state.status == AgentStatus.COMPLETED and state.final_response:
        console.print()
        # Render markdown if it contains markdown syntax
        text = state.final_response
        if any(c in text for c in ["#", "**", "`", "-", "|"]):
            console.print(Markdown(text))
        else:
            console.print(create_response_panel(text))
    elif state.status == AgentStatus.ERROR:
        console.print(create_response_panel(f"Error: {state.error}", is_error=True))
    elif state.status == AgentStatus.MAX_ITERATIONS:
        console.print(create_response_panel(state.final_response or "", is_error=True))
    else:
        console.print(f"[dim]Agent stopped with status: {state.status}[/dim]")

    # Show tool call summary
    if state.tool_calls:
        tool_count = len(state.tool_calls)
        console.print(
            f"[dim]  {tool_count} tool call{'s' if tool_count > 1 else ''}, "
            f"{state.iteration} iterations[/dim]"
        )
    console.print()


def show_sessions(runtime: AgentRuntime) -> None:
    """Display list of saved sessions."""
    sessions = runtime.list_sessions()
    table_panel = create_sessions_table(sessions, runtime.session_id)
    console.print(table_panel)


def show_auth(runtime: AgentRuntime) -> None:
    """Display configured authentication."""
    configs = runtime.auth_provider.list_auth()
    table_panel = create_auth_table(configs)
    console.print(table_panel)


def parse_auth_command(args: str) -> tuple[str, str, dict[str, str]]:
    """Parse auth command arguments."""
    parts = args.split()
    if len(parts) < 2:
        return "", "", {}

    base_url = parts[0]
    auth_type = parts[1]
    options: dict[str, str] = {}

    for part in parts[2:]:
        if "=" in part:
            key, value = part.split("=", 1)
            options[key] = value

    return base_url, auth_type, options


def handle_auth_set(runtime: AgentRuntime, args: str) -> None:
    """Handle 'auth set' command."""
    base_url, auth_type_str, options = parse_auth_command(args)

    if not base_url or not auth_type_str:
        console.print(
            Panel(
                Text.from_markup(
                    "[bold]Usage:[/bold] auth set <base_url> <type> [options]\n\n"
                    "[bold]Types:[/bold] api_key, bearer, basic, oauth2\n\n"
                    "[bold]Options:[/bold]\n"
                    "  --token=xxx          Bearer/OAuth2 token\n"
                    "  --key-name=X-API-Key API key header name\n"
                    "  --key-value=xxx      API key value\n"
                    "  --username=xxx       Basic auth username\n"
                    "  --password=xxx       Basic auth password"
                ),
                title="[bold]Auth Set[/bold]",
                border_style="dim",
            )
        )
        return

    try:
        auth_type = AuthType(auth_type_str)
    except ValueError:
        console.print(f"[red]Invalid auth type:[/red] {auth_type_str}")
        return

    config = AuthConfig(type=auth_type, base_url=base_url)

    if auth_type == AuthType.API_KEY:
        config.key_name = options.get("key-name", "X-API-Key")
        config.key_value = options.get("key-value", options.get("key", ""))
        config.key_location = options.get("location", "header")
    elif auth_type == AuthType.BEARER:
        config.token = options.get("token", "")
    elif auth_type == AuthType.BASIC:
        config.username = options.get("username", "")
        config.password = options.get("password", "")
    elif auth_type == AuthType.OAUTH2:
        config.client_id = options.get("client-id", "")
        config.client_secret = options.get("client-secret", "")
        config.token_url = options.get("token-url", "")
        config.access_token = options.get("access-token", options.get("token", ""))

    runtime.auth_provider.set_auth(base_url, config)
    masked = config.mask_sensitive()
    console.print(f"[green]✓ Auth configured for {base_url} ({auth_type_str})[/green]")
    console.print(f"[dim]{masked}[/dim]")


def handle_auth_clear(runtime: AgentRuntime, args: str) -> None:
    """Handle 'auth clear' command."""
    base_url = args.strip()
    if not base_url:
        # Clear all
        count = runtime.auth_provider.clear_all()
        console.print(f"[green]✓ Cleared {count} auth config(s).[/green]")
    else:
        deleted = runtime.auth_provider.remove_auth(base_url)
        if deleted:
            console.print(f"[green]✓ Auth cleared for {base_url}[/green]")
        else:
            console.print(f"[dim]No auth found for {base_url}[/dim]")


def handle_command(runtime: AgentRuntime, command: str) -> bool:
    """Handle built-in commands. Returns True if command was handled."""
    if command in ("exit", "quit", "q"):
        console.print("[dim]Goodbye.[/dim]")
        return True

    if command == "clear":
        runtime.reset()
        console.clear()
        print_welcome(runtime)
        return False

    if command == "sessions":
        show_sessions(runtime)
        return False

    if command.startswith("load "):
        session_id = command.split(" ", 1)[1].strip()
        if runtime.load_session(session_id):
            console.print(f"[green]✓ Loaded session {session_id}[/green]")
            console.print(
                f"[dim]  {runtime.get_message_count()} messages in history[/dim]"
            )
        else:
            console.print(f"[red]✗ Session not found: {session_id}[/red]")
        return False

    if command == "new":
        new_id = runtime.new_session()
        console.print(f"[green]✓ New session: {new_id}[/green]")
        return False

    if command in ("auth", "auth list"):
        show_auth(runtime)
        return False

    if command.startswith("auth set "):
        handle_auth_set(runtime, command[9:])
        return False

    if command.startswith("auth clear"):
        args = command[10:].strip()
        handle_auth_clear(runtime, args)
        return False

    if command == "help":
        console.print(create_help_panel())
        return False

    return False


def run_interactive() -> None:
    """Run the interactive CLI session."""
    console.clear()

    if not settings.groq_api_key_list:
        console.print(
            Panel(
                Text.from_markup(
                    "[bold yellow]No API keys configured.[/bold yellow]\n\n"
                    "Set [cyan]GROQ_API_KEYS[/cyan] in your .env file:\n"
                    "[dim]GROQ_API_KEYS=gsk_...[/dim]"
                ),
                title="[bold]Configuration[/bold]",
                border_style="yellow",
            )
        )
        raise typer.Exit(1)

    runtime = make_runtime(on_step=step_printer)

    # Print welcome with runtime info
    print_welcome(runtime)

    while True:
        try:
            # Input with prompt
            user_input = console.input("[bold green]❯[/bold green] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        command = user_input.strip()
        if not command:
            continue

        # Handle built-in commands
        if handle_command(runtime, command):
            break

        # Run agent
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
