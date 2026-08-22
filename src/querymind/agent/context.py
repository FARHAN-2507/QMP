"""Agent context — builds what the LLM sees on each iteration.

Context assembles the system prompt and available tools from the
current state and configuration.
"""

from __future__ import annotations

from typing import Any

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
- Generate HTML test reports
- Configure authentication for target APIs
- Answer general questions

BEHAVIOR:
- For general questions: answer directly, be concise
- For API testing: use tools to investigate, then report findings
- Keep responses short and clear
- Use markdown formatting in your final answer

AUTHENTICATION:
- Use configure_auth to set up authentication for target APIs
- Supported types: API key, Bearer token, Basic auth, OAuth 2.0
- Once configured, auth headers are automatically applied to all requests
- Use list_auth to see configured authentication
- Use clear_auth to remove authentication for an API
- Do NOT manually include Authorization headers when auth is configured

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

REPORT GENERATION:
- After running tests, offer to generate a report
- Use generate_report tool with the test results
- Default save location: ~/Downloads/
- Reports are self-contained HTML files
- Ask user where to save, or use default

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
        auth_provider: Any | None = None,
    ) -> None:
        self._tool_registry = tool_registry
        self._system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self._auth_provider = auth_provider

    def get_system_prompt(self) -> str:
        """Return the system prompt with auth summary."""
        prompt = self._system_prompt
        if self._auth_provider:
            auth_summary = self._auth_provider.get_auth_summary()
            if auth_summary and auth_summary != "No authentication configured.":
                prompt += f"\n\n{auth_summary}"
        return prompt

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
            result.append(ChatMessage(role="system", content=self.get_system_prompt()))  # type: ignore[arg-type]

        result.extend(messages)
        return result
