"""Graph builder — compiles a PluginManifest into a runnable LangGraph StateGraph.

This is where the plugin contributions become a real executable graph.
The builder:
  1. Creates a StateGraph with core + extra channels
  2. Adds all plugin-contributed nodes
  3. Wires the default agent loop (LLM → should_continue → tools → back to LLM)
  4. Inserts plugin-contributed edges and hooks
  5. Compiles with a checkpointer for resumability
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from harness.core.plugin import HookPoint, ToolSpec
from harness.core.registry import PluginManifest, PluginRegistry
from harness.core.state import AgentState
from harness.llm.base import BaseLLM


class GraphBuilder:
    """Compiles registered plugins into a runnable LangGraph agent."""

    def __init__(self, llm: BaseLLM, registry: PluginRegistry) -> None:
        self.llm = llm
        self.registry = registry
        self._manifest: PluginManifest | None = None

    @property
    def manifest(self) -> PluginManifest:
        if self._manifest is None:
            self._manifest = self.registry.resolve()
        return self._manifest

    def _bind_tools(self) -> Any:
        tools = self.manifest.tools
        tool_schemas = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in tools.values()
        ]
        return self.llm.bind_tools(tool_schemas)

    def _make_tool_node(self) -> ToolNode:
        tools = self.manifest.tools
        langchain_tools = []
        for spec in tools.values():
            langchain_tools.append(_spec_to_langchain_tool(spec))
        return ToolNode(langchain_tools)

    def _build_agent_node(self):
        llm_with_tools = self._bind_tools()

        async def call_llm(state: AgentState) -> dict[str, Any]:
            messages = state["messages"]
            hooks = self.manifest.hooks[HookPoint.PRE_LLM_CALL]
            for hook in hooks:
                result = await hook.fn(state)
                if result:
                    messages = result.get("messages", messages)

            response = await llm_with_tools.ainvoke(messages)

            post_hooks = self.manifest.hooks[HookPoint.POST_LLM_CALL]
            for hook in post_hooks:
                result = await hook.fn(state, response)
                if result:
                    response = result.get("response", response)

            return {"messages": [response]}

        return call_llm

    def _should_continue(self, state: AgentState) -> str:
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        return END

    def build(self, checkpointer: Any | None = None) -> Any:
        if checkpointer is None:
            checkpointer = MemorySaver()

        graph = StateGraph(AgentState)

        graph.add_node("agent", self._build_agent_node())
        graph.add_node("tools", self._make_tool_node())

        for node_spec in self.manifest.nodes.values():
            if node_spec.name not in ("agent", "tools"):
                graph.add_node(node_spec.name, node_spec.fn)

        graph.set_entry_point("agent")
        graph.add_conditional_edges("agent", self._should_continue, {"tools": "tools", END: END})
        graph.add_edge("tools", "agent")

        for edge in self.manifest.edges:
            if edge.condition:
                graph.add_conditional_edges(edge.source, edge.condition)
            elif edge.target:
                graph.add_edge(edge.source, edge.target)

        return graph.compile(checkpointer=checkpointer)


def _spec_to_langchain_tool(spec: ToolSpec):
    from langchain_core.tools import StructuredTool
    return StructuredTool.from_function(
        coroutine=spec.handler,
        name=spec.name,
        description=spec.description,
        args_schema=None,
    )
