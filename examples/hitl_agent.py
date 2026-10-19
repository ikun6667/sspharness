"""HITL agent example — with permission gates using interrupt().

Demonstrates the core "framework true increment": the graph pauses at
write_file / bash calls, waits for user approval, then resumes.

Run:
    export ANTHROPIC_API_KEY=sk-ant-...
    python -m examples.hitl_agent
"""

import asyncio

from harness.core.registry import PluginRegistry
from harness.core.graph import GraphBuilder
from harness.core.state import make_initial_state
from harness.llm.anthropic_client import AnthropicLLM
from harness.plugins.tools import ToolsPlugin
from harness.plugins.permissions import PermissionsPlugin, PermissionLevel
from harness.plugins.memory import MemoryPlugin


async def main():
    llm = AnthropicLLM(model="claude-sonnet-4-20250514")

    registry = PluginRegistry()
    registry.register(ToolsPlugin(workspace="./workspace"))
    registry.register(PermissionsPlugin(policy={
        "read_file": PermissionLevel.ALLOW,
        "list_files": PermissionLevel.ALLOW,
        "write_file": PermissionLevel.ASK,
        "bash": PermissionLevel.ASK,
    }))
    registry.register(MemoryPlugin())

    builder = GraphBuilder(llm=llm, registry=registry)
    agent = builder.build()

    initial = make_initial_state(
        "Create a file called hello.py with a simple Hello World program, then run it."
    )

    config = {"configurable": {"thread_id": "hitl-demo"}}

    result = await agent.ainvoke(initial, config=config)

    for msg in result["messages"]:
        role = type(msg).__name__
        content = msg.content if hasattr(msg, "content") else str(msg)
        if isinstance(content, list):
            content = str(content)
        print(f"\n[{role}] {content[:500]}")


if __name__ == "__main__":
    asyncio.run(main())
