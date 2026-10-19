from harness.llm.base import BaseLLM
from harness.llm.anthropic_client import AnthropicLLM

__all__ = ["BaseLLM", "AnthropicLLM"]


def get_openai_llm(**kwargs):
    from harness.llm.openai_client import OpenAILLM
    return OpenAILLM(**kwargs)
