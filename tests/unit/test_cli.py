"""Tests for QueryMind CLI."""

from typer.testing import CliRunner

from querymind.cli.main import app

runner = CliRunner()


def test_cli_runs() -> None:
    result = runner.invoke(app, ["run"], input="exit\n")
    assert result.exit_code == 0
    assert "QueryMind" in result.output


def test_cli_help_command() -> None:
    result = runner.invoke(app, ["run"], input="help\nexit\n")
    assert result.exit_code == 0
    assert "Commands" in result.output
