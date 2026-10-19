"""Plugin protocol — the contract every plugin must satisfy.

A Plugin declares what it contributes to the agent graph:
  - tools: callable tools the LLM can invoke
  - nodes: named graph nodes (functions that read/write state)
  - edges: routing logic between nodes
  - hooks: pre/post interceptors on any node execution
  - extra_channels: additional state channels beyond the core AgentState

This is the Python spiritual counterpart of deepseek-harness's Cordis plugin
system — each plugin is self-describing and the registry assembles them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class ToolSpec:
    """A tool the LLM can call. Mirrors the Anthropic tool_use contract."""
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Awaitable[str]]


class HookPoint(str, Enum):
    """Points in the graph lifecycle where hooks can intercept."""
    PRE_TOOL_CALL = "pre_tool_call"
    POST_TOOL_CALL = "post_tool_call"
    PRE_LLM_CALL = "pre_llm_call"
    POST_LLM_CALL = "post_llm_call"
    PRE_NODE = "pre_node"
    POST_NODE = "post_node"


@dataclass(frozen=True)
class NodeSpec:
    """A graph node contributed by a plugin."""
    name: str
    fn: Callable[..., Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class EdgeSpec:
    """A routing edge contributed by a plugin.

    - source/target: node names
    - condition: optional function that returns the next node name(s)
    """
    source: str
    target: str | None = None
    condition: Callable[..., str | list[str]] | None = None


@dataclass(frozen=True)
class HookSpec:
    """A hook interceptor contributed by a plugin."""
    point: HookPoint
    fn: Callable[..., Awaitable[dict[str, Any] | None]]
    target_node: str | None = None


class Plugin:
    """Base plugin class. Subclass and override methods to contribute to the graph.

    Default implementations return empty — override only what you contribute.
    """

    @property
    def name(self) -> str:
        raise NotImplementedError

    @property
    def priority(self) -> int:
        return 0

    def tools(self) -> Sequence[ToolSpec]:
        return []

    def nodes(self) -> Sequence[NodeSpec]:
        return []

    def edges(self) -> Sequence[EdgeSpec]:
        return []

    def hooks(self) -> Sequence[HookSpec]:
        return []

    def extra_channels(self) -> dict[str, Any]:
        return {}
