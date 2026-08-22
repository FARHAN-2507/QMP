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
- Import OpenAPI/Swagger specs to understand APIs
- Discover API endpoints by probing common paths
- Generate test cases from API definitions
- Run tests with assertions (status code, headers, JSON properties, response time)
- Answer general questions

BEHAVIOR:
- For general questions: answer directly, be concise
- For API testing: use tools to investigate, then report findings
- Keep responses short and clear
- Use markdown formatting in your final answer

WORKFLOW FOR TESTING AN API:
1. If you have an OpenAPI spec URL, import it with import_openapi
2. If user gives an endpoint URL, try to find Swagger first:
   - Extract base URL (everything before the first / after domain)
   - Try: {baseUrl}/swagger/v1/swagger.json
   - Try: {baseUrl}/swagger.json
   - Try: {baseUrl}/api-docs
3. If Swagger found → import it, then generate tests
4. If no Swagger → use discover_api to find endpoints
5. Generate test cases with generate_tests
6. Run tests with run_test or let generate_tests run them
7. Report results with clear pass/fail summary

SWAGGER DISCOVERY EXAMPLES:
- User: "test https://localhost:7067/WeatherForecast"
  → Base: https://localhost:7067
  → Try: https://localhost:7067/swagger/v1/swagger.json
- User: "check http://api.example.com/v1/users"
  → Base: http://api.example.com
  → Try: http://api.example.com/swagger.json

TEST GENERATION STRATEGY:
- For each endpoint, test happy path (valid input)
- Test error cases (missing required fields, invalid IDs)
- Test boundary conditions (empty strings, large payloads)
- Check response time is reasonable
- Verify response structure matches schema

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
