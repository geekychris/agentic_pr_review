"""OpenAI-based AI provider."""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from code_review_agent.ai.base import AIProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    """AI provider backed by the OpenAI API (GPT-4o, etc.)."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "gpt-4o",
        org_id: str = "",
    ) -> None:
        kwargs: dict[str, Any] = {}
        if api_key:
            kwargs["api_key"] = api_key
        if org_id:
            kwargs["organization"] = org_id
        self._client = AsyncOpenAI(**kwargs)
        self.model = model

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: dict[str, str] | None = None,
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        logger.debug("OpenAI request: model=%s, messages=%d", self.model, len(messages))
        response = await self._client.chat.completions.create(**kwargs)
        text = response.choices[0].message.content or ""
        logger.debug("OpenAI response: %d chars", len(text))
        return text

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        text = await self.chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.error("Failed to parse AI response as JSON: %s", text[:200])
            return {"error": "Invalid JSON response", "raw": text}

    async def close(self) -> None:
        await self._client.close()
