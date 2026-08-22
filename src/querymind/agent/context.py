"""Agent context — builds what the LLM sees on each iteration.

Context assembles the system prompt and available tools from the
current state and configuration.
"""

from __future__ import annotations

from querymind.llm.client import ChatMessage, ToolDefinition
from querymind.tools.registry import ToolRegistry

DEFAULT_SYSTEM_PROMPT = """\
You are QueryMind, an AI-powered API testing agent and helpful assistant.

You can:
- Answer general questions and have normal conversations
- Help users test, explore, and analyze APIs
- Use tools to send HTTP requests, inspect APIs, and run tests

When the user asks you something:
- If it's a general question, answer directly and helpfully
- If it involves an API, use your tools to investigate
- If you need more information, ask the user

When testing APIs, reason step by step:
1. Understand what they want to test
2. Use tools to explore the API
3. Execute tests
4. Analyze the results
5. Report your findings

Be friendly, concise, and helpful. You can chat about anything \
while being especially good at API testing.
"""


class AgentContext:
    """Builds the prompt and tool list for each LLM call."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        system_prompt: str | None = None,
    ) -> None:
        self._tool_registry = tool_registry
        self._system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    def get_system_prompt(self) -> str:
        """Return the system prompt."""
        return self._system_prompt

    def get_tool_definitions(self) -> list[ToolDefinition]:
        """Return tool definitions for the LLM."""
        return [
            ToolDefinition(
                name=t.name,
                description=t.description,
                parameters=t.input_schema,
            )
            for t in self._tool_registry.list_tools()
        ]

    def build_messages(
        self,
        messages: list[ChatMessage],
    ) -> list[ChatMessage]:
        """Build the full message list for the LLM.

        Prepends the system prompt if the first message is not already
        a system message.
        """
        result: list[ChatMessage] = []

        has_system = messages and messages[0].role.value == "system"
        if not has_system:
            result.append(ChatMessage(role="system", content=self._system_prompt))  # type: ignore[arg-type]

        result.extend(messages)
        return result
