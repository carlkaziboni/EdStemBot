"""Google Gemini LLM provider."""

from __future__ import annotations

import logging

from bot.llm.provider import LLMProvider

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gemini-1.5-flash"


class GeminiProvider(LLMProvider):
    """
    LLM provider backed by Google Gemini.

    Args:
        api_key: Google AI Studio API key.
        model: Model name (default: gemini-1.5-flash).
    """

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL) -> None:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model)
        self._model_name = model

    async def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        import asyncio
        import google.generativeai as genai

        # Gemini doesn't have a separate system role in the basic SDK;
        # we prefix it into the user turn.
        combined = f"{system_prompt}\n\n{user_prompt}"

        # Gemini's Python SDK is synchronous — run in thread pool
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._model.generate_content(combined),
        )
        text = response.text or ""
        logger.debug("Gemini response (%d chars)", len(text))
        return text
