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
from querymind.cli.smoke import smoke_command
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
    invoke_without_command=True,
)
console = Console(theme=theme)

app.command("smoke")(smoke_command)


@app.command("set-key")
def set_api_key(
    key: str = typer.Argument(..., help="Groq API key (starts with gsk_)"),
    model: str = typer.Option(None, "--model", "-m", help="Model to use"),
) -> None:
    """Set Groq API key for QueryMind."""
    import json
    from pathlib import Path

    config_path = Path(settings.data_dir).expanduser() / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing config
    config: dict[str, str] = {}
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)

    # Update keys (append if multiple)
    existing = config.get("groq_api_keys", "")
    keys: list[str] = [k.strip() for k in existing.split(",") if k.strip()]
    if key not in keys:
        keys.append(key)
    config["groq_api_keys"] = ",".join(keys)

    if model:
        config["groq_model"] = model

    # Save
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    console.print(f"[green]✓ API key saved to {config_path}[/green]")
    console.print(f"[dim]Keys configured: {len(keys)}[/dim]")


@app.command("show-key")
def show_api_key() -> None:
    """Show configured API keys (masked)."""
    keys = settings.groq_api_key_list
    if not keys:
        console.print("[yellow]No API keys configured.[/yellow]")
        console.print("[dim]Run: querymind set-key <your-groq-api-key>[/dim]")
        return

    console.print(f"[green]Configured keys: {len(keys)}[/green]")
    for i, k in enumerate(keys):
        masked = k[:8] + "..." + k[-4:] if len(k) > 12 else "***"
        console.print(f"  {i+1}. {masked}")


@app.command("remove-key")
def remove_api_key(
    index: int = typer.Argument(..., help="Key number to remove (from show-key)"),
) -> None:
    """Remove an API key by index."""
    import json
    from pathlib import Path

    keys = settings.groq_api_key_list
    if not keys:
        console.print("[yellow]No API keys configured.[/yellow]")
        return

    if index < 1 or index > len(keys):
        console.print(f"[red]Invalid index. Use 1-{len(keys)}[/red]")
        return

    removed = keys.pop(index - 1)

    # Save
    config_path = Path(settings.data_dir).expanduser() / "config.json"
    config: dict[str, str] = {}
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)

    config["groq_api_keys"] = ",".join(keys)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    console.print(f"[green]✓ Removed key {removed[:8]}...[/green]")


@app.command("run")
def run_command(
    ollama: bool = typer.Option(False, "--ollama", "-o", help="Use local Ollama model"),
    model: str = typer.Option(None, "--model", "-m", help="Model to use"),
) -> None:
    """Launch QueryMind interactive session."""
    run_interactive(use_ollama=ollama, model_override=model)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    ollama: bool = typer.Option(False, "--ollama", "-o", help="Use local Ollama model"),
    model: str = typer.Option(None, "--model", "-m", help="Model to use"),
) -> None:
    """QueryMind - AI API Testing Agent."""
    if ctx.invoked_subcommand is None:
        run_interactive(use_ollama=ollama, model_override=model)


