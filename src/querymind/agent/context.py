"""Agent context — builds what the LLM sees on each iteration.

Context assembles the system prompt and available tools from the
current state and configuration.
"""

from __future__ import annotations

from typing import Any

from querymind.llm.client import ChatMessage, ToolDefinition
from querymind.tools.registry import ToolRegistry

# Full prompt — used on first call to establish behavior
BOOTSTRAP_PROMPT = """\
You are QueryMind, an AI API testing agent.

CAPABILITIES:
- Send HTTP requests (GET, POST, PUT, PATCH, DELETE) to any URL
- Parse and execute curl commands (auto-extracts auth tokens)
- Import OpenAPI/Swagger specs to understand APIs
- Discover API endpoints by probing common paths
- Generate test cases from API definitions
- Run tests with assertions
- Generate HTML test reports
- Configure authentication for target APIs
- Answer general questions

HOW TO MAKE HTTP REQUESTS:
Use send_http_request tool with these EXACT parameters:

For GET:
{"method": "GET", "url": "https://api.com/endpoint"}

For POST:
{"method": "POST", "url": "https://api.com/endpoint", "body": {"key": "value"}}

For POST with JSON array body:
{"method": "POST", "url": "https://api.com/endpoint", "body": [{"id": 1, "name": "test"}]}

IMPORTANT: Keep the JSON simple. Do not add extra fields unless needed.

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

TEST GENERATION STRATEGY:
- For each endpoint, test happy path (valid input)
- Test error cases (missing required fields, invalid IDs)
- Test boundary conditions (empty strings, large payloads)
- Check response time is reasonable
- Verify response structure matches schema

TOKEN-SAVING MODE (for APIs with many endpoints):
- Use generate_tests_batch instead of generate_tests
- Call generate_tests_batch once per endpoint
- Process endpoints sequentially, run tests after each batch
- This keeps context small and saves tokens on free tier

REPORT GENERATION:
- After running tests, offer to generate a report
- Use generate_report tool with the test results
- Default save location: ~/Downloads/
- Reports are self-contained HTML files
- Ask user where to save, or use default

CURL COMMANDS:
- When user pastes a curl command, use run_curl tool
- run_curl automatically extracts and configures auth tokens
- It parses headers, method, URL, and body from the curl
- Auth tokens are auto-configured for the target API
- Example: "test this curl: curl -H 'Authorization: Bearer xxx' https://api.com/data"

RULES:
- Never guess. Use tools to verify.
- Be specific about what you found.
- If something looks wrong, explain why.
- Keep tool calls minimal and purposeful.

STOP IMMEDIATELY — Give your final answer when:
1. You have made 2+ tool calls (you have enough info)
2. You have the response from the API
3. You have test results
4. You have imported a spec or discovered endpoints
5. You already answered part of the question

IMPORTANT: After getting tool results, summarize and answer NOW.
Do NOT make more tool calls if you already have the information.
"""

# Compact prompt — used after first call (context already established)
WORKING_PROMPT = """\
You are QueryMind, an AI API testing agent.
Be concise. Use tools to investigate, then report findings.

RULES:
- Never guess. Use tools to verify.
- Be specific about what you found.
- Keep tool calls minimal and purposeful.
- After 1-2 tool calls, STOP and give your final answer.
"""

# Tool sets for different phases — reduces token usage
TOOL_SETS: dict[str, list[str]] = {
    "setup": [
        "configure_auth",
        "list_auth",
        "clear_auth",
        "import_openapi",
        "discover_api",
    ],
    "testing": [
        "send_request",
        "run_test",
        "generate_tests",
        "generate_tests_batch",
        "run_smoke_tests",
    ],
    "reporting": [
        "generate_report",
    ],
    "full": [],  # Empty means all tools
}


class AgentContext:
    """Builds the prompt and tool list for each LLM call."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        system_prompt: str | None = None,
        auth_provider: Any | None = None,
    ) -> None:
        self._tool_registry = tool_registry
        self._bootstrap_prompt = system_prompt or BOOTSTRAP_PROMPT
        self._auth_provider = auth_provider
        self._current_phase = "full"
        self._call_count = 0

    def set_phase(self, phase: str) -> None:
        """Set the current tool phase to filter tool definitions."""
        if phase in TOOL_SETS:
            self._current_phase = phase

    def get_system_prompt(self) -> str:
        """Return the system prompt with auth summary.

        Uses compact working prompt after first call to save tokens.
        """
        prompt = WORKING_PROMPT if self._call_count > 0 else self._bootstrap_prompt

        if self._auth_provider:
            auth_summary = self._auth_provider.get_auth_summary()
            if auth_summary and auth_summary != "No authentication configured.":
                prompt += f"\n\n{auth_summary}"
        return prompt

    def increment_call_count(self) -> None:
        """Track number of LLM calls for prompt consolidation."""
        self._call_count += 1

    def get_tool_definitions(self) -> list[ToolDefinition]:
        """Return tool definitions for the LLM.

        Filters tools based on current phase to save tokens.
        """
        all_tools = self._tool_registry.list_tools()

        # Filter by phase if not in full mode
        if self._current_phase != "full":
            allowed_names = TOOL_SETS.get(self._current_phase, [])
            if allowed_names:
                tools = [t for t in all_tools if t.name in allowed_names]
                return [
                    ToolDefinition(
                        name=t.name,
                        description=t.description,
                        parameters=t.input_schema,
                    )
                    for t in tools
                ]

        # Full mode — return all tools
        return [
            ToolDefinition(
                name=t.name,
                description=t.description,
                parameters=t.input_schema,
            )
            for t in all_tools
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
