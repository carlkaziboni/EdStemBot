"""OpenAI LLM provider (GPT-4o / GPT-4o-mini)."""

from __future__ import annotations

import logging

from bot.llm.provider import LLMProvider

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(LLMProvider):
    """
    LLM provider backed by OpenAI's Chat Completions API.

    Args:
        api_key: OpenAI API key.
        model: Model to use (default: gpt-4o-mini for cost efficiency).
    """

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL) -> None:
        import openai
        self._client = openai.AsyncOpenAI(api_key=api_key)
        self._model = model

    async def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        temperature = kwargs.get("temperature", 0.2)
        max_tokens = kwargs.get("max_tokens", 512)

        response = await self._client.chat.completions.create(
            model=self._model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or ""
        logger.debug("OpenAI response (%d chars)", len(content))
        return content
