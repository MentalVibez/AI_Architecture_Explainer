"""
provider.py — FastAPI dependency for the LLM provider.

Returns a shared AnthropicProvider instance. Import get_llm_provider
and use it as a FastAPI Depends() wherever you need the LLM.
"""

from app.llm.anthropic_provider import AnthropicProvider

_provider: AnthropicProvider | None = None


def get_llm_provider() -> AnthropicProvider:
    global _provider
    if _provider is None:
        _provider = AnthropicProvider()
    return _provider
