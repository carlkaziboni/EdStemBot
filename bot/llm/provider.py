"""
Abstract LLM provider interface.

All concrete providers implement this interface so the rest of the
codebase never imports provider-specific code directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Base class for LLM provider implementations."""

    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        Generate a text response from the LLM.

        Args:
            system_prompt: System/instruction prompt.
            user_prompt: User message / query.
            **kwargs: Provider-specific options (temperature, max_tokens, etc.)

        Returns:
            Generated text string.
        """
        ...

    async def classify_topics(self, system_prompt: str, user_prompt: str) -> list[str]:
        """
        Convenience wrapper: generate and parse a JSON list of topics.

        Falls back to ["Other"] on parse errors.
        """
        import json
        import re

        raw = await self.generate(system_prompt, user_prompt, temperature=0.1)

        # Extract JSON array from response (even if LLM adds prose around it)
        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return ["Other"]
