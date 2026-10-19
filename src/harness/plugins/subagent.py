"""Subagent plugin — spawns sub-agents as graph subgraphs.

The third "framework true increment": sub-agents are LangGraph subgraphs,
naturally isolating their context from the parent. The parent agent sees
the subagent as a tool call; internally it runs a full agent loop in its
own compiled graph.
"""

from __future__ import annotations

from typing import Any

from harness.core.plugin import Plugin, ToolSpec


class SubagentPlugin(Plugin):
    """Provides a 'spawn_subagent' tool that runs a task in an isolated subgraph.

    The subagent gets its own message context and returns a result to the parent.
    This mirrors learn-claude-code's spawn_teammate / task mechanism, but uses
    LangGraph's native subgraph support for context isolation.
    """

    def __init__(self, llm: Any, max_turns: int = 10) -> None:
        self._llm = llm
        self._max_turns = max_turns

    @property
    def name(self) -> str:
        return "subagent"

    @property
    def priority(self) -> int:
        return 30

    def tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="spawn_subagent",
                description="Spawn a sub-agent to handle a specific task in isolation. "
                            "The sub-agent runs its own agent loop and returns a result.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "The task description for the sub-agent"},
                        "context": {"type": "string", "description": "Additional context to provide", "default": ""},
                    },
                    "required": ["task"],
                },
                handler=self._spawn_subagent,
            ),
        ]

    async def _spawn_subagent(self, task: str, context: str = "") -> str:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.graph import END, StateGraph

        from harness.core.state import AgentState

        system_prompt = (
            "You are a sub-agent working on a specific task. "
            "Focus only on the task at hand. Be concise and return a clear result."
        )
        if context:
            system_prompt += f"\n\nContext from parent: {context}"

        messages = [SystemMessage(content=system_prompt), HumanMessage(content=task)]

        async def agent_node(state: AgentState) -> dict[str, Any]:
            response = await self._llm.ainvoke(state["messages"])
            return {"messages": [response]}

        def should_end(state: AgentState) -> str:
            last = state["messages"][-1]
            if hasattr(last, "tool_calls") and last.tool_calls:
                return "continue"
            return END

        graph = StateGraph(AgentState)
        graph.add_node("agent", agent_node)
        graph.set_entry_point("agent")
        graph.add_conditional_edges("agent", should_end, {"continue": "agent", END: END})

        compiled = graph.compile(checkpointer=MemorySaver())
        result = await compiled.ainvoke(
            {"messages": messages, "tool_results": [], "pending_permission": None, "interrupted": False},
            config={"configurable": {"thread_id": "subagent-temp"}},
        )

        final_msg = result["messages"][-1]
        return final_msg.content if hasattr(final_msg, "content") else str(final_msg)