def make_runtime(
    on_step: object = None,
    use_ollama: bool = False,
    model_override: str | None = None,
) -> AgentRuntime:
    """Create an AgentRuntime with the configured LLM provider."""
    if use_ollama:
        from querymind.llm.ollama import OllamaProvider
        model = model_override or settings.ollama_model
        llm = OllamaProvider(model=model, base_url=settings.ollama_url)
        if not llm.is_available():
            console.print(
                "[red]Ollama is not running. Start it with: ollama serve[/red]"
            )
            raise typer.Exit(1)
        console.print(f"[green]Using local model: {model}[/green]")
    else:
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
    from querymind.agent.preprocessor import detect_request_type, parse_curl, parse_powershell
    from querymind.tools.curl import parse_curl as parse_curl_tool

    console.print()

    # Pre-process: handle curl and PowerShell commands directly
    request_info = detect_request_type(user_input)

    if request_info["type"] in ("curl", "powershell"):
        # Parse command
        if request_info["type"] == "curl":
            console.print("[dim]Detected curl command — executing directly...[/dim]")
            parsed = parse_curl(request_info["details"])
        else:
            console.print("[dim]Detected PowerShell command — executing directly...[/dim]")
            parsed = parse_powershell(request_info["details"])

        if parsed["url"]:
            url = parsed["url"]
            method = parsed["method"]
            headers = parsed["headers"]

            # Auto-configure auth
            if parsed["auth_type"] and runtime.auth_provider:
                from querymind.security.models import AuthConfig, AuthType
                url_parts = url.split("/")
                base_url = "/".join(url_parts[:3]) if len(url_parts) >= 3 else url
                if parsed["auth_type"] == "bearer":
                    config = AuthConfig(
                        type=AuthType.BEARER,
                        base_url=base_url,
                        token=parsed["auth_value"],
                    )
                    runtime.auth_provider.set_auth(base_url=base_url, config=config)
                    console.print(f"[green]✓ Auth configured: Bearer token for {base_url}[/green]")

            # Apply stored auth
            headers = runtime.auth_provider.apply_auth(headers, url)

            # Make request
            try:
                import httpx
                async with httpx.AsyncClient(
                    timeout=30, follow_redirects=True, verify=False
                ) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        json=parsed["body"],
                    )

                # Show response
                status_code = response.status_code
                icon = "[green]✓[/green]" if status_code < 400 else "[red]✗[/red]"
                console.print(f"\n{icon} [bold]{method} {url}[/bold] → {status_code}\n")

                # Try to format JSON response
                try:
                    data = response.json()
                    import json
                    formatted = json.dumps(data, indent=2, ensure_ascii=False)
                    if len(formatted) > 2000:
                        formatted = formatted[:2000] + "\n... (truncated)"
                    console.print(Panel(formatted, title="Response", border_style="dim"))
                except Exception:
                    text = response.text
                    if len(text) > 2000:
                        text = text[:2000] + "\n... (truncated)"
                    console.print(Panel(text, title="Response", border_style="dim"))

            except Exception as e:
                console.print(f"[red]Request failed:[/red] {e}")
        else:
            console.print("[red]Could not parse command[/red]")
        console.print()
        return

    if request_info["type"] == "simple_url":
        # Simple URL - test intelligently
        url = request_info["details"]["url"]
        console.print(f"[bold]Testing endpoint:[/bold] {url}\n")

        # Apply stored auth
        headers: dict[str, str] = {}
        headers = runtime.auth_provider.apply_auth(headers, url)

        try:
            import httpx
            async with httpx.AsyncClient(
                timeout=30, follow_redirects=True, verify=False
            ) as client:
                # First try GET
                console.print("[dim]Testing GET...[/dim]")
                response = await client.get(url, headers=headers)
                status_code = response.status_code
                icon = "[green]✓[/green]" if status_code < 400 else "[red]✗[/red]"
                console.print(f"  {icon} GET → {status_code}")

                # Show response body
                data = None
                try:
                    data = response.json()
                    import json
                    formatted = json.dumps(data, indent=2, ensure_ascii=False)
                    if len(formatted) > 2000:
                        formatted = formatted[:2000] + "\n... (truncated)"
                    console.print(Panel(formatted, title="GET Response", border_style="dim"))
                except Exception:
                    text = response.text
                    if len(text) > 2000:
                        text = text[:2000] + "\n... (truncated)"
                    console.print(Panel(text, title="GET Response", border_style="dim"))

                # Test POST with body from GET response
                if status_code == 200 and data:
                    # Build POST body from response
                    post_body = None
                    if isinstance(data, list) and len(data) > 0:
                        # Use first item, remove id and dates
                        post_body = {k: v for k, v in data[0].items()
                                    if k not in ("id", "createdAt", "updatedAt")}
                    elif isinstance(data, dict):
                        # Use same structure, remove id and dates
                        post_body = {k: v for k, v in data.items()
                                    if k not in ("id", "createdAt", "updatedAt")}

                    if post_body:
                        console.print(f"\n[dim]Testing POST...[/dim]")
                        console.print(f"  [dim]Body: {json.dumps(post_body)[:100]}[/dim]")
                        response = await client.post(url, headers=headers, json=post_body)
                        status_code = response.status_code
                        icon = "[green]✓[/green]" if status_code < 400 else "[red]✗[/red]"
                        console.print(f"  {icon} POST → {status_code}")
                        if status_code < 400:
                            try:
                                resp_data = response.json()
                                formatted = json.dumps(resp_data, indent=2, ensure_ascii=False)
                                console.print(Panel(formatted, title="POST Response", border_style="dim"))
                            except Exception:
                                pass

        except Exception as e:
            console.print(f"[red]Request failed:[/red] {e}")

        console.print()
        return

    # Complex request - use LLM agent with visible tool calls
    console.print("[bold cyan]Agent thinking...[/bold cyan]\n")

    # Create a streaming callback to show tool calls in real-time
    def on_tool_call(tool_name: str, arguments: dict[str, Any]) -> None:
        tool_label = tool_name.replace("_", " ").title()
        args_str = str(arguments)[:80]
        console.print(f"  [dim]🔧 Calling:[/dim] [bold]{tool_label}[/bold] {args_str}")

    # Run agent with visible steps
    state = await runtime.run(user_input, on_tool_call=on_tool_call)

    # Show tool call history
    if state.tool_calls:
        console.print("\n[bold]Tool calls:[/bold]")
        for tc in state.tool_calls:
            if not tc.is_error:
                icon = "[green]✓[/green]"
            else:
                icon = "[red]✗[/red]"

            # Format tool name
            tool_name = tc.tool_call.name.replace("_", " ").title()

            # Format arguments
            args = tc.tool_call.arguments
            if "url" in args:
                detail = f"{args.get('method', 'GET')} {args['url']}"
            elif "file_path" in args:
                detail = args["file_path"]
            elif "spec_url" in args:
                detail = args["spec_url"]
            elif "base_url" in args:
                detail = args["base_url"]
            else:
                detail = str(args)[:60]

            console.print(f"  {icon} [bold]{tool_name}[/bold] — {detail}")

    console.print()

    # Show final response
    if state.status == AgentStatus.COMPLETED and state.final_response:
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
    # Exit commands
    if command in ("exit", "quit", "q", "/exit"):
        console.print("[dim]Goodbye.[/dim]")
        return True

    # Clear
    if command in ("clear", "/clear"):
        runtime.reset()
        console.clear()
        print_welcome(runtime)
        return False

    # Sessions
    if command in ("sessions", "/sessions"):
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

    if command in ("new", "/new"):
        new_id = runtime.new_session()
        console.print(f"[green]✓ New session: {new_id}[/green]")
        return False

    # Auth commands
    if command in ("auth", "auth list", "/auth"):
        show_auth(runtime)
        return False

    if command.startswith("auth set ") or command.startswith("/auth set "):
        args = command.split(" ", 2)[-1] if command.startswith("/auth") else command[9:]
        handle_auth_set(runtime, args)
        return False

    if command.startswith("auth clear") or command.startswith("/auth clear"):
        args = command.split(" ", 2)[-1] if command.startswith("/auth") else command[10:]
        handle_auth_clear(runtime, args.strip())
        return False

    # API Key commands
    if command.startswith("/setkey "):
        key = command.split(" ", 1)[1].strip()
        _handle_set_key(key)
        return False

    if command in ("/showkey", "/keys"):
        _handle_show_key()
        return False

    if command.startswith("/removekey "):
        try:
            index = int(command.split(" ", 1)[1].strip())
            _handle_remove_key(index)
        except ValueError:
            console.print("[red]Usage: /removekey <number>[/red]")
        return False

    # Help
    if command in ("help", "/help", "/?"):
        console.print(create_help_panel())
        return False

    return False


