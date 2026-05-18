"""Deterministic mock provider for tests and local development.

Given the same messages, MockProvider returns the same reply. Useful for:
- Unit tests of the orchestrator without network/keys
- Cypress E2E with `simulation_chat_provider = "mock"`
- Replay of recorded sessions for didactic benchmarking
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator

from ..config import ProviderConfig
from ..provider import (
    ChatChunk,
    ChatMessage,
    ChatResponse,
    JsonSchema,
    LLMProvider,
    Usage,
)
from ..registry import register


@register("mock")
class MockProvider(LLMProvider):
    """Deterministic adapter. Returns canned replies derived from message hash.

    Behavior:
    - chat() returns ChatResponse with text = "MOCK[<8-char-hash>]: <last user msg, truncated>".
    - When response_format is set, returns a minimal JSON instance derived from the schema.
    - Token usage is computed as len(text)//4 (rough char->token estimate).
    - Streaming yields the response one word at a time.
    """

    def __init__(self, config: ProviderConfig):
        self._config = config
        self._model = config.default_model or "mock-1"

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
        text = self._build_reply(messages, system, response_format)
        prompt_tokens = self._estimate_tokens(messages, system)
        completion_tokens = max(1, len(text) // 4)
        usage = Usage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
        used_model = model or self._model

        if stream:
            return self._stream_words(text, usage)

        return ChatResponse(
            text=text,
            finish_reason="stop",
            usage=usage,
            model=used_model,
            provider=self.name,
            raw={"mock": True},
        )

    def health_check(self) -> bool:
        return True

    @staticmethod
    def _build_reply(
        messages: list[ChatMessage],
        system: str | None,
        response_format: JsonSchema | None,
    ) -> str:
        fingerprint = MockProvider._fingerprint(messages, system)
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )
        if response_format is not None:
            return json.dumps(_minimal_json_from_schema(response_format.schema))
        snippet = re.sub(r"\s+", " ", last_user.strip())[:80]
        return f"MOCK[{fingerprint}]: {snippet}" if snippet else f"MOCK[{fingerprint}]"

    @staticmethod
    def _fingerprint(messages: list[ChatMessage], system: str | None) -> str:
        h = hashlib.sha256()
        if system:
            h.update(b"S:")
            h.update(system.encode())
        for m in messages:
            h.update(b"|")
            h.update(m.role.encode())
            h.update(b":")
            h.update(m.content.encode())
        return h.hexdigest()[:8]

    @staticmethod
    def _estimate_tokens(messages: list[ChatMessage], system: str | None) -> int:
        chars = sum(len(m.content) for m in messages) + (len(system) if system else 0)
        return max(1, chars // 4)

    @staticmethod
    def _stream_words(text: str, usage: Usage) -> Iterator[ChatChunk]:
        words = text.split(" ")
        for i, word in enumerate(words):
            delta = word if i == 0 else " " + word
            is_last = i == len(words) - 1
            yield ChatChunk(
                delta=delta,
                finish_reason="stop" if is_last else None,
                usage=usage if is_last else None,
            )


def _minimal_json_from_schema(schema: dict) -> dict:
    """Build a minimal instance of a JSON schema, sufficient for structured-output
    tests. Supports object/array/string/number/integer/boolean."""
    return _build(schema)


def _build(node: dict):
    t = node.get("type")
    if t == "object":
        out: dict = {}
        props = node.get("properties", {})
        required = node.get("required", list(props))
        for key in required:
            if key in props:
                out[key] = _build(props[key])
        return out
    if t == "array":
        items = node.get("items", {"type": "string"})
        return [_build(items)]
    if t == "string":
        return node.get("default", "mock")
    if t == "integer":
        return int(node.get("default", 0))
    if t == "number":
        return float(node.get("default", 0))
    if t == "boolean":
        return bool(node.get("default", False))
    if "enum" in node:
        return node["enum"][0]
    return None
