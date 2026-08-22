"""Tests for agent state."""

from querymind.agent.state import AgentState, AgentStatus, ToolCallRecord
from querymind.llm.client import ToolCall


def test_initial_state() -> None:
    s = AgentState()
    assert s.status == AgentStatus.IDLE
    assert s.iteration == 0
    assert s.final_response is None
    assert len(s.messages) == 0


def test_add_messages() -> None:
    s = AgentState()
    s.add_user_message("hello")
    s.add_assistant_message("hi")
    s.add_tool_result("c1", "result", "mytool")
    assert len(s.messages) == 3
    assert s.messages[0].role.value == "user"
    assert s.messages[1].role.value == "assistant"
    assert s.messages[2].role.value == "tool"
    assert s.messages[2].tool_call_id == "c1"


def test_add_system_message() -> None:
    s = AgentState()
    s.add_user_message("hello")
    s.add_system_message("you are helpful")
    assert len(s.messages) == 2
    assert s.messages[0].role.value == "system"
    assert s.messages[1].role.value == "user"


def test_iteration() -> None:
    s = AgentState()
    assert s.iteration == 0
    s.increment_iteration()
    assert s.iteration == 1
    s.increment_iteration()
    assert s.iteration == 2


def test_set_completed() -> None:
    s = AgentState()
    s.set_completed("done")
    assert s.status == AgentStatus.COMPLETED
    assert s.final_response == "done"


def test_set_error() -> None:
    s = AgentState()
    s.set_error("something broke")
    assert s.status == AgentStatus.ERROR
    assert s.error == "something broke"


def test_set_max_iterations() -> None:
    s = AgentState()
    s.iteration = 20
    s.set_max_iterations()
    assert s.status == AgentStatus.MAX_ITERATIONS
    assert "20" in s.final_response


def test_record_tool_call() -> None:
    s = AgentState()
    tc = ToolCall(id="c1", name="mytool", arguments={"x": 1})
    record = ToolCallRecord(tool_call=tc, result_content="ok", is_error=False)
    s.record_tool_call(record)
    assert len(s.tool_calls) == 1
    assert s.tool_calls[0].tool_call.id == "c1"
