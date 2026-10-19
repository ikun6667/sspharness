"""Tests for the plugin registry."""

import pytest
from harness.core.plugin import HookPoint, HookSpec, NodeSpec, Plugin, ToolSpec
from harness.core.registry import PluginRegistry


class MockPlugin(Plugin):
    def __init__(self, name: str, priority: int = 0):
        self._name = name
        self._priority = priority

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    def tools(self):
        return [
            ToolSpec(
                name=f"{self._name}_tool",
                description=f"Tool from {self._name}",
                input_schema={"type": "object", "properties": {}},
                handler=lambda: None,
            )
        ]


class TestPluginRegistry:
    def test_register_and_list(self):
        registry = PluginRegistry()
        registry.register(MockPlugin("alpha"))
        registry.register(MockPlugin("beta"))
        assert set(registry.list_plugins()) == {"alpha", "beta"}

    def test_priority_ordering(self):
        registry = PluginRegistry()
        registry.register(MockPlugin("low", priority=10))
        registry.register(MockPlugin("high", priority=100))
        plugins = registry.plugins
        assert plugins[0].name == "high"
        assert plugins[1].name == "low"

    def test_resolve_manifest(self):
        registry = PluginRegistry()
        registry.register(MockPlugin("alpha"))
        registry.register(MockPlugin("beta"))
        manifest = registry.resolve()
        assert "alpha_tool" in manifest.tools
        assert "beta_tool" in manifest.tools

    def test_duplicate_tool_raises(self):
        registry = PluginRegistry()

        class DupPlugin(Plugin):
            @property
            def name(self): return "dup"
            def tools(self):
                return [ToolSpec(name="same", description="", input_schema={}, handler=lambda: None)]

        registry.register(DupPlugin())
        registry.register(DupPlugin())
        with pytest.raises(ValueError, match="Tool 'same' registered by both"):
            registry.resolve()

    def test_unregister(self):
        registry = PluginRegistry()
        registry.register(MockPlugin("alpha"))
        registry.unregister("alpha")
        assert "alpha" not in registry.list_plugins()
