"""Tests for the agent state and initial state creation."""

from harness.core.state import AgentState, make_initial_state
from langchain_core.messages import HumanMessage


class TestAgentState:
    def test_make_initial_state(self):
        state = make_initial_state("hello")
        assert len(state["messages"]) == 1
        assert isinstance(state["messages"][0], HumanMessage)
        assert state["messages"][0].content == "hello"
        assert state["tool_results"] == []
        assert state["pending_permission"] is None
        assert state["interrupted"] is False
