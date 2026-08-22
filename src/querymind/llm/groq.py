"""Groq LLM provider implementation with round-robin key rotation."""

from __future__ import annotations

import itertools
import json
import logging
from typing import Any

from groq import (
    AsyncGroq,  # type: ignore[import-untyped]  # pyright: ignore[reportMissingModuleSource]
)

from querymind.llm.client import (
    ChatMessage,
    ChatResponse,
    LLMProvider,
    ToolCall,
    ToolDefinition,
)

logger = logging.getLogger(__name__)


class GroqProvider(LLMProvider):
    """Groq API provider with round-robin API key rotation.

    Supports multiple API keys for higher throughput. Keys are rotated
    on each request in round-robin fashion. If only one key is provided,
    it behaves like a standard single-key provider.
    """

    def __init__(self, api_keys: list[str], model: str) -> None:
        self._api_keys = api_keys
        self._model = model
        self._clients: list[AsyncGroq] = [
            AsyncGroq(api_key=key) for key in api_keys
        ]
        self._key_cycle: Any = (
            itertools.cycle(range(len(api_keys))) if api_keys else iter([])
        )
        logger.info(
            "GroqProvider initialized with %d API key(s), model=%s",
            len(api_keys),
            model,
        )

    def validate_config(self) -> bool:
        """Check that at least one API key is set."""
        if not self._api_keys:
            logger.warning("No Groq API keys configured")
            return False
        return True

    def _next_client(self) -> AsyncGroq:
        """Get the next client in round-robin order."""
        idx = next(self._key_cycle)
        return self._clients[idx]  # pyright: ignore[reportUnknownVariableType]

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        """Send a chat completion request to Groq.

        Rotates through API keys on each call for load distribution.
        """
        if not self.validate_config():
            raise ValueError("Groq provider is not configured. Set GROQ_API_KEYS.")

        client = self._next_client()

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [m.to_provider_dict() for m in messages],
            "temperature": temperature,
        }

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        if tools:
            payload["tools"] = [t.to_provider_dict() for t in tools]
            payload["tool_choice"] = "auto"

        logger.debug(
            "Groq request: model=%s, messages=%d", self._model, len(messages)
        )

        # Groq SDK lacks type stubs; responses are untyped.
        response = await client.chat.completions.create(**payload)  # type: ignore[misc]  # pyright: ignore[reportUnknownMemberType]

        choice = response.choices[0]  # type: ignore[union-attr]  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType]
        message = choice.message  # type: ignore[union-attr]  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType]

        tool_calls: list[ToolCall] = []
        if message.tool_calls:  # type: ignore[union-attr]  # pyright: ignore[reportUnknownMemberType]
            for tc in message.tool_calls:  # type: ignore[union-attr]  # pyright: ignore[reportUnknownMemberType]
                args: dict[str, Any] = {}
                if tc.function.arguments:  # pyright: ignore[reportUnknownMemberType]
                    try:
                        args = json.loads(tc.function.arguments)  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType]
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(
                            "Failed to parse tool call arguments: %s",
                            tc.function.arguments,  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType]
                        )
                tool_calls.append(
                    ToolCall(
                        id=tc.id,  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType]
                        name=tc.function.name,  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType]
                        arguments=args,
                    )
                )

        usage_dict: dict[str, int] = {}
        if response.usage:  # type: ignore[union-attr]  # pyright: ignore[reportUnknownMemberType]
            usage_dict = {
                "prompt_tokens": response.usage.prompt_tokens or 0,  # type: ignore[union-attr]  # pyright: ignore[reportUnknownMemberType]
                "completion_tokens": response.usage.completion_tokens or 0,  # type: ignore[union-attr]  # pyright: ignore[reportUnknownMemberType]
                "total_tokens": response.usage.total_tokens or 0,  # type: ignore[union-attr]  # pyright: ignore[reportUnknownMemberType]
            }

        return ChatResponse(
            content=message.content,  # type: ignore[arg-type]  # pyright: ignore[reportUnknownMemberType]
            tool_calls=tool_calls,
            model=response.model or self._model,  # type: ignore[union-attr]  # pyright: ignore[reportUnknownMemberType]
            usage=usage_dict,
            finish_reason=choice.finish_reason or "",  # type: ignore[union-attr]  # pyright: ignore[reportUnknownMemberType]
        )
