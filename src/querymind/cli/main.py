"""QueryMind CLI entry point."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from querymind.agent.runtime import AgentRuntime
from querymind.agent.state import AgentStatus
from querymind.config.settings import settings
from querymind.llm.groq import GroqProvider
from querymind.security.models import AuthConfig, AuthType
from querymind.tools.base import ToolResult

app = typer.Typer(
    name="querymind",
    help="QueryMind - AI API Testing Agent",
    no_args_is_help=False,
)
console = Console()

BANNER = """\
[bold cyan]QueryMind[/bold cyan]
[dim]AI API Testing Agent — Multi-turn with persistent memory[/dim]"""


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

    # Show tool call summary and session info
    msg_count = runtime.get_message_count()
    parts: list[str] = []
    if state.tool_calls:
        parts.append(
            f"{len(state.tool_calls)} tool call"
            f"{'s' if len(state.tool_calls) > 1 else ''}, "
            f"{state.iteration} iterations"
        )
    parts.append(f"{msg_count} messages")
    if runtime.session_id:
        parts.append(f"session:{runtime.session_id}")
    console.print(f"[dim]({', '.join(parts)})[/dim]")


def show_sessions(runtime: AgentRuntime) -> None:
    """Display list of saved sessions."""
    sessions = runtime.list_sessions()
    if not sessions:
        console.print("[dim]No saved sessions.[/dim]")
        return

    table = Table(title="Saved Sessions", border_style="dim")
    table.add_column("ID", style="cyan")
    table.add_column("Last Updated")
    table.add_column("Messages", justify="right")

    for s in sessions:
        is_current = s["session_id"] == runtime.session_id
        sid = f"[bold]{s['session_id']}[/bold] *" if is_current else s["session_id"]
        table.add_row(
            sid,
            s.get("updated_at", "unknown")[:19],
            str(s.get("total_messages", 0)),
        )

    console.print(table)
    console.print("[dim]* = current session[/dim]")


def show_auth(runtime: AgentRuntime) -> None:
    """Display configured authentication."""
    configs = runtime.auth_provider.list_auth()
    if not configs:
        console.print("[dim]No authentication configured.[/dim]")
        return

    table = Table(title="Configured Authentication", border_style="dim")
    table.add_column("Base URL", style="cyan")
    table.add_column("Type")
    table.add_column("Details")

    for config in configs:
        url = config.get("base_url", "unknown")
        auth_type = config.get("type", "unknown")
        details = ""
        if auth_type == "api_key":
            details = f"Key: {config.get('key_name', 'X-API-Key')}"
        elif auth_type == "bearer":
            details = f"Token: {config.get('token', '***')[:20]}..."
        elif auth_type == "basic":
            details = f"User: {config.get('username', '')}"
        elif auth_type == "oauth2":
            details = f"Client: {config.get('client_id', '')[:20]}..."

        table.add_row(url, auth_type, details)

    console.print(table)


def parse_auth_command(args: str) -> tuple[str, str, dict[str, str]]:
    """Parse auth command arguments.

    Returns: (base_url, auth_type, options)
    """
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
            "[red]Usage:[/red] auth set <base_url> <type> [options]\n"
            "[dim]Types: api_key, bearer, basic, oauth2[/dim]\n"
            "[dim]Options: --token=xxx --key-name=X-API-Key --key-value=xxx[/dim]\n"
            "[dim]         --username=xxx --password=xxx[/dim]"
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
    console.print(f"[green]Auth configured for {base_url} ({auth_type_str})[/green]")
    console.print(f"[dim]{masked}[/dim]")


def handle_auth_clear(runtime: AgentRuntime, args: str) -> None:
    """Handle 'auth clear' command."""
    base_url = args.strip()
    if not base_url:
        # Clear all
        count = runtime.auth_provider.clear_all()
        console.print(f"[green]Cleared {count} auth config(s).[/green]")
    else:
        deleted = runtime.auth_provider.remove_auth(base_url)
        if deleted:
            console.print(f"[green]Auth cleared for {base_url}[/green]")
        else:
            console.print(f"[dim]No auth found for {base_url}[/dim]")


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

    session_info = f"session:{runtime.session_id}" if runtime.session_id else "new session"
    console.print(
        f"[dim]Model: {settings.groq_model} | "
        f"Keys: {len(settings.groq_api_key_list)} | "
        f"{session_info}[/dim]\n"
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
            runtime.reset()
            console.clear()
            console.print(f"[dim]New session: {runtime.session_id}[/dim]\n")
            continue
        if command == "sessions":
            show_sessions(runtime)
            continue
        if command.startswith("load "):
            session_id = command.split(" ", 1)[1].strip()
            if runtime.load_session(session_id):
                console.print(f"[green]Loaded session {session_id}[/green]")
                console.print(f"[dim]({runtime.get_message_count()} messages in history)[/dim]\n")
            else:
                console.print(f"[red]Session not found: {session_id}[/red]")
            continue
        if command == "new":
            new_id = runtime.new_session()
            console.print(f"[green]New session: {new_id}[/green]\n")
            continue
        if command == "auth" or command == "auth list":
            show_auth(runtime)
            continue
        if command.startswith("auth set "):
            handle_auth_set(runtime, command[9:])
            continue
        if command.startswith("auth clear"):
            args = command[10:].strip()
            handle_auth_clear(runtime, args)
            continue
        if command == "help":
            console.print(
                Panel(
                    "[bold]Commands[/bold]\n"
                    "  [cyan]help[/cyan]        — Show this message\n"
                    "  [cyan]clear[/cyan]       — Start new session\n"
                    "  [cyan]new[/cyan]         — Start new session\n"
                    "  [cyan]sessions[/cyan]    — List saved sessions\n"
                    "  [cyan]load <id>[/cyan]   — Load a saved session\n"
                    "  [cyan]auth[/cyan]        — Show configured authentication\n"
                    "  [cyan]auth set[/cyan]    — Configure authentication\n"
                    "  [cyan]auth clear[/cyan]  — Clear authentication\n"
                    "  [cyan]exit[/cyan]        — Exit QueryMind\n\n"
                    "[bold]Auth Examples[/bold]\n"
                    "  [dim]auth set <url> bearer --token=eyJhbG...[/dim]\n"
                    "  [dim]auth set <url> api-key --key-name=X-API-Key --key-value=abc[/dim]\n"
                    "  [dim]auth set <url> basic --username=user --password=pass[/dim]\n"
                    "  [dim]auth clear <url>[/dim]\n\n"
                    "[bold]Testing Examples[/bold]\n"
                    "  [dim]test http://localhost:3000/api/login[/dim]\n"
                    "  [dim]now test the register endpoint[/dim]  (remembers previous context)\n"
                    "  [dim]what did we test so far?[/dim]        (agent remembers)\n"
                    "  [dim]sessions[/dim]                       (view all sessions)",
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
