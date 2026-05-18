"""Anthropic Claude adapter.

Native Messages API (https://api.anthropic.com/v1/messages). Unlike the
OpenAI-compatible providers, Anthropic has:
- header `x-api-key` instead of `Authorization: Bearer`
- mandatory `anthropic-version` header
- `system` is a top-level field, not a message
- `max_tokens` is required (no default)
- streaming events use named SSE events (`message_start`, `content_block_delta`,
  `message_delta`, `message_stop`) rather than chunked deltas
- structured output via tool_use forcing (no native response_format)

If the official `anthropic` SDK is ever introduced, the import must live in
this module exclusively (encapsulation rule, see test_provider_encapsulation).
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import requests

from ..config import ProviderConfig
from ..errors import (
    LLMContextWindow,
    LLMError,
    LLMInvalidAuth,
    LLMRateLimit,
    LLMServerError,
    LLMTimeout,
    LLMUnsupported,
)
from ..provider import (
    ChatChunk,
    ChatMessage,
    ChatResponse,
    JsonSchema,
    LLMProvider,
    Usage,
)
from ..registry import register

DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
DEFAULT_VERSION = "2023-06-01"
STRUCTURED_TOOL_NAME = "respond_with_schema"


@register("anthropic")
class AnthropicProvider(LLMProvider):
    """Adapter for Anthropic's Messages API."""

    def __init__(self, config: ProviderConfig):
        self._config = config
        self._base_url = (config.base_url or DEFAULT_BASE_URL).rstrip("/")
        self._model = config.default_model
        # Version is configurable via extra_headers for future migrations.
        self._version = (config.extra_headers or {}).get("anthropic-version", DEFAULT_VERSION)

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
        payload = self._build_payload(
            messages=messages,
            system=system,
            model=model or self._model,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stop=stop,
            response_format=response_format,
            stream=stream,
        )
        headers = self._build_headers()
        url = f"{self._base_url}/messages"

        if stream:
            return self._stream(url, payload, headers, timeout)
        return self._send_blocking(url, payload, headers, timeout, response_format)

    def health_check(self) -> bool:
        try:
            resp = self.chat(
                messages=[ChatMessage(role="user", content="ping")],
                max_tokens=1,
                timeout=10.0,
            )
            assert isinstance(resp, ChatResponse)
            return True
        except LLMError:
            return False

    # -- internals --

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "x-api-key": self._config.api_key,
            "anthropic-version": self._version,
            "Content-Type": "application/json",
        }
        for k, v in (self._config.extra_headers or {}).items():
            if k.lower() == "anthropic-version":
                continue
            headers[k] = v
        return headers

    def _build_payload(
        self,
        *,
        messages: list[ChatMessage],
        system: str | None,
        model: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
        stop: list[str] | None,
        response_format: JsonSchema | None,
        stream: bool,
    ) -> dict[str, Any]:
        msgs: list[dict[str, Any]] = []
        for m in messages:
            role = m.role
            if role == "system":
                # Anthropic does not accept system inside messages; merge into top-level system.
                system = (system + "\n\n" + m.content) if system else m.content
                continue
            if role == "tool":
                # Not supported in this MVP; surface as an LLMUnsupported on send.
                msgs.append({"role": "user", "content": m.content})
                continue
            msgs.append({"role": role, "content": m.content})

        payload: dict[str, Any] = {
            "model": model,
            "messages": msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": stream,
        }
        if system:
            payload["system"] = system
        if stop:
            payload["stop_sequences"] = stop
        if response_format is not None:
            if stream:
                raise LLMUnsupported(
                    "Anthropic adapter does not support streaming with response_format yet",
                    provider=self.name,
                )
            payload["tools"] = [
                {
                    "name": STRUCTURED_TOOL_NAME,
                    "description": response_format.name,
                    "input_schema": response_format.schema,
                }
            ]
            payload["tool_choice"] = {"type": "tool", "name": STRUCTURED_TOOL_NAME}
        return payload

    def _send_blocking(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout: float,
        response_format: JsonSchema | None,
    ) -> ChatResponse:
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
        except requests.Timeout as e:
            raise LLMTimeout(str(e), provider=self.name, cause=e) from e
        except requests.RequestException as e:
            raise LLMServerError(str(e), provider=self.name, cause=e) from e

        self._check_status(r)
        try:
            data = r.json()
        except ValueError as e:
            raise LLMError("Provider returned non-JSON response", provider=self.name, cause=e) from e
        return self._parse_blocking(data, response_format)

    def _parse_blocking(
        self,
        data: dict[str, Any],
        response_format: JsonSchema | None,
    ) -> ChatResponse:
        content_blocks = data.get("content") or []
        text = ""
        if response_format is not None:
            text = _extract_tool_input(content_blocks)
            if not text:
                # Provider returned plain text instead of tool_use — surface as parsing failure.
                raise LLMError(
                    "Structured output requested but provider did not call the schema tool",
                    provider=self.name,
                )
        else:
            text = _extract_text(content_blocks)

        usage = data.get("usage") or {}
        return ChatResponse(
            text=text,
            finish_reason=_map_stop_reason(data.get("stop_reason")),
            usage=Usage(
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
            ),
            model=data.get("model", self._model),
            provider=self.name,
            raw=data,
        )

    def _stream(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout: float,
    ) -> Iterator[ChatChunk]:
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout, stream=True)
        except requests.Timeout as e:
            raise LLMTimeout(str(e), provider=self.name, cause=e) from e
        except requests.RequestException as e:
            raise LLMServerError(str(e), provider=self.name, cause=e) from e

        with r:
            self._check_status(r)
            current_event: str | None = None
            input_tokens = 0
            output_tokens = 0
            stop_reason: str | None = None
            for line in r.iter_lines(decode_unicode=True):
                if line is None or line == "":
                    current_event = None
                    continue
                if line.startswith("event: "):
                    current_event = line[7:].strip()
                    continue
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                try:
                    evt = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                if current_event == "message_start":
                    msg = evt.get("message") or {}
                    usage = msg.get("usage") or {}
                    input_tokens = usage.get("input_tokens", 0)
                    output_tokens = usage.get("output_tokens", 0)
                elif current_event == "content_block_delta":
                    delta = evt.get("delta") or {}
                    if delta.get("type") == "text_delta":
                        yield ChatChunk(delta=delta.get("text", ""))
                elif current_event == "message_delta":
                    delta = evt.get("delta") or {}
                    if "stop_reason" in delta:
                        stop_reason = delta["stop_reason"]
                    usage = evt.get("usage") or {}
                    if "output_tokens" in usage:
                        output_tokens = usage["output_tokens"]
                elif current_event == "message_stop":
                    yield ChatChunk(
                        delta="",
                        finish_reason=_map_stop_reason(stop_reason),
                        usage=Usage(prompt_tokens=input_tokens, completion_tokens=output_tokens),
                    )
                    break

    def _check_status(self, r: requests.Response) -> None:
        if 200 <= r.status_code < 300:
            return
        body = _read_body_safely(r)
        msg = _extract_error_message(body) or f"HTTP {r.status_code}"
        if r.status_code in (401, 403):
            raise LLMInvalidAuth(msg, provider=self.name)
        if r.status_code == 429:
            raise LLMRateLimit(msg, provider=self.name)
        if r.status_code == 400 and _is_context_window_error(msg):
            raise LLMContextWindow(msg, provider=self.name)
        if r.status_code >= 500:
            raise LLMServerError(msg, provider=self.name)
        raise LLMError(msg, provider=self.name)


def _extract_text(blocks: list[dict[str, Any]]) -> str:
    parts = [b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
    return "".join(parts)


def _extract_tool_input(blocks: list[dict[str, Any]]) -> str:
    for b in blocks:
        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == STRUCTURED_TOOL_NAME:
            tool_input = b.get("input") or {}
            return json.dumps(tool_input)
    return ""


def _map_stop_reason(stop_reason: str | None) -> str:
    """Translate Anthropic stop_reason to the normalized finish_reason vocabulary."""
    if stop_reason in (None, "end_turn", "stop_sequence"):
        return "stop"
    if stop_reason == "max_tokens":
        return "length"
    if stop_reason == "tool_use":
        return "tool_calls"
    return stop_reason


def _read_body_safely(r: requests.Response) -> str:
    try:
        return r.text
    except Exception:
        return ""


def _extract_error_message(body: str) -> str | None:
    if not body:
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return body[:200]
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            return err.get("message") or err.get("type")
        if isinstance(err, str):
            return err
    return body[:200]


def _is_context_window_error(msg: str) -> bool:
    lo = msg.lower()
    return ("context" in lo and "length" in lo) or "too many tokens" in lo or "max input length" in lo
