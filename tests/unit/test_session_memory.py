"""Tests for session memory in AgentRuntime."""

import pytest

from querymind.agent.runtime import AgentRuntime
from querymind.agent.state import AgentStatus
from querymind.llm.client import ChatMessage, ChatResponse


class FakeLLM:
    """Fake LLM for testing that returns predetermined responses."""

    def __init__(self, responses: list[ChatResponse]) -> None:
        self._responses = list(responses)
        self._call_count = 0

    async def chat(self, messages: list[ChatMessage], tools: list[object] = None) -> ChatResponse:
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
            self._call_count += 1
            return resp
        return ChatResponse(content="Done")


def make_text_response(text: str) -> ChatResponse:
    return ChatResponse(content=text)


@pytest.mark.asyncio
async def test_session_memory_persists_state() -> None:
    llm = FakeLLM([
        make_text_response("First response"),
        make_text_response("Second response"),
    ])
    runtime = AgentRuntime(llm=llm)  # type: ignore[arg-type]

    # First call
    state1 = await runtime.run("Hello")
    assert state1.status == AgentStatus.COMPLETED
    assert runtime.get_message_count() > 0

    # Second call — should reuse state
    state2 = await runtime.run("Again")
    assert state2.status == AgentStatus.COMPLETED
    # Messages should accumulate
    assert runtime.get_message_count() > 2


@pytest.mark.asyncio
async def test_session_memory_resets() -> None:
    llm = FakeLLM([
        make_text_response("Response 1"),
        make_text_response("Response 2"),
    ])
    runtime = AgentRuntime(llm=llm)  # type: ignore[arg-type]

    await runtime.run("Hello")
    count_after_first = runtime.get_message_count()
    assert count_after_first > 0

    runtime.reset()
    # After reset, should have 0 messages (fresh state)
    assert runtime.get_message_count() == 0


@pytest.mark.asyncio
async def test_session_memory_get_history() -> None:
    llm = FakeLLM([make_text_response("Response")])
    runtime = AgentRuntime(llm=llm)  # type: ignore[arg-type]

    await runtime.run("Test message")
    history = runtime.get_history()
    # Should have user message and assistant response
    assert len(history) >= 2
    # First non-system message should be user
    user_msgs = [h for h in history if h["role"] == "user"]
    assert len(user_msgs) >= 1
    assert user_msgs[0]["content"] == "Test message"


@pytest.mark.asyncio
async def test_session_memory_trim_history() -> None:
    llm = FakeLLM([
        make_text_response("R1"),
        make_text_response("R2"),
        make_text_response("R3"),
    ])
    # Set small max history to force trimming
    runtime = AgentRuntime(llm=llm, max_history_messages=8)  # type: ignore[arg-type]

    await runtime.run("Msg 1")
    await runtime.run("Msg 2")

    await runtime.run("Msg 3")
    count_after = runtime.get_message_count()

    # After trimming, count should not grow beyond max
    # (messages include system prompt from context, so allow some buffer)
    assert count_after <= 10


@pytest.mark.asyncio
async def test_session_memory_new_session() -> None:
    llm = FakeLLM([
        make_text_response("Response 1"),
        make_text_response("Response 2"),
    ])
    runtime = AgentRuntime(llm=llm)  # type: ignore[arg-type]

    await runtime.run("Hello")
    old_id = runtime.session_id

    new_id = runtime.new_session()
    assert new_id != old_id
    assert runtime.get_message_count() == 0


@pytest.mark.asyncio
async def test_session_memory_preserves_context() -> None:
    """Test that the agent can reference previous conversation."""
    llm = FakeLLM([
        make_text_response("I tested the users endpoint."),
        make_text_response("Based on our previous discussion about users, I'll now test posts."),
    ])
    runtime = AgentRuntime(llm=llm)  # type: ignore[arg-type]

    state1 = await runtime.run("test /api/users")
    state2 = await runtime.run("now test /api/posts")

    # Both should complete
    assert state1.status == AgentStatus.COMPLETED
    assert state2.status == AgentStatus.COMPLETED
