"""Tests for QueryMind CLI."""

from typer.testing import CliRunner

from querymind.cli.main import app, format_tool_call

runner = CliRunner()


def test_cli_runs() -> None:
    result = runner.invoke(app, input="exit\n")
    assert result.exit_code == 0
    assert "QueryMind" in result.output


def test_cli_help_command() -> None:
    result = runner.invoke(app, input="help\nexit\n")
    assert result.exit_code == 0
    assert "Commands" in result.output


def test_format_tool_call_http() -> None:
    result = format_tool_call("send_http_request", {"method": "GET", "url": "http://test"})
    assert result == "GET http://test"


def test_format_tool_call_env() -> None:
    result = format_tool_call("get_current_test_environment", {})
    assert "Checking" in result
