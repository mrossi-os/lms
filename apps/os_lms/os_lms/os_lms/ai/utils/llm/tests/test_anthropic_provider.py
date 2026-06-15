"""Unit tests for AnthropicProvider."""
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
    LLMInvalidAuth,
    LLMRateLimit,
    LLMServerError,
    LLMUnsupported,
)

from ._http_fakes import FakeResponse, RequestRecorder


def _make_provider() -> "object":
    return get_provider(
        ProviderConfig(name="anthropic", api_key="sk-ant-fake", default_model="claude-sonnet-4-5")
    )


def _text_response_handler(url, **kw):
    payload = kw.get("json") or {}
    return FakeResponse(
        200,
        json_body={
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": payload.get("model", "claude-sonnet-4-5"),
            "content": [{"type": "text", "text": "Buongiorno."}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 4, "output_tokens": 2},
        },
    )


class TestAnthropicRequestShape(UnitTestCase):
    def test_uses_x_api_key_header_and_version(self):
        recorder = RequestRecorder(_text_response_handler)
        with patch.object(requests, "post", recorder):
            _make_provider().chat(messages=[ChatMessage(role="user", content="ciao")])
        self.assertEqual(recorder.last_url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(recorder.last_headers["x-api-key"], "sk-ant-fake")
        self.assertEqual(recorder.last_headers["anthropic-version"], "2023-06-01")
        self.assertNotIn("Authorization", recorder.last_headers)

    def test_system_passed_as_top_level_field(self):
        recorder = RequestRecorder(_text_response_handler)
        with patch.object(requests, "post", recorder):
            _make_provider().chat(
                messages=[ChatMessage(role="user", content="x")],
                system="Sei un cliente.",
            )
        self.assertEqual(recorder.last_payload["system"], "Sei un cliente.")
        # system MUST NOT appear inside the messages list
        for msg in recorder.last_payload["messages"]:
            self.assertNotEqual(msg["role"], "system")

    def test_system_role_in_messages_merged_into_top_level(self):
        recorder = RequestRecorder(_text_response_handler)
        with patch.object(requests, "post", recorder):
            _make_provider().chat(
                messages=[
                    ChatMessage(role="system", content="extra"),
                    ChatMessage(role="user", content="x"),
                ],
                system="base",
            )
        self.assertEqual(recorder.last_payload["system"], "base\n\nextra")
        self.assertEqual(
            recorder.last_payload["messages"], [{"role": "user", "content": "x"}]
        )

    def test_stop_sequences_renamed(self):
        recorder = RequestRecorder(_text_response_handler)
        with patch.object(requests, "post", recorder):
            _make_provider().chat(
                messages=[ChatMessage(role="user", content="x")],
                stop=["STOP"],
            )
        self.assertEqual(recorder.last_payload["stop_sequences"], ["STOP"])
        self.assertNotIn("stop", recorder.last_payload)


def _tool_use_response_handler(input_payload: dict | None = None):
    """Return a handler that responds with a valid tool_use block."""
    body_input = input_payload if input_payload is not None else {"score": 0}

    def handler(url, **kw):
        return FakeResponse(
            200,
            json_body={
                "id": "msg",
                "model": "claude-sonnet-4-5",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tu",
                        "name": "respond_with_schema",
                        "input": body_input,
                    }
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    return handler


class TestAnthropicStructuredOutput(UnitTestCase):
    def test_response_format_uses_tool_use_forcing(self):
        recorder = RequestRecorder(_tool_use_response_handler({"score": 1}))
        schema = JsonSchema(name="eval", schema={"type": "object", "properties": {"score": {"type": "integer"}}})
        with patch.object(requests, "post", recorder):
            _make_provider().chat(
                messages=[ChatMessage(role="user", content="rate")],
                response_format=schema,
            )
        tools = recorder.last_payload["tools"]
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], "respond_with_schema")
        self.assertEqual(tools[0]["input_schema"], schema.schema)
        self.assertEqual(
            recorder.last_payload["tool_choice"],
            {"type": "tool", "name": "respond_with_schema"},
        )

    def test_tool_use_response_parsed_as_json_text(self):
        def handler(url, **kw):
            return FakeResponse(
                200,
                json_body={
                    "id": "msg_2",
                    "model": "claude-opus-4-7",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tu_1",
                            "name": "respond_with_schema",
                            "input": {"score": 85, "summary": "ok"},
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {"input_tokens": 9, "output_tokens": 5},
                },
            )

        schema = JsonSchema(name="x", schema={"type": "object"})
        with patch.object(requests, "post", handler):
            resp = _make_provider().chat(
                messages=[ChatMessage(role="user", content="rate")],
                response_format=schema,
            )
        parsed = json.loads(resp.text)
        self.assertEqual(parsed, {"score": 85, "summary": "ok"})
        self.assertEqual(resp.finish_reason, "tool_calls")

    def test_streaming_with_response_format_raises_unsupported(self):
        schema = JsonSchema(name="x", schema={"type": "object"})
        with self.assertRaises(LLMUnsupported):
            list(
                _make_provider().chat(
                    messages=[ChatMessage(role="user", content="x")],
                    response_format=schema,
                    stream=True,
                )
            )


class TestAnthropicErrorMapping(UnitTestCase):
    def _patch_status(self, status: int):
        def handler(url, **kw):
            return FakeResponse(
                status, json_body={"type": "error", "error": {"type": "x", "message": f"http {status}"}}
            )

        return patch.object(requests, "post", handler)

    def test_401(self):
        with self._patch_status(401):
            with self.assertRaises(LLMInvalidAuth):
                _make_provider().chat(messages=[ChatMessage(role="user", content="x")])

    def test_429(self):
        with self._patch_status(429):
            with self.assertRaises(LLMRateLimit):
                _make_provider().chat(messages=[ChatMessage(role="user", content="x")])

    def test_5xx(self):
        with self._patch_status(503):
            with self.assertRaises(LLMServerError):
                _make_provider().chat(messages=[ChatMessage(role="user", content="x")])


class TestAnthropicStreaming(UnitTestCase):
    SSE = [
        "event: message_start",
        'data: {"type":"message_start","message":{"id":"msg_3","model":"claude-sonnet-4-5","usage":{"input_tokens":4,"output_tokens":0}}}',
        "",
        "event: content_block_delta",
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Buongiorno"}}',
        "",
        "event: content_block_delta",
        'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" cliente."}}',
        "",
        "event: message_delta",
        'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":5}}',
        "",
        "event: message_stop",
        'data: {"type":"message_stop"}',
        "",
    ]

    def test_streaming_yields_text_and_final_usage(self):
        def handler(url, **kw):
            return FakeResponse(200, sse_lines=self.SSE)

        with patch.object(requests, "post", handler):
            chunks = list(
                _make_provider().chat(
                    messages=[ChatMessage(role="user", content="x")], stream=True
                )
            )
        text = "".join(c.delta for c in chunks)
        self.assertEqual(text, "Buongiorno cliente.")
        self.assertEqual(chunks[-1].finish_reason, "stop")
        self.assertEqual(chunks[-1].usage.total_tokens, 9)