def _handle_set_key(key: str) -> None:
    """Handle /setkey command in interactive mode."""
    import json
    from pathlib import Path

    config_path = Path(settings.data_dir).expanduser() / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config: dict[str, str] = {}
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)

    existing = config.get("groq_api_keys", "")
    keys: list[str] = [k.strip() for k in existing.split(",") if k.strip()]
    if key not in keys:
        keys.append(key)
    config["groq_api_keys"] = ",".join(keys)

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    console.print("[green]✓ API key saved![/green]")
    console.print(f"[dim]Keys configured: {len(keys)}[/dim]")
    console.print("[dim]Restart QueryMind to use the new key.[/dim]")


def _handle_show_key() -> None:
    """Handle /showkey command in interactive mode."""
    keys = settings.groq_api_key_list
    if not keys:
        console.print("[yellow]No API keys configured.[/yellow]")
        console.print("[dim]Run: /setkey <your-groq-api-key>[/dim]")
        return

    console.print(f"[green]Configured keys: {len(keys)}[/green]")
    for i, k in enumerate(keys):
        masked = k[:8] + "..." + k[-4:] if len(k) > 12 else "***"
        console.print(f"  {i+1}. {masked}")


def _handle_remove_key(index: int) -> None:
    """Handle /removekey command in interactive mode."""
    import json
    from pathlib import Path

    keys = settings.groq_api_key_list
    if not keys:
        console.print("[yellow]No API keys configured.[/yellow]")
        return

    if index < 1 or index > len(keys):
        console.print(f"[red]Invalid index. Use 1-{len(keys)}[/red]")
        return

    removed = keys.pop(index - 1)

    config_path = Path(settings.data_dir).expanduser() / "config.json"
    config: dict[str, str] = {}
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)

    config["groq_api_keys"] = ",".join(keys)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    console.print(f"[green]✓ Removed key {removed[:8]}...[/green]")


def run_interactive(use_ollama: bool = False, model_override: str | None = None) -> None:
    """Run the interactive CLI session."""
    console.clear()

    if not use_ollama and not settings.groq_api_key_list:
        console.print()
        console.print(Panel(
            Text.from_markup(
                "[bold yellow]No API key configured![/bold yellow]\n\n"
                "QueryMind uses [bold]Groq[/bold] for AI-powered testing.\n\n"
                "Get your free API key (takes 30 seconds):\n"
                "[cyan]https://console.groq.com/keys[/cyan]\n\n"
                "Then run:\n"
                "[green]querymind set-key gsk_your_key_here[/green]\n\n"
                "[dim]Or use local model:[/dim]\n"
                "[green]querymind --ollama[/green]\n\n"
                "[dim]Free tier includes 30 requests/minute — plenty for testing.[/dim]"
            ),
            title="[bold]Welcome to QueryMind[/bold]",
            border_style="cyan",
        ))
        console.print()
        raise typer.Exit(1)

    runtime = make_runtime(
        on_step=step_printer,
        use_ollama=use_ollama,
        model_override=model_override,
    )

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


if __name__ == "__main__":
    app()
