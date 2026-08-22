"""Agent runtime — wires together LLM, tools, and the agent loop.

This is the top-level entry point that the CLI and (later) FastAPI
call to start an agent session.
"""

from __future__ import annotations

import logging

from querymind.agent.context import AgentContext
from querymind.agent.loop import AgentLoop, AgentStepCallback
from querymind.agent.state import AgentState
from querymind.config.settings import settings
from querymind.llm.client import LLMProvider
from querymind.tools.discovery import DiscoverApi
from querymind.tools.executor import ToolExecutor
from querymind.tools.http import SendHttpRequest
from querymind.tools.mock import GetCurrentTestEnvironment
from querymind.tools.openapi import ImportOpenApi
from querymind.tools.registry import ToolRegistry
from querymind.tools.testing import RunTest

logger = logging.getLogger(__name__)


class AgentRuntime:
    """High-level orchestrator for running the agent."""

    def __init__(
        self,
        llm: LLMProvider,
        system_prompt: str | None = None,
        on_step: AgentStepCallback = None,
    ) -> None:
        self._llm = llm
        self._registry = ToolRegistry()
        self._register_default_tools()
        self._context = AgentContext(
            tool_registry=self._registry,
            system_prompt=system_prompt,
        )
        self._executor = ToolExecutor(self._registry)
        self._loop = AgentLoop(
            llm=llm,
            context=self._context,
            executor=self._executor,
            max_iterations=settings.max_agent_iterations,
            on_step=on_step,
        )

    def _register_default_tools(self) -> None:
        """Register the built-in tools."""
        self._registry.register(GetCurrentTestEnvironment())
        self._registry.register(SendHttpRequest())
        self._registry.register(ImportOpenApi())
        self._registry.register(DiscoverApi())
        self._registry.register(RunTest())

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    async def run(self, user_input: str) -> AgentState:
        """Run the agent on a single user request.

        Creates fresh state, executes the loop, and returns the result.
        """
        state = AgentState()
        state.add_user_message(user_input)
        state = await self._loop.run(state)
        return state

    def get_tools_summary(self) -> str:
        """Return a summary of registered tools."""
        names = self._registry.list_names()
        return f"Registered tools ({len(names)}): {', '.join(names)}"
