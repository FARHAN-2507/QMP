"""Agent loop — the heart of QueryMind.

The loop repeatedly:
1. Sends messages to the LLM
2. If the LLM requests a tool, executes it and feeds the result back
3. If the LLM responds with text, returns the final answer

It enforces iteration limits, handles errors, and never runs forever.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from querymind.agent.context import AgentContext
from querymind.agent.state import AgentState, AgentStatus, ToolCallRecord
from querymind.llm.client import (
    ChatMessage,
    LLMProvider,
    Role,
    ToolCall,
)
from querymind.tools.base import ToolResult
from querymind.tools.executor import ToolExecutor

logger = logging.getLogger(__name__)

# Type alias for a callback that receives (iteration, tool_name, result)
AgentStepCallback = Callable[[int, str, ToolResult], None] | None


class AgentLoop:
    """Runs the agent's reasoning loop.

    The loop continues until:
    - The LLM responds with a final text answer (no tool calls)
    - The maximum iteration count is reached
    - An unrecoverable error occurs
    """

    def __init__(
        self,
        llm: LLMProvider,
        context: AgentContext,
        executor: ToolExecutor,
        max_iterations: int = 20,
        on_step: AgentStepCallback = None,
        max_context_messages: int = 30,
    ) -> None:
        self._llm = llm
        self._context = context
        self._executor = executor
        self._max_iterations = max_iterations
        self._on_step = on_step
        self._max_context_messages = max_context_messages

    async def run(self, state: AgentState) -> AgentState:
        """Execute the agent loop from the current state.

        Mutates and returns the state.
        """
        state.status = AgentStatus.RUNNING

        while state.iteration < self._max_iterations:
            state.increment_iteration()
            logger.debug("Iteration %d", state.iteration)

            # Trim context before each LLM call to save tokens
            self._trim_context(state)

            try:
                response = await self._llm_call(state)
            except Exception as e:
                logger.exception("LLM call failed on iteration %d", state.iteration)
                state.set_error(f"LLM call failed: {e}")
                return state

            if not response.has_tool_calls:
                final = response.content or ""
                state.add_assistant_message(final)
                state.set_completed(final)
                return state

            tool_calls = response.tool_calls
            if response.content:
                state.add_assistant_message(response.content)

            for tc in tool_calls:
                result = await self._execute_tool(tc)
                tool_content = result.to_content_string(max_length=2000)
                state.add_tool_result(tc.id, tool_content, tc.name)
                state.record_tool_call(
                    ToolCallRecord(
                        tool_call=tc,
                        result_content=tool_content,
                        is_error=not result.is_success,
                    )
                )
                if self._on_step:
                    self._on_step(state.iteration, tc.name, result)

        state.set_max_iterations()
        return state

    def _trim_context(self, state: AgentState) -> None:
        """Trim messages to keep context size manageable.

        Strategy:
        1. Always keep system message (if present)
        2. Always keep first user message (original request)
        3. Compress old tool results to save tokens
        4. Keep only recent messages within limit
        """
        messages = state.messages
        if len(messages) <= self._max_context_messages:
            return

        # Identify indices to preserve
        system_idx = 0 if messages and messages[0].role.value == "system" else -1
        first_user_idx = -1
        for i, msg in enumerate(messages):
            if msg.role.value == "user":
                first_user_idx = i
                break

        # Build new message list
        preserved_indices: set[int] = set()
        if system_idx >= 0:
            preserved_indices.add(system_idx)
        if first_user_idx >= 0 and first_user_idx != system_idx:
            preserved_indices.add(first_user_idx)

        # Keep recent messages
        keep_count = self._max_context_messages - len(preserved_indices)
        recent_start = max(0, len(messages) - keep_count)
        for i in range(recent_start, len(messages)):
            preserved_indices.add(i)

        # Compress old tool results
        new_messages: list[ChatMessage] = []
        for i, msg in enumerate(messages):
            if i in preserved_indices:
                new_messages.append(msg)
            elif msg.role.value == "tool":
                # Compress old tool results to minimal summary
                compressed = _compress_tool_result(msg)
                new_messages.append(compressed)
            # Skip other old messages (assistant, user) to save tokens

        state.messages = new_messages
        logger.debug(
            "Trimmed context: %d → %d messages",
            len(messages), len(new_messages),
        )

    async def _llm_call(self, state: AgentState) -> Any:
        """Send the current messages to the LLM."""
        messages = self._context.build_messages(state.messages)
        tools = self._context.get_tool_definitions()
        self._context.increment_call_count()
        return await self._llm.chat(messages=messages, tools=tools)

    async def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call."""
        return await self._executor.execute(tool_call)


def _compress_tool_result(msg: Any) -> Any:
    """Compress a tool result message to a minimal summary.

    Old tool results with full data waste tokens. This keeps only
    the tool name and success/error status.
    """
    content = msg.content or ""
    tool_name = msg.name or "unknown"

    # Extract status from content
    if "Error" in content or "error" in content.lower():
        status = "error"
    elif len(content) > 200:
        status = "success (truncated)"
    else:
        status = "success"

    return ChatMessage(
        role=Role.TOOL,
        content=f"[{tool_name}: {status}]",
        tool_call_id=msg.tool_call_id,
        name=msg.name,
    )
