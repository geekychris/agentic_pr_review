"""Abstract base class for AI providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    """Interface that all AI providers must implement.

    To add a new provider (e.g. Anthropic), subclass this and implement
    the two abstract methods.  Then register it in ``get_provider()``.
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: dict[str, str] | None = None,
    ) -> str:
        """Send a chat completion request and return the assistant message text."""

    @abstractmethod
    async def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Like ``chat`` but parse the response as JSON."""

    async def close(self) -> None:  # noqa: B027
        """Clean up resources (optional override)."""


def get_provider(name: str, **kwargs: Any) -> AIProvider:
    """Factory: instantiate a provider by name.

    Parameters
    ----------
    name : str
        Provider identifier, e.g. ``"openai"``.
    **kwargs
        Passed through to the provider constructor (api_key, model, etc.).
    """
    if name == "openai":
        from code_review_agent.ai.openai_provider import OpenAIProvider

        return OpenAIProvider(**kwargs)
    raise ValueError(f"Unknown AI provider: {name!r}. Available: openai")
