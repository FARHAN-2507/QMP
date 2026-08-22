"""Agent context — builds what the LLM sees on each iteration.

Context assembles the system prompt and available tools from the
current state and configuration.
"""

from __future__ import annotations

from querymind.llm.client import ChatMessage, ToolDefinition
from querymind.tools.registry import ToolRegistry

DEFAULT_SYSTEM_PROMPT = """\
You are QueryMind, an AI API testing agent.

CAPABILITIES:
- Send HTTP requests (GET, POST, PUT, PATCH, DELETE) to any URL
- Inspect API responses (status, headers, body)
- Test APIs for correctness, security, and edge cases
- Answer general questions

BEHAVIOR:
- For general questions: answer directly, be concise
- For API testing: use tools to investigate, then report findings
- Keep responses short and clear
- Use markdown formatting in your final answer

WHEN TESTING AN API:
1. First check if the endpoint is reachable
2. Test with valid input
3. Test with invalid input (missing fields, wrong types)
4. Check error handling
5. Report what you found

RULES:
- Never guess. Use tools to verify.
- Be specific about what you found.
- If something looks wrong, explain why.
- Keep tool calls minimal and purposeful.
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
