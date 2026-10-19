"""Agent state definition — the shared state channels flowing through the graph.

LangGraph uses TypedDict + Annotated reducers to define state. Each field is a
"channel" whose values are merged by its reducer (e.g. add_messages appends).
Plugins can declare additional channels via Plugin.extra_channels().
"""

from __future__ import annotations

from typing import Annotated, Any, Sequence

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class ToolResult(TypedDict):
    tool_call_id: str
    name: str
    output: str
    error: bool


def _merge_tool_results(existing: Sequence[ToolResult], new: Sequence[ToolResult]) -> list[ToolResult]:
    return [*existing, *new]


class AgentState(TypedDict):
    """Core state shared by all nodes in the agent graph.

    - messages: the conversation channel, appended via add_messages reducer
    - tool_results: append-only log of tool executions (for auditing / memory)
    - pending_permission: set by permission node, cleared after HITL resume
    - interrupted: signals that the graph is paused for human input
    """
    messages: Annotated[list[AnyMessage], add_messages]
    tool_results: Annotated[list[ToolResult], _merge_tool_results]
    pending_permission: dict[str, Any] | None
    interrupted: bool


def make_initial_state(user_message: str) -> dict[str, Any]:
    from langchain_core.messages import HumanMessage
    return {
        "messages": [HumanMessage(content=user_message)],
        "tool_results": [],
        "pending_permission": None,
        "interrupted": False,
    }
