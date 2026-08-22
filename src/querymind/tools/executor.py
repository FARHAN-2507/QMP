"""Tool executor — validates arguments and runs tools.

The executor sits between the LLM's tool call request and the actual
tool execution. It enforces permission checks and catches errors.
"""

from __future__ import annotations

import logging
from typing import Any

from querymind.llm.client import ToolCall
from querymind.tools.base import Tool, ToolResult, ToolStatus
from querymind.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Validates and executes tool calls."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def execute_sync(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call synchronously.

        Resolves the tool from the registry, validates the arguments,
        and runs it. Catches all exceptions to prevent the agent loop
        from crashing.
        """
        tool = self._registry.resolve(tool_call.name)
        if tool is None:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Tool not found: {tool_call.name}",
            )

        try:
            if not self._validate_arguments(tool, tool_call.arguments):
                return ToolResult(
                    status=ToolStatus.VALIDATION_ERROR,
                    error=f"Invalid arguments for {tool_call.name}",
                )
        except Exception:
            logger.exception("Argument validation failed for %s", tool_call.name)
            return ToolResult(
                status=ToolStatus.VALIDATION_ERROR,
                error=f"Argument validation failed for {tool_call.name}",
            )

        logger.info("Executing tool: %s", tool_call.name)
        try:
            import asyncio

            result = asyncio.get_event_loop().run_until_complete(
                tool.execute(tool_call.arguments)
            )
        except Exception as e:
            logger.exception("Tool execution failed: %s", tool_call.name)
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Tool execution failed: {e}",
            )

        return result

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call asynchronously.

        Resolves the tool from the registry, validates the arguments,
        and runs it. Catches all exceptions to prevent the agent loop
        from crashing.
        """
        tool = self._registry.resolve(tool_call.name)
        if tool is None:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Tool not found: {tool_call.name}",
            )

        try:
            if not self._validate_arguments(tool, tool_call.arguments):
                return ToolResult(
                    status=ToolStatus.VALIDATION_ERROR,
                    error=f"Invalid arguments for {tool_call.name}",
                )
        except Exception:
            logger.exception("Argument validation failed for %s", tool_call.name)
            return ToolResult(
                status=ToolStatus.VALIDATION_ERROR,
                error=f"Argument validation failed for {tool_call.name}",
            )

        logger.info("Executing tool: %s", tool_call.name)
        try:
            result = await tool.execute(tool_call.arguments)
        except Exception as e:
            logger.exception("Tool execution failed: %s", tool_call.name)
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Tool execution failed: {e}",
            )

        return result

    @staticmethod
    def _validate_arguments(tool: Tool, arguments: dict[str, Any]) -> bool:
        """Basic argument validation against the tool's schema.

        Checks that required fields from the schema are present.
        Does not perform deep type validation (that's Pydantic's job
        inside the tool itself).
        """
        schema = tool.input_schema
        if not schema or schema.get("type") != "object":
            return True

        required = schema.get("required", [])
        for field in required:
            if field not in arguments:
                logger.warning(
                    "Missing required argument '%s' for tool %s",
                    field,
                    tool.name,
                )
                return False
        return True
