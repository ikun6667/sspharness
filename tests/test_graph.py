"""Tests for the graph builder (integration-level)."""

import pytest
from harness.core.registry import PluginRegistry
from harness.core.graph import GraphBuilder


class MockLLM:
    """Minimal mock LLM for testing graph construction."""

    def bind_tools(self, tool_schemas):
        return self

    async def ainvoke(self, messages):
        from langchain_core.messages import AIMessage
        return AIMessage(content="mock response")


class TestGraphBuilder:
    def test_build_with_empty_registry(self):
        registry = PluginRegistry()
        builder = GraphBuilder(llm=MockLLM(), registry=registry)
        agent = builder.build()
        assert agent is not None

    def test_build_with_tools_plugin(self):
        from harness.plugins.tools import ToolsPlugin
        registry = PluginRegistry()
        registry.register(ToolsPlugin(workspace="."))
        builder = GraphBuilder(llm=MockLLM(), registry=registry)
        agent = builder.build()
        assert agent is not None
