"""Tool abstraction layer.

Every tool in QueryMind implements the `Tool` interface. The agent
never executes tools directly — it requests them through the tool
registry and executor.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ToolStatus(StrEnum):
    """Status of a tool execution."""

    SUCCESS = "success"
    ERROR = "error"
    PERMISSION_DENIED = "permission_denied"
    VALIDATION_ERROR = "validation_error"


class ToolResult(BaseModel):
    """Structured result from a tool execution."""

    status: ToolStatus
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.status == ToolStatus.SUCCESS

    def to_content_string(self) -> str:
        """Serialize to a string the LLM can read."""
        if self.status == ToolStatus.SUCCESS:
            if isinstance(self.data, str):
                return self.data
            return str(self.data)
        return f"Error ({self.status}): {self.error or 'Unknown error'}"


class Tool(ABC):
    """Base class for all QueryMind tools.

    Subclasses must define name, description, input_schema, and execute.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name the LLM will use to call this tool."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does."""

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """JSON Schema for the tool's input parameters."""

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        """Execute the tool with the given arguments.

        Args:
            arguments: Validated input arguments from the LLM.

        Returns:
            A structured ToolResult.
        """

    def to_definition(self) -> dict[str, Any]:
        """Convert to OpenAI-compatible tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }
