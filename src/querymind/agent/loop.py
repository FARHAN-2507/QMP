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
    LLMProvider,
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
    ) -> None:
        self._llm = llm
        self._context = context
        self._executor = executor
        self._max_iterations = max_iterations
        self._on_step = on_step

    async def run(self, state: AgentState) -> AgentState:
        """Execute the agent loop from the current state.

        Mutates and returns the state.
        """
        state.status = AgentStatus.RUNNING

        while state.iteration < self._max_iterations:
            state.increment_iteration()
            logger.debug("Iteration %d", state.iteration)

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
                tool_content = result.to_content_string()
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

    async def _llm_call(self, state: AgentState) -> Any:
        """Send the current messages to the LLM."""
        messages = self._context.build_messages(state.messages)
        tools = self._context.get_tool_definitions()
        return await self._llm.chat(messages=messages, tools=tools)

    async def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call."""
        return await self._executor.execute(tool_call)
