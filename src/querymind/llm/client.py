"""LLM provider abstraction layer.

The LLM module defines a provider-agnostic interface for communicating
with language models. The application code depends on `LLMProvider`, not
on any concrete SDK.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Role(StrEnum):
    """Message role."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ChatMessage(BaseModel):
    """A single message in a conversation."""

    role: Role
    content: str | None = None
    tool_call_id: str | None = None
    name: str | None = None

    def to_provider_dict(self) -> dict[str, Any]:
        """Convert to a dict suitable for LLM provider APIs."""
        d: dict[str, Any] = {"role": self.role.value}
        if self.content is not None:
            d["content"] = self.content
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            d["name"] = self.name
        return d


class ToolDefinition(BaseModel):
    """Definition of a tool the LLM can call."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)

    def to_provider_dict(self) -> dict[str, Any]:
        """Convert to OpenAI-compatible tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolCall(BaseModel):
    """A tool call requested by the LLM."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """Response from the LLM provider."""

    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)  # pyright: ignore[reportUnknownVariableType]
    model: str = ""
    usage: dict[str, int] = Field(default_factory=dict)
    finish_reason: str = ""

    @property
    def has_tool_calls(self) -> bool:
        """Check if the response contains tool calls."""
        return len(self.tool_calls) > 0


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All providers must implement `chat`. The rest of the application
    depends only on this interface, making it easy to swap providers.
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        """Send a chat completion request.

        Args:
            messages: Conversation history.
            tools: Optional tool definitions the model may call.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in the response.

        Returns:
            A structured ChatResponse.
        """

    @abstractmethod
    def validate_config(self) -> bool:
        """Validate that the provider is properly configured.

        Returns:
            True if the provider is ready to use.
        """
