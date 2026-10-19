"""Base LLM abstraction — decouples the harness from any specific provider."""

from __future__ import annotations

from typing import Any, Protocol


class BaseLLM(Protocol):
    """Minimal LLM interface the harness needs.

    The harness only requires: bind tools → invoke with messages.
    This keeps the core provider-agnostic (Anthropic, OpenAI, DeepSeek, etc.).
    """

    def bind_tools(self, tool_schemas: list[dict[str, Any]]) -> Any:
        """Return a new LLM instance with tool definitions bound."""
        ...

    async def ainvoke(self, messages: list[Any]) -> Any:
        """Async invoke with a message list, return an AIMessage."""
        ...
