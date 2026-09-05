"""Agent runtime — wires together LLM, tools, and the agent loop.

This is the top-level entry point that the CLI and (later) FastAPI
call to start an agent session.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from querymind.agent.context import AgentContext
from querymind.agent.loop import AgentLoop, AgentStepCallback
from querymind.agent.state import AgentState
from querymind.config.settings import settings
from querymind.llm.client import ChatMessage, LLMProvider, Role
from querymind.security.provider import AuthProvider
from querymind.storage.session import SessionStore
from querymind.tools.auth import ClearAuth, ConfigureAuth, ListAuth
from querymind.tools.curl import ParseCurl, RunCurl
from querymind.tools.discovery import DiscoverApi
from querymind.tools.executor import ToolExecutor
from querymind.tools.generator import GenerateTests, GenerateTestsBatch
from querymind.tools.http import SendHttpRequest
from querymind.tools.mock import GetCurrentTestEnvironment
from querymind.tools.openapi import ImportOpenApi
from querymind.tools.registry import ToolRegistry
from querymind.tools.report import GenerateReport
from querymind.tools.smoke import RunSmokeTests
from querymind.tools.testing import RunTest

logger = logging.getLogger(__name__)


class AgentRuntime:
    """High-level orchestrator for running the agent.

    Maintains conversation state across multiple run() calls,
    enabling multi-turn conversations with memory.
    Persists sessions to disk for cross-session persistence.
    """

    def __init__(
        self,
        llm: LLMProvider,
        system_prompt: str | None = None,
        on_step: AgentStepCallback = None,
        max_history_messages: int | None = None,
        data_dir: Path | str | None = None,
    ) -> None:
        self._llm = llm
        self._registry = ToolRegistry()

        # Auth provider for target API authentication
        data_path = Path(data_dir) if data_dir else Path(settings.data_dir)
        self._auth_provider = AuthProvider(data_path)

        self._register_default_tools()
        self._context = AgentContext(
            tool_registry=self._registry,
            system_prompt=system_prompt,
            auth_provider=self._auth_provider,
        )
        self._executor = ToolExecutor(self._registry)
        self._loop = AgentLoop(
            llm=llm,
            context=self._context,
            executor=self._executor,
            max_iterations=settings.max_agent_iterations,
            on_step=on_step,
        )
        self._state: AgentState | None = None
        self._max_history_messages = max_history_messages or settings.max_history_messages

        # Session persistence
        self._session_store = SessionStore(data_dir or settings.data_dir)
        self._session_id: str | None = None

        # Auto-load last session and cleanup old ones
        self._auto_load_session()

    def _register_default_tools(self) -> None:
        """Register the built-in tools."""
        self._registry.register(GetCurrentTestEnvironment())
        self._registry.register(SendHttpRequest(auth_provider=self._auth_provider))
        self._registry.register(ImportOpenApi())
        self._registry.register(DiscoverApi(auth_provider=self._auth_provider))
        self._registry.register(RunTest(auth_provider=self._auth_provider))
        self._registry.register(GenerateTests())
        self._registry.register(GenerateTestsBatch())
        self._registry.register(GenerateReport())
        self._registry.register(RunSmokeTests(auth_provider=self._auth_provider))
        self._registry.register(ParseCurl())
        self._registry.register(RunCurl(auth_provider=self._auth_provider))
        self._registry.register(ConfigureAuth(auth_provider=self._auth_provider))
        self._registry.register(ListAuth(auth_provider=self._auth_provider))
        self._registry.register(ClearAuth(auth_provider=self._auth_provider))

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    @property
    def session_id(self) -> str | None:
        """Return current session ID."""
        return self._session_id

    @property
    def auth_provider(self) -> AuthProvider:
        """Return the auth provider."""
        return self._auth_provider

    def _auto_load_session(self) -> None:
        """Load the most recent session if it exists and is valid."""
        # Cleanup old sessions first
        deleted = self._session_store.cleanup_old_sessions(settings.session_ttl_days)
        if deleted > 0:
            logger.info("Cleaned up %d old sessions", deleted)

        # Try to load current session
        current_id = self._session_store.get_current_session_id()
        if current_id and self._session_store.session_exists(current_id):
            data = self._session_store.load(current_id)
            if data and self._is_session_valid(data):
                self._session_id = current_id
                raw_messages = data.get("messages", [])
                self._state = AgentState()
                self._state.messages = self._deserialize_messages(raw_messages)
                # Compress old tool results to save tokens
                self._compress_loaded_session()
                logger.info("Loaded session %s (%d messages)", current_id, len(raw_messages))
                return

        # No valid session — start fresh
        self._session_id = self._session_store.create_new_session()
        logger.info("Created new session %s", self._session_id)

    def _is_session_valid(self, data: dict[str, Any]) -> bool:
        """Check if session data is valid and usable."""
        required_keys = {"session_id", "messages", "updated_at"}
        if not all(k in data for k in required_keys):
            return False
        return isinstance(data["messages"], list)

    async def run(self, user_input: str, on_tool_call: Any = None) -> AgentState:
        """Run the agent on a user request.

        Reuses existing conversation state if available, enabling
        multi-turn conversations with memory.
        Auto-saves to disk after each run.
        """
        if self._state is None:
            self._state = AgentState()

        self._state.add_user_message(user_input)
        self._trim_history()

        # Update the on_step callback if provided
        if on_tool_call:
            self._loop._on_step = on_tool_call

        self._state = await self._loop.run(self._state)

        # Auto-save after each run
        self._save_session()
        return self._state

    def new_session(self) -> str:
        """Start a new session. Returns the new session ID."""
        self._session_id = self._session_store.create_new_session()
        self._state = AgentState()
        return self._session_id

    def load_session(self, session_id: str) -> bool:
        """Load a specific session. Returns True if successful."""
        data = self._session_store.load(session_id)
        if data and self._is_session_valid(data):
            self._session_id = session_id
            self._state = AgentState()
            self._state.messages = self._deserialize_messages(data.get("messages", []))
            self._session_store.set_current_session_id(session_id)
            return True
        return False

    def reset(self) -> None:
        """Clear conversation history from memory (keeps file)."""
        self._state = None
        self._session_id = self._session_store.create_new_session()

    def get_message_count(self) -> int:
        """Return number of messages in conversation history."""
        if self._state is None:
            return 0
        return len(self._state.messages)

    def get_history(self) -> list[dict[str, str]]:
        """Return conversation history as list of dicts."""
        if self._state is None:
            return []
        return [
            {"role": m.role.value, "content": m.content or ""}
            for m in self._state.messages
        ]

    def list_sessions(self) -> list[dict[str, str]]:
        """List all saved sessions."""
        return self._session_store.list_sessions(settings.session_ttl_days)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        return self._session_store.delete(session_id)

    def _save_session(self) -> None:
        """Save current session to disk."""
        if self._session_id and self._state:
            messages: list[dict[str, str]] = []
            for m in self._state.messages:
                msg: dict[str, str] = {
                    "role": m.role.value,
                    "content": m.content or "",
                }
                if m.tool_call_id:
                    msg["tool_call_id"] = m.tool_call_id
                if m.name:
                    msg["name"] = m.name
                messages.append(msg)
            self._session_store.save(
                self._session_id,
                messages,
                {"tool_calls": len(self._state.tool_calls)},
            )

    def _trim_history(self) -> None:
        """Keep only recent messages to stay within token limits.

        Always preserves the system message if present.
        """
        if self._state is None:
            return

        messages = self._state.messages
        if len(messages) <= self._max_history_messages:
            return

        # Check if first message is system
        has_system = messages and messages[0].role.value == "system"
        system_msg = messages[0:1] if has_system else []
        non_system = messages[1:] if has_system else messages

        # Keep only recent non-system messages
        keep_count = self._max_history_messages - len(system_msg)
        recent = non_system[-keep_count:] if len(non_system) > keep_count else non_system

        self._state.messages = system_msg + recent
        logger.debug(
            "Trimmed history: %d → %d messages",
            len(messages), len(self._state.messages),
        )

    def _compress_loaded_session(self) -> None:
        """Compress old tool results when loading a session.

        Prevents old tool output from bloating the context.
        Keeps only tool name and success/error status for old results.
        """
        if self._state is None:
            return

        messages = self._state.messages
        if len(messages) <= 10:
            return  # Small session, no compression needed

        # Keep system message and first user message intact
        # Compress tool results older than the last 6 messages
        keep_recent = 6
        for i, msg in enumerate(messages):
            if msg.role.value == "tool" and i < len(messages) - keep_recent:
                content = msg.content or ""
                tool_name = msg.name or "unknown"

                # Determine status
                if "Error" in content or "error" in content.lower():
                    status = "error"
                elif len(content) > 100:
                    status = "success (compressed)"
                else:
                    status = "success"

                # Replace with compressed version
                messages[i] = ChatMessage(
                    role=Role.TOOL,
                    content=f"[{tool_name}: {status}]",
                    tool_call_id=msg.tool_call_id,
                    name=msg.name,
                )

        logger.debug("Compressed loaded session tool results")

    def _deserialize_messages(self, raw_messages: list[dict[str, str]]) -> list[ChatMessage]:
        """Convert dict messages from JSON to ChatMessage objects."""
        result: list[ChatMessage] = []
        for msg in raw_messages:
            role_str = msg.get("role", "user")
            try:
                role = Role(role_str)
            except ValueError:
                role = Role.USER
            result.append(ChatMessage(
                role=role,
                content=msg.get("content", ""),
                tool_call_id=msg.get("tool_call_id"),
                name=msg.get("name"),
            ))
        return result

    def get_tools_summary(self) -> str:
        """Return a summary of registered tools."""
        names = self._registry.list_names()
        return f"Registered tools ({len(names)}): {', '.join(names)}"
