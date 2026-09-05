"""Ollama LLM provider implementation for local models.

Supports running models locally via Ollama for offline/private usage.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from querymind.llm.client import (
    ChatMessage,
    ChatResponse,
    LLMProvider,
    ToolCall,
    ToolDefinition,
)

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Ollama provider for local model inference.

    Uses Ollama's HTTP API for chat completions with tool calling support.
    """

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        base_url: str = "http://localhost:11434",
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        logger.info(
            "OllamaProvider initialized: model=%s, url=%s",
            model,
            base_url,
        )

    def validate_config(self) -> bool:
        """Check that Ollama server is reachable."""
        try:
            response = httpx.get(f"{self._base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        """Send a chat completion request to Ollama.

        Ollama doesn't have native tool calling, so we use prompt engineering
        to instruct the model to output JSON tool calls.
        """
        # Build the prompt with tool instructions
        system_prompt = self._build_system_prompt(messages, tools)

        # Convert messages to Ollama format
        ollama_messages = []
        for msg in messages:
            ollama_messages.append({
                "role": msg.role.value,
                "content": msg.content or "",
            })

        # If we have tools, add them to the system prompt
        if tools:
            tool_instructions = self._format_tools_for_prompt(tools)
            # Prepend tool instructions to the first system message
            if ollama_messages and ollama_messages[0]["role"] == "system":
                ollama_messages[0]["content"] += f"\n\n{tool_instructions}"
            else:
                ollama_messages.insert(0, {
                    "role": "system",
                    "content": f"You are a helpful assistant.\n\n{tool_instructions}",
                })

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

        logger.debug(
            "Ollama request: model=%s, messages=%d",
            self._model,
            len(messages),
        )

        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                f"{self._base_url}/api/chat",
                json=payload,
            )

        if response.status_code != 200:
            error_msg = response.text
            logger.error("Ollama error: %s", error_msg)
            raise ValueError(f"Ollama request failed: {error_msg}")

        data = response.json()
        message = data.get("message", {})
        content = message.get("content", "")

        # Parse tool calls from the response
        tool_calls = self._parse_tool_calls(content, tools)

        usage = {
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
            "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
        }

        return ChatResponse(
            content=content if not tool_calls else None,
            tool_calls=tool_calls,
            model=self._model,
            usage=usage,
            finish_reason="stop",
        )

    def _build_system_prompt(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None,
    ) -> str:
        """Build system prompt with tool instructions."""
        parts = ["You are a helpful API testing agent."]

        if tools:
            parts.append(self._format_tools_for_prompt(tools))

        return "\n\n".join(parts)

    def _format_tools_for_prompt(self, tools: list[ToolDefinition]) -> str:
        """Format tool definitions for the prompt."""
        tool_descriptions = []
        for tool in tools:
            params = json.dumps(tool.parameters, indent=2)
            tool_descriptions.append(
                f"TOOL: {tool.name}\n"
                f"DESCRIPTION: {tool.description}\n"
                f"PARAMETERS:\n{params}"
            )

        return (
            "AVAILABLE TOOLS:\n"
            "\n\n".join(tool_descriptions) +
            "\n\n"
            "To use a tool, respond with a JSON block like this:\n"
            "```tool_call\n"
            '{"name": "tool_name", "arguments": {"param": "value"}}\n'
            "```\n"
            "Only call one tool at a time. Wait for the result before calling another tool."
        )

    def _parse_tool_calls(
        self,
        content: str,
        tools: list[ToolDefinition] | None,
    ) -> list[ToolCall]:
        """Parse tool calls from the model's response."""
        if not tools:
            return []

        tool_calls = []
        import re

        # Look for tool_call blocks
        pattern = r'```tool_call\s*\n(.*?)\n\s*```'
        matches = re.findall(pattern, content, re.DOTALL)

        for i, match in enumerate(matches):
            try:
                call_data = json.loads(match)
                tool_name = call_data.get("name", "")
                arguments = call_data.get("arguments", {})

                # Validate tool exists
                valid_names = {t.name for t in tools}
                if tool_name in valid_names:
                    tool_calls.append(ToolCall(
                        id=f"call_{i}",
                        name=tool_name,
                        arguments=arguments,
                    ))
            except json.JSONDecodeError:
                logger.warning("Failed to parse tool call: %s", match)

        # Also try to parse JSON without code blocks
        if not tool_calls:
            # Try to find JSON with "name" key - handle nested objects
            # Look for patterns like: {"name": "xxx", "arguments": {...}}
            try:
                # Find all JSON-like objects that contain "name"
                brace_start = -1
                depth = 0
                for i, char in enumerate(content):
                    if char == '{':
                        if depth == 0:
                            brace_start = i
                        depth += 1
                    elif char == '}':
                        depth -= 1
                        if depth == 0 and brace_start >= 0:
                            candidate = content[brace_start:i+1]
                            if '"name"' in candidate:
                                try:
                                    call_data = json.loads(candidate)
                                    tool_name = call_data.get("name", "")
                                    arguments = call_data.get("arguments", {})
                                    valid_names = {t.name for t in tools}
                                    if tool_name in valid_names:
                                        tool_calls.append(ToolCall(
                                            id=f"call_{len(tool_calls)}",
                                            name=tool_name,
                                            arguments=arguments if isinstance(arguments, dict) else {},
                                        ))
                                        break  # Only take the first valid tool call
                                except json.JSONDecodeError:
                                    pass
                            brace_start = -1
            except Exception:
                pass

        return tool_calls

    def is_available(self) -> bool:
        """Check if Ollama server is running."""
        return self.validate_config()

    def list_models(self) -> list[str]:
        """List available models in Ollama."""
        try:
            response = httpx.get(f"{self._base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    def pull_model(self, model: str) -> bool:
        """Pull a model from Ollama registry."""
        try:
            response = httpx.post(
                f"{self._base_url}/api/pull",
                json={"name": model},
                timeout=300,
            )
            return response.status_code == 200
        except Exception:
            return False
