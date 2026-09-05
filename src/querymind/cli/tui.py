"""QueryMind TUI components — beautiful terminal interface like OpenCode."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

# Color scheme
COLORS = {
    "primary": "cyan",
    "secondary": "blue",
    "success": "green",
    "error": "red",
    "warning": "yellow",
    "dim": "dim",
    "bold": "bold",
}


def create_banner() -> Panel:
    """Create the main banner panel."""
    banner_text = Text()
    banner_text.append("⚡ ", style="bold yellow")
    banner_text.append("QueryMind", style="bold cyan")
    banner_text.append(" — ", style="dim")
    banner_text.append("AI API Testing Agent", style="dim")

    return Panel(
        banner_text,
        border_style="cyan",
        padding=(0, 1),
    )


def create_status_bar(
    model: str,
    session_id: str | None,
    message_count: int,
    auth_count: int = 0,
    tool_count: int = 0,
) -> Panel:
    """Create a status bar at the bottom."""
    parts: list[str] = []

    # Model info
    parts.append(f"[bold cyan]Model:[/bold cyan] {model}")

    # Session info
    if session_id:
        short_id = session_id[:8] if len(session_id) > 8 else session_id
        parts.append(f"[bold cyan]Session:[/bold cyan] {short_id}")

    # Message count
    parts.append(f"[bold cyan]Messages:[/bold cyan] {message_count}")

    # Auth info
    if auth_count > 0:
        parts.append(f"[bold green]Auth:[/bold green] {auth_count} configured")

    # Tool count
    parts.append(f"[bold cyan]Tools:[/bold cyan] {tool_count}")

    status_text = " │ ".join(parts)

    return Panel(
        Text.from_markup(status_text),
        border_style="dim",
        padding=(0, 1),
    )


def create_help_panel() -> Panel:
    """Create a beautiful help panel."""
    help_text = Text()

    help_text.append("Commands\n", style="bold cyan")
    help_text.append("  ", style="dim")
    help_text.append("help", style="bold green")
    help_text.append("        — Show this message\n", style="dim")

    help_text.append("  ", style="dim")
    help_text.append("clear", style="bold green")
    help_text.append("       — Start new session\n", style="dim")

    help_text.append("  ", style="dim")
    help_text.append("new", style="bold green")
    help_text.append("         — Start new session\n", style="dim")

    help_text.append("  ", style="dim")
    help_text.append("sessions", style="bold green")
    help_text.append("    — List saved sessions\n", style="dim")

    help_text.append("  ", style="dim")
    help_text.append("load <id>", style="bold green")
    help_text.append("   — Load a saved session\n", style="dim")

    help_text.append("  ", style="dim")
    help_text.append("auth", style="bold green")
    help_text.append("        — Show configured authentication\n", style="dim")

    help_text.append("  ", style="dim")
    help_text.append("auth set", style="bold green")
    help_text.append("    — Configure authentication\n", style="dim")

    help_text.append("  ", style="dim")
    help_text.append("auth clear", style="bold green")
    help_text.append("  — Clear authentication\n", style="dim")

    help_text.append("  ", style="dim")
    help_text.append("exit", style="bold green")
    help_text.append("        — Exit QueryMind\n", style="dim")

    help_text.append("\n", style="dim")
    help_text.append("API Key Commands\n", style="bold cyan")
    help_text.append("  ", style="dim")
    help_text.append("/setkey <key>", style="bold green")
    help_text.append("  — Add Groq API key\n", style="dim")

    help_text.append("  ", style="dim")
    help_text.append("/showkey", style="bold green")
    help_text.append("       — Show configured keys\n", style="dim")

    help_text.append("  ", style="dim")
    help_text.append("/removekey <n>", style="bold green")
    help_text.append(" — Remove key by index\n", style="dim")

    help_text.append("\n", style="dim")
    help_text.append("Auth Examples\n", style="bold cyan")
    help_text.append("  ", style="dim")
    help_text.append("auth set <url> bearer --token=eyJhbG...\n", style="dim")

    help_text.append("  ", style="dim")
    help_text.append("auth set <url> api-key --key-name=X-API-Key --key-value=abc\n", style="dim")

    help_text.append("  ", style="dim")
    help_text.append("auth set <url> basic --username=user --password=pass\n", style="dim")

    help_text.append("\n", style="dim")
    help_text.append("Testing Examples\n", style="bold cyan")
    help_text.append("  ", style="dim")
    help_text.append("test http://localhost:3000/api/login\n", style="dim")

    help_text.append("  ", style="dim")
    help_text.append("now test the register endpoint", style="dim")
    help_text.append("  (remembers previous context)\n", style="dim")

    help_text.append("  ", style="dim")
    help_text.append("what did we test so far?", style="dim")
    help_text.append("        (agent remembers)\n", style="dim")

    return Panel(
        help_text,
        title="[bold]Help[/bold]",
        border_style="dim",
        padding=(1, 2),
    )


def create_tool_activity(
    tool_name: str,
    status: str = "running",
    details: str = "",
) -> Panel:
    """Create a tool activity panel."""
    content = Text()

    if status == "running":
        content.append("⟳ ", style="bold yellow")
        content.append(f"{tool_name}", style="bold")
        if details:
            content.append(f" — {details}", style="dim")
    elif status == "success":
        content.append("✓ ", style="bold green")
        content.append(f"{tool_name}", style="bold")
        if details:
            content.append(f" — {details}", style="dim")
    elif status == "error":
        content.append("✗ ", style="bold red")
        content.append(f"{tool_name}", style="bold")
        if details:
            content.append(f" — {details}", style="dim")

    return Panel(
        content,
        border_style="dim",
        padding=(0, 1),
    )


def create_response_panel(response: str, is_error: bool = False) -> Panel:
    """Create a response panel."""
    if is_error:
        return Panel(
            Text(response, style="red"),
            title="[bold red]Error[/bold red]",
            border_style="red",
            padding=(1, 2),
        )
    return Panel(
        Text(response, style="white"),
        border_style="cyan",
        padding=(1, 2),
    )


def create_sessions_table(
    sessions: list[dict[str, str]], current_session: str | None = None
) -> Panel:
    """Create a sessions table."""
    if not sessions:
        return Panel(
            Text("No saved sessions.", style="dim"),
            title="[bold]Sessions[/bold]",
            border_style="dim",
        )

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", style="cyan")
    table.add_column("Last Updated")
    table.add_column("Messages", justify="right")

    for s in sessions:
        is_current = s["session_id"] == current_session
        sid = f"[bold]{s['session_id'][:8]}[/bold] *" if is_current else s["session_id"][:8]
        table.add_row(
            sid,
            s.get("updated_at", "unknown")[:19],
            s.get("total_messages", "0"),
        )

    return Panel(
        table,
        title="[bold]Sessions[/bold]",
        border_style="dim",
        padding=(1, 1),
    )


def create_auth_table(configs: list[dict[str, str]]) -> Panel:
    """Create an auth configuration table."""
    if not configs:
        return Panel(
            Text("No authentication configured.", style="dim"),
            title="[bold]Authentication[/bold]",
            border_style="dim",
        )

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Base URL", style="cyan")
    table.add_column("Type")
    table.add_column("Details")

    for config in configs:
        url = str(config.get("base_url", "unknown"))
        auth_type = str(config.get("type", "unknown"))
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

    return Panel(
        table,
        title="[bold]Authentication[/bold]",
        border_style="dim",
        padding=(1, 1),
    )
