"""Anthropic LLM client — implements BaseLLM via langchain-anthropic."""

from __future__ import annotations

from typing import Any

from langchain_anthropic import ChatAnthropic


class AnthropicLLM:
    """Thin wrapper around ChatAnthropic conforming to BaseLLM protocol."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> None:
        self._model = ChatAnthropic(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )

    def bind_tools(self, tool_schemas: list[dict[str, Any]]) -> Any:
        return self._model.bind_tools(tool_schemas)

    async def ainvoke(self, messages: list[Any]) -> Any:
        return await self._model.ainvoke(messages)
