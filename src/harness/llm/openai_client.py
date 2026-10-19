"""OpenAI-compatible LLM client — works with any /v1 endpoint.

Supports: polixir proxy, OpenAI, DeepSeek, Ollama, vLLM, etc.
"""

from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI


class OpenAILLM:
    """ChatOpenAI wrapper conforming to BaseLLM protocol, pointing at a custom endpoint."""

    def __init__(
        self,
        base_url: str = "https://llm.polixir.site/v1",
        api_key: str = "",
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> None:
        self._model = ChatOpenAI(
            base_url=base_url,
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )

    def bind_tools(self, tool_schemas: list[dict[str, Any]]) -> Any:
        return self._model.bind_tools(tool_schemas)

    async def ainvoke(self, messages: list[Any]) -> Any:
        return await self._model.ainvoke(messages)
