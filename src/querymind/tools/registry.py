"""Tool registry — central catalog of available tools.

The registry holds tool instances by name. The agent loop queries it
to build the tool list sent to the LLM, and the executor resolves
tool calls against it.
"""

from __future__ import annotations

import logging
from typing import Any

from querymind.tools.base import Tool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry of available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool. Overwrites if name already exists."""
        if tool.name in self._tools:
            logger.warning("Overwriting existing tool: %s", tool.name)
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)

    def resolve(self, name: str) -> Tool | None:
        """Look up a tool by name. Returns None if not found."""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def list_names(self) -> list[str]:
        """Return all registered tool names."""
        return list(self._tools.keys())

    def to_definitions(self) -> list[dict[str, Any]]:
        """Convert all tools to OpenAI-compatible definitions."""
        return [t.to_definition() for t in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
