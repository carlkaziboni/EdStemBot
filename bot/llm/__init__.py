"""LLM package — provider factory and exports."""

from __future__ import annotations

from bot.llm.provider import LLMProvider


def get_llm_provider(provider: str, **kwargs) -> LLMProvider:
    """
    Factory function — return the correct LLMProvider based on config.

    Args:
        provider: One of "openai", "gemini", "claude".
        **kwargs: Provider-specific kwargs (api_key, model, etc.)

    Raises:
        ValueError: For unknown provider names.
        RuntimeError: If the required API key is missing.
    """
    from config.settings import settings

    if provider == "openai":
        api_key = kwargs.get("api_key") or settings.openai_api_key
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set in .env")
        from bot.llm.openai_provider import OpenAIProvider
        return OpenAIProvider(api_key=api_key)

    elif provider == "gemini":
        api_key = kwargs.get("api_key") or settings.google_api_key
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set in .env")
        from bot.llm.gemini_provider import GeminiProvider
        return GeminiProvider(api_key=api_key)

    elif provider == "claude":
        api_key = kwargs.get("api_key") or settings.anthropic_api_key
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set in .env")
        from bot.llm.claude_provider import ClaudeProvider
        return ClaudeProvider(api_key=api_key)

    else:
        raise ValueError(f"Unknown LLM provider: '{provider}'. Choose openai | gemini | claude")
