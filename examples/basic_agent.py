"""Basic agent example — no permission gates, just tools + memory.

Run:
    export ANTHROPIC_API_KEY=sk-ant-...
    python -m examples.basic_agent
"""

import asyncio
import os

from harness.core.registry import PluginRegistry
from harness.core.graph import GraphBuilder
from harness.core.state import make_initial_state
from harness.llm.anthropic_client import AnthropicLLM
from harness.plugins.tools import ToolsPlugin
from harness.plugins.memory import MemoryPlugin


async def main():
    llm = AnthropicLLM(model="claude-sonnet-4-20250514")

    registry = PluginRegistry()
    registry.register(ToolsPlugin(workspace="."))
    registry.register(MemoryPlugin())

    builder = GraphBuilder(llm=llm, registry=registry)
    agent = builder.build()

    initial = make_initial_state("List the files in the current directory and read pyproject.toml if it exists.")

    config = {"configurable": {"thread_id": "basic-demo"}}
    result = await agent.ainvoke(initial, config=config)

    for msg in result["messages"]:
        role = type(msg).__name__
        content = msg.content if hasattr(msg, "content") else str(msg)
        if isinstance(content, list):
            content = str(content)
        print(f"\n[{role}] {content[:500]}")


if __name__ == "__main__":
    asyncio.run(main())
