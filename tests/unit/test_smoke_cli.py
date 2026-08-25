"""CLI wiring tests for smoke subcommand (existing REPL preserved)."""

from __future__ import annotations

from typer.testing import CliRunner

from querymind.cli.main import app

runner = CliRunner()


def test_smoke_help() -> None:
    result = runner.invoke(app, ["smoke", "--help"])
    assert result.exit_code == 0
    assert "Smoke" in result.output or "smoke" in result.output.lower()


def test_default_cli_still_interactive() -> None:
    """Regression: bare querymind still launches agent REPL (not smoke)."""
    result = runner.invoke(app, input="exit\n", env={"GROQ_API_KEYS": "test-key-for-cli"})
    assert "QueryMind" in result.output
    # With a key present, REPL starts and exit succeeds
    assert result.exit_code == 0
    assert "API SMOKE TEST" not in result.output
