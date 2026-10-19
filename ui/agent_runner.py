"""Agent runner — bridges the LangGraph agent with the Streamlit UI.

Handles:
  - Agent lifecycle (create, configure)
  - Streaming execution with tool call capture
  - interrupt() for HITL permission flow
  - Resume with user decision
"""

from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphInterrupt

from harness.core.graph import GraphBuilder
from harness.core.registry import PluginRegistry
from harness.core.state import make_initial_state
from harness.plugins.memory import MemoryPlugin
from harness.plugins.permissions import PermissionLevel, PermissionsPlugin
from harness.plugins.tools import ToolsPlugin


@dataclass
class ToolCallEvent:
    tool_name: str
    tool_input: dict[str, Any]
    output: str | None = None
    status: str = "pending"


@dataclass
class InterruptInfo:
    tool_name: str
    tool_input: dict[str, Any]
    message: str


@dataclass
class AgentRunner:
    workspace: str = "."
    thread_id: str = ""
    _agent: Any = None
    _messages: list[Any] = field(default_factory=list)
    _tool_events: list[ToolCallEvent] = field(default_factory=list)
    _pending_interrupt: InterruptInfo | None = None

    def __post_init__(self):
        if not self.thread_id:
            self.thread_id = str(uuid.uuid4())[:8]

    def _create_agent(self):
        from harness.llm.openai_client import OpenAILLM
        llm = OpenAILLM(
            base_url=os.environ.get("LLM_BASE_URL", "https://llm.polixir.site/v1"),
            api_key=os.environ.get("LLM_API_KEY", ""),
            model=os.environ.get("LLM_MODEL", "glm-5.2"),
        )
        registry = PluginRegistry()
        registry.register(ToolsPlugin(workspace=self.workspace))
        registry.register(PermissionsPlugin())
        registry.register(MemoryPlugin())

        builder = GraphBuilder(llm=llm, registry=registry)
        return builder.build(checkpointer=MemorySaver())

    @property
    def agent(self):
        if self._agent is None:
            self._agent = self._create_agent()
        return self._agent

    @property
    def messages(self) -> list[Any]:
        return self._messages

    @property
    def tool_events(self) -> list[ToolCallEvent]:
        return self._tool_events

    @property
    def pending_interrupt(self) -> InterruptInfo | None:
        return self._pending_interrupt

    def get_config(self) -> dict[str, Any]:
        return {"configurable": {"thread_id": self.thread_id}}

    async def send_message(self, user_input: str) -> AsyncIterator[dict[str, Any]]:
        """Send a message and stream back events.

        Yields dicts with keys:
          - {"type": "token", "content": str}  — LLM text token
          - {"type": "tool_start", "name": str, "input": dict}
          - {"type": "tool_end", "name": str, "output": str}
          - {"type": "interrupt", "info": InterruptInfo}
          - {"type": "done"}
        """
        if self._pending_interrupt:
            raise RuntimeError("Cannot send message while interrupt is pending. Call resume() first.")

        state = make_initial_state(user_input)
        self._messages.append(HumanMessage(content=user_input))

        async for event in self._stream_run(state):
            yield event

    async def resume(self, approved: bool) -> AsyncIterator[dict[str, Any]]:
        """Resume after an interrupt with the user's decision."""
        if not self._pending_interrupt:
            raise RuntimeError("No pending interrupt to resume from.")

        interrupt_info = self._pending_interrupt
        self._pending_interrupt = None

        from langgraph.types import Command
        resume_value = Command(resume={"approved": approved})

        async for event in self._stream_resume(resume_value):
            yield event

    async def _stream_run(self, state: dict) -> AsyncIterator[dict[str, Any]]:
        config = self.get_config()

        try:
            async for event in self.agent.astream(state, config=config, stream_mode="updates"):
                for node_name, node_output in event.items():
                    if node_name == "agent":
                        for msg in node_output.get("messages", []):
                            if isinstance(msg, AIMessage):
                                if msg.content:
                                    yield {"type": "token", "content": msg.content}
                                if msg.tool_calls:
                                    for tc in msg.tool_calls:
                                        tool_event = ToolCallEvent(
                                            tool_name=tc["name"],
                                            tool_input=tc["args"],
                                        )
                                        self._tool_events.append(tool_event)
                                        yield {
                                            "type": "tool_start",
                                            "name": tc["name"],
                                            "input": tc["args"],
                                        }
                                self._messages.append(msg)

                    elif node_name == "tools":
                        for msg in node_output.get("messages", []):
                            if isinstance(msg, ToolMessage):
                                for te in reversed(self._tool_events):
                                    if te.tool_name == msg.name and te.status == "pending":
                                        te.output = msg.content
                                        te.status = "completed"
                                        yield {
                                            "type": "tool_end",
                                            "name": msg.name,
                                            "output": msg.content,
                                        }
                                        break
                                self._messages.append(msg)

        except GraphInterrupt as e:
            interrupt_data = e.args[0] if e.args else {}
            if isinstance(interrupt_data, dict) and interrupt_data.get("type") == "permission_request":
                info = InterruptInfo(
                    tool_name=interrupt_data.get("tool", "unknown"),
                    tool_input=interrupt_data.get("input", {}),
                    message=interrupt_data.get("message", "Approve?"),
                )
                self._pending_interrupt = info
                yield {"type": "interrupt", "info": info}
                return

        yield {"type": "done"}

    async def _stream_resume(self, resume_value: Any) -> AsyncIterator[dict[str, Any]]:
        config = self.get_config()

        try:
            async for event in self.agent.astream(resume_value, config=config, stream_mode="updates"):
                for node_name, node_output in event.items():
                    if node_name == "agent":
                        for msg in node_output.get("messages", []):
                            if isinstance(msg, AIMessage):
                                if msg.content:
                                    yield {"type": "token", "content": msg.content}
                                self._messages.append(msg)
                    elif node_name == "tools":
                        for msg in node_output.get("messages", []):
                            if isinstance(msg, ToolMessage):
                                yield {
                                    "type": "tool_end",
                                    "name": msg.name,
                                    "output": msg.content,
                                }
                                self._messages.append(msg)
        except GraphInterrupt as e:
            interrupt_data = e.args[0] if e.args else {}
            if isinstance(interrupt_data, dict) and interrupt_data.get("type") == "permission_request":
                info = InterruptInfo(
                    tool_name=interrupt_data.get("tool", "unknown"),
                    tool_input=interrupt_data.get("input", {}),
                    message=interrupt_data.get("message", "Approve?"),
                )
                self._pending_interrupt = info
                yield {"type": "interrupt", "info": info}
                return

        yield {"type": "done"}

    def get_file_tree(self, path: str = ".") -> list[dict[str, Any]]:
        root = Path(self.workspace) / path
        if not root.exists():
            return []
        entries = []
        for entry in sorted(root.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            if entry.name.startswith("."):
                continue
            entries.append({
                "name": entry.name,
                "path": str(entry.relative_to(self.workspace)),
                "is_dir": entry.is_dir(),
            })
        return entries

    def read_file(self, path: str) -> str:
        full = Path(self.workspace) / path
        if not full.is_file():
            return f"File not found: {path}"
        try:
            return full.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"[Binary file: {path}]"
