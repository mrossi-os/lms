"""Provider-agnostic LLM abstraction.

All business code in os_lms consumes LLMProvider through this module.
Concrete adapters live in providers/ and must encapsulate any SDK usage.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Literal


Role = Literal["system", "user", "assistant", "tool"]
FinishReason = Literal["stop", "length", "content_filter", "tool_calls", "error"]


@dataclass
class ChatMessage:
    role: Role
    content: str
    name: str | None = None


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class ChatResponse:
    text: str
    finish_reason: FinishReason
    usage: Usage
    model: str
    provider: str
    raw: dict = field(default_factory=dict)


@dataclass
class ChatChunk:
    delta: str
    finish_reason: FinishReason | None = None
    usage: Usage | None = None


@dataclass
class JsonSchema:
    name: str
    schema: dict
    strict: bool = True


class LLMProvider(ABC):
    """Abstract base for any LLM provider adapter.

    Implementations live in providers/ and may use the provider's official SDK
    internally; the SDK must never leak across this boundary.
    """

    name: str = ""

    @abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        top_p: float = 1.0,
        max_tokens: int = 1024,
        stop: list[str] | None = None,
        response_format: JsonSchema | None = None,
        stream: bool = False,
        timeout: float = 60.0,
    ) -> ChatResponse | Iterator[ChatChunk]:
        """Send a chat completion request. Returns ChatResponse, or an iterator
        of ChatChunk when stream=True."""

    @abstractmethod
    def health_check(self) -> bool:
        """Lightweight ping used to validate configuration."""
