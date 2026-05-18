"""Unit tests for OpenAI-compatible adapters (openai, deepseek, gemini).

Adapters share OpenAICompatibleProvider; differences are limited to the
base URL. Most tests are parametrized across the three providers via
subTest to avoid duplication.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import requests
from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.utils.llm import (
    ChatMessage,
    JsonSchema,
    ProviderConfig,
    get_provider,
)
from os_lms.os_lms.ai.utils.llm.errors import (
    LLMContextWindow,
    LLMError,
    LLMInvalidAuth,
    LLMRateLimit,
    LLMServerError,
)

from ._http_fakes import FakeResponse, RequestRecorder


COMPAT_PROVIDERS = [
    ("openai", "https://api.openai.com/v1"),
    ("deepseek", "https://api.deepseek.com/v1"),
    ("gemini", "https://generativelanguage.googleapis.com/v1beta/openai"),
]


def _success_handler(url, **kw):
    payload = kw.get("json") or {}
    return FakeResponse(
        200,
        json_body={
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "model": payload.get("model", "x"),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
        },
    )


class TestOpenAICompatibleRouting(UnitTestCase):
    def test_each_adapter_targets_its_base_url(self):
        for name, base in COMPAT_PROVIDERS:
            with self.subTest(provider=name):
                recorder = RequestRecorder(_success_handler)
                with patch.object(requests, "post", recorder):
                    provider = get_provider(
                        ProviderConfig(name=name, api_key="sk-x", default_model=f"{name}-m")
                    )
                    resp = provider.chat(messages=[ChatMessage(role="user", content="ping")])

                self.assertEqual(recorder.last_url, f"{base}/chat/completions")
                self.assertEqual(recorder.last_headers["Authorization"], "Bearer sk-x")
                self.assertEqual(resp.provider, name)
                self.assertEqual(resp.text, "ok")
                self.assertEqual(resp.usage.total_tokens, 4)

    def test_system_prepended_as_first_message(self):
        recorder = RequestRecorder(_success_handler)
        with patch.object(requests, "post", recorder):
            provider = get_provider(
                ProviderConfig(name="openai", api_key="x", default_model="gpt-4o")
            )
            provider.chat(
                messages=[ChatMessage(role="user", content="ciao")],
                system="Sei un cliente.",
            )
        msgs = recorder.last_payload["messages"]
        self.assertEqual(msgs[0], {"role": "system", "content": "Sei un cliente."})
        self.assertEqual(msgs[1], {"role": "user", "content": "ciao"})

    def test_response_format_serialized_as_json_schema(self):
        schema = JsonSchema(
            name="eval",
            schema={"type": "object", "properties": {"score": {"type": "integer"}}, "required": ["score"]},
        )
        recorder = RequestRecorder(_success_handler)
        with patch.object(requests, "post", recorder):
            provider = get_provider(
                ProviderConfig(name="openai", api_key="x", default_model="gpt-4o")
            )
            provider.chat(messages=[ChatMessage(role="user", content="x")], response_format=schema)

        rf = recorder.last_payload["response_format"]
        self.assertEqual(rf["type"], "json_schema")
        self.assertEqual(rf["json_schema"]["name"], "eval")
        self.assertTrue(rf["json_schema"]["strict"])

    def test_model_override_takes_priority_over_default(self):
        recorder = RequestRecorder(_success_handler)
        with patch.object(requests, "post", recorder):
            provider = get_provider(
                ProviderConfig(name="openai", api_key="x", default_model="gpt-4o-mini")
            )
            provider.chat(messages=[ChatMessage(role="user", content="x")], model="gpt-4.1")

        self.assertEqual(recorder.last_payload["model"], "gpt-4.1")


class TestOpenAICompatibleErrorMapping(UnitTestCase):
    def _provider(self):
        return get_provider(ProviderConfig(name="openai", api_key="x", default_model="gpt-4o"))

    def _patch_status(self, status: int, body: dict | None = None):
        body = body or {"error": {"message": f"http {status}"}}

        def handler(url, **kw):
            return FakeResponse(status, json_body=body)

        return patch.object(requests, "post", handler)

    def test_401_raises_invalid_auth(self):
        with self._patch_status(401):
            with self.assertRaises(LLMInvalidAuth):
                self._provider().chat(messages=[ChatMessage(role="user", content="x")])

    def test_403_raises_invalid_auth(self):
        with self._patch_status(403):
            with self.assertRaises(LLMInvalidAuth):
                self._provider().chat(messages=[ChatMessage(role="user", content="x")])

    def test_429_raises_rate_limit(self):
        with self._patch_status(429):
            with self.assertRaises(LLMRateLimit):
                self._provider().chat(messages=[ChatMessage(role="user", content="x")])

    def test_5xx_raises_server_error(self):
        with self._patch_status(503):
            with self.assertRaises(LLMServerError):
                self._provider().chat(messages=[ChatMessage(role="user", content="x")])

    def test_400_with_context_keyword_raises_context_window(self):
        with self._patch_status(
            400, body={"error": {"message": "This model's maximum context length is 4096 tokens."}}
        ):
            with self.assertRaises(LLMContextWindow):
                self._provider().chat(messages=[ChatMessage(role="user", content="x")])

    def test_400_generic_raises_base_llm_error(self):
        with self._patch_status(400, body={"error": {"message": "bad request"}}):
            with self.assertRaises(LLMError) as cm:
                self._provider().chat(messages=[ChatMessage(role="user", content="x")])
            self.assertNotIsInstance(cm.exception, (LLMRateLimit, LLMServerError, LLMInvalidAuth, LLMContextWindow))


class TestOpenAICompatibleStreaming(UnitTestCase):
    SSE = [
        'data: {"choices":[{"delta":{"role":"assistant","content":""}}]}',
        '',
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        '',
        'data: {"choices":[{"delta":{"content":" world"}}]}',
        '',
        'data: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":3,"completion_tokens":2}}',
        '',
        'data: [DONE]',
    ]

    def test_streaming_emits_chunks_and_final_usage(self):
        def handler(url, **kw):
            return FakeResponse(200, sse_lines=self.SSE)

        with patch.object(requests, "post", handler):
            provider = get_provider(ProviderConfig(name="openai", api_key="x", default_model="gpt-4o"))
            chunks = list(provider.chat(messages=[ChatMessage(role="user", content="hi")], stream=True))

        text = "".join(c.delta for c in chunks)
        self.assertEqual(text, "Hello world")
        self.assertEqual(chunks[-1].finish_reason, "stop")
        self.assertIsNotNone(chunks[-1].usage)
        self.assertEqual(chunks[-1].usage.total_tokens, 5)
