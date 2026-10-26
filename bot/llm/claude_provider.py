"""Anthropic Claude LLM provider."""

from __future__ import annotations

import logging

from bot.llm.provider import LLMProvider

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class ClaudeProvider(LLMProvider):
    """
    LLM provider backed by Anthropic Claude.

    Args:
        api_key: Anthropic API key.
        model: Model ID (default: claude-3-haiku — fastest/cheapest).
    """

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL) -> None:
        import anthropic
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        max_tokens = kwargs.get("max_tokens", 512)

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = response.content[0].text if response.content else ""
        logger.debug("Claude response (%d chars)", len(text))
        return text
