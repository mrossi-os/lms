"""Adapter for any OpenAI Chat Completions-compatible HTTP endpoint.

Speaks the OpenAI Chat Completions protocol over `requests` (already in the
Frappe env). Concrete adapters — OpenAI, DeepSeek, Gemini OpenAI-compat,
Groq, Together, Ollama, vLLM, ... — just override DEFAULT_BASE_URL and
register under their own name.

Stays SDK-free on purpose: the openai package would force a hard dependency
that the encapsulation rule reserves for OpenAIProvider exclusively if/when
we decide to switch.
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
)
from ..provider import (
    ChatChunk,
    ChatMessage,
    ChatResponse,
    JsonSchema,
    LLMProvider,
    Usage,
)


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI Chat Completions over HTTP. Stateless. Safe to instantiate per call."""

    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def __init__(self, config: ProviderConfig):
        self._config = config
        self._base_url = (config.base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._model = config.default_model

    # -- public API --

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
        url = f"{self._base_url}/chat/completions"

        if stream:
            return self._stream(url, payload, headers, timeout)
        return self._send_blocking(url, payload, headers, timeout)

    def health_check(self) -> bool:
        """Cheap probe: minimal request that validates auth + base_url."""
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
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        if self._config.organization:
            headers["OpenAI-Organization"] = self._config.organization
        if self._config.extra_headers:
            headers.update(self._config.extra_headers)
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
        if system:
            msgs.append({"role": "system", "content": system})
        for m in messages:
            msgs.append({"role": m.role, "content": m.content})

        payload: dict[str, Any] = {
            "model": model,
            "messages": msgs,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if stop:
            payload["stop"] = stop
        if response_format is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_format.name,
                    "schema": response_format.schema,
                    "strict": response_format.strict,
                },
            }
        if stream:
            payload["stream_options"] = {"include_usage": True}
        return payload

    def _send_blocking(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout: float,
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
        return self._parse_blocking(data)

    def _parse_blocking(self, data: dict[str, Any]) -> ChatResponse:
        choices = data.get("choices") or []
        if not choices:
            raise LLMError("Empty choices in response", provider=self.name)
        choice = choices[0]
        message = choice.get("message") or {}
        usage = data.get("usage") or {}
        return ChatResponse(
            text=message.get("content") or "",
            finish_reason=choice.get("finish_reason") or "stop",
            usage=Usage(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
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
            for line in r.iter_lines(decode_unicode=True):
                chunk = self._parse_stream_line(line)
                if chunk is _STREAM_DONE:
                    break
                if chunk is not None:
                    yield chunk

    def _parse_stream_line(self, line: str) -> ChatChunk | object | None:
        """Parse one SSE line. Returns:
        - _STREAM_DONE sentinel when [DONE] is seen
        - ChatChunk for a content/finish delta
        - None for keep-alives or unparseable lines
        """
        if not line:
            return None
        if line.startswith("data: "):
            data_str = line[6:]
        elif line.startswith(":"):  # comment / keep-alive
            return None
        else:
            data_str = line
        if data_str == "[DONE]":
            return _STREAM_DONE
        try:
            payload = json.loads(data_str)
        except json.JSONDecodeError:
            return None
        return _chunk_from_payload(payload)

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


_STREAM_DONE = object()


def _chunk_from_payload(payload: dict[str, Any]) -> ChatChunk | None:
    choices = payload.get("choices") or []
    delta_text = ""
    finish_reason = None
    if choices:
        c0 = choices[0]
        finish_reason = c0.get("finish_reason")
        delta_text = (c0.get("delta") or {}).get("content") or ""
    usage = None
    if payload.get("usage"):
        u = payload["usage"]
        usage = Usage(
            prompt_tokens=u.get("prompt_tokens", 0),
            completion_tokens=u.get("completion_tokens", 0),
        )
    if not delta_text and finish_reason is None and usage is None:
        return None
    return ChatChunk(delta=delta_text, finish_reason=finish_reason, usage=usage)


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
    return ("context" in lo and "length" in lo) or "too many tokens" in lo
