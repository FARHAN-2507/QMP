"""Agent state — tracks the conversation and execution progress.

The agent loop reads and mutates state on every iteration.
State is the single source of truth for "where are we in this task".
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from querymind.llm.client import ChatMessage, Role, ToolCall


class AgentStatus(StrEnum):
    """Current status of the agent."""

    IDLE = "idle"
    RUNNING = "running"
    WAITING_FOR_TOOL = "waiting_for_tool"
    COMPLETED = "completed"
    ERROR = "error"
    MAX_ITERATIONS = "max_iterations"
    CANCELLED = "cancelled"


class ToolCallRecord(BaseModel):
    """Record of a single tool call made by the agent."""

    tool_call: ToolCall
    result_content: str
    is_error: bool = False


class AgentState(BaseModel):
    """Mutable state for a single agent run.

    The agent loop reads this on every iteration and updates it
    after each LLM call and tool execution.
    """

    messages: list[ChatMessage] = Field(default_factory=list)  # pyright: ignore[reportUnknownVariableType]
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)  # pyright: ignore[reportUnknownVariableType]
    iteration: int = 0
    status: AgentStatus = AgentStatus.IDLE
    final_response: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_user_message(self, content: str) -> None:
        """Append a user message."""
        self.messages.append(ChatMessage(role=Role.USER, content=content))

    def add_system_message(self, content: str) -> None:
        """Prepend a system message."""
        self.messages.insert(0, ChatMessage(role=Role.SYSTEM, content=content))

    def add_assistant_message(self, content: str) -> None:
        """Append an assistant message."""
        self.messages.append(ChatMessage(role=Role.ASSISTANT, content=content))

    def add_tool_result(self, tool_call_id: str, content: str, name: str) -> None:
        """Append a tool result message."""
        self.messages.append(
            ChatMessage(role=Role.TOOL, content=content, tool_call_id=tool_call_id, name=name)
        )

    def record_tool_call(self, record: ToolCallRecord) -> None:
        """Record a completed tool call."""
        self.tool_calls.append(record)

    def increment_iteration(self) -> None:
        """Bump the iteration counter."""
        self.iteration += 1

    def set_completed(self, response: str) -> None:
        """Mark the agent as finished successfully."""
        self.status = AgentStatus.COMPLETED
        self.final_response = response

    def set_error(self, error: str) -> None:
        """Mark the agent as errored."""
        self.status = AgentStatus.ERROR
        self.error = error

    def set_max_iterations(self) -> None:
        """Mark the agent as stopped due to iteration limit."""
        self.status = AgentStatus.MAX_ITERATIONS
        self.final_response = (
            f"Agent stopped after {self.iteration} iterations without a final answer."
        )

    def set_cancelled(self) -> None:
        """Mark the agent as cancelled."""
        self.status = AgentStatus.CANCELLED
