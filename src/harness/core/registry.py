"""Plugin registry — collects plugins and assembles their contributions.

The registry is the "Cordis kernel" of our system: plugins register themselves,
and the registry resolves their combined tools / nodes / edges / hooks into a
flat manifest that GraphBuilder consumes to compile the LangGraph state graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.core.plugin import (
    EdgeSpec,
    HookPoint,
    HookSpec,
    NodeSpec,
    Plugin,
    ToolSpec,
)


@dataclass
class PluginManifest:
    """The resolved, combined output of all registered plugins."""
    tools: dict[str, ToolSpec] = field(default_factory=dict)
    nodes: dict[str, NodeSpec] = field(default_factory=dict)
    edges: list[EdgeSpec] = field(default_factory=list)
    hooks: dict[HookPoint, list[HookSpec]] = field(default_factory=lambda: {p: [] for p in HookPoint})
    extra_channels: dict[str, Any] = field(default_factory=dict)


class PluginRegistry:
    """Collects plugins in priority order and resolves their manifest."""

    def __init__(self) -> None:
        self._plugins: list[Plugin] = []
        self._manifest: PluginManifest | None = None

    def register(self, plugin: Plugin) -> None:
        self._plugins.append(plugin)
        self._manifest = None

    def unregister(self, name: str) -> None:
        self._plugins = [p for p in self._plugins if p.name != name]
        self._manifest = None

    @property
    def plugins(self) -> list[Plugin]:
        return sorted(self._plugins, key=lambda p: p.priority, reverse=True)

    def resolve(self) -> PluginManifest:
        if self._manifest is not None:
            return self._manifest

        manifest = PluginManifest()
        for plugin in self.plugins:
            for tool in plugin.tools():
                if tool.name in manifest.tools:
                    raise ValueError(f"Tool '{tool.name}' registered by both "
                                     f"'{manifest.tools[tool.name].name}' and '{plugin.name}'")
                manifest.tools[tool.name] = tool

            for node in plugin.nodes():
                if node.name in manifest.nodes:
                    raise ValueError(f"Node '{node.name}' registered by both "
                                     f"'{manifest.nodes[node.name].name}' and '{plugin.name}'")
                manifest.nodes[node.name] = node

            manifest.edges.extend(plugin.edges())

            for hook in plugin.hooks():
                manifest.hooks[hook.point].append(hook)

            for channel_name, reducer in plugin.extra_channels().items():
                if channel_name in manifest.extra_channels:
                    raise ValueError(f"Channel '{channel_name}' conflict in plugin '{plugin.name}'")
                manifest.extra_channels[channel_name] = reducer

        self._manifest = manifest
        return manifest

    def list_plugins(self) -> list[str]:
        return [p.name for p in self.plugins]
