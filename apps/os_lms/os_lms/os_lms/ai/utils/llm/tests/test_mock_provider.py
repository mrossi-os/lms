"""Unit tests for the MockProvider deterministic adapter."""
from __future__ import annotations

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.utils.llm import (
    ChatChunk,
    ChatMessage,
    JsonSchema,
    ProviderConfig,
    get_provider,
)


def _make_provider() -> "object":
    return get_provider(ProviderConfig(name="mock", default_model="mock-1"))


class TestMockProvider(UnitTestCase):
    def test_blocking_response_shape(self):
        provider = _make_provider()
        resp = provider.chat(messages=[ChatMessage(role="user", content="hello")])

        self.assertEqual(resp.provider, "mock")
        self.assertEqual(resp.model, "mock-1")
        self.assertEqual(resp.finish_reason, "stop")
        self.assertIn("hello", resp.text)
        self.assertGreater(resp.usage.prompt_tokens, 0)
        self.assertGreater(resp.usage.completion_tokens, 0)

    def test_is_deterministic(self):
        provider = _make_provider()
        a = provider.chat(messages=[ChatMessage(role="user", content="ping")])
        b = provider.chat(messages=[ChatMessage(role="user", content="ping")])
        self.assertEqual(a.text, b.text)

    def test_different_inputs_produce_different_outputs(self):
        provider = _make_provider()
        a = provider.chat(messages=[ChatMessage(role="user", content="A")])
        b = provider.chat(messages=[ChatMessage(role="user", content="B")])
        self.assertNotEqual(a.text, b.text)

    def test_streaming_concatenates_to_blocking(self):
        provider = _make_provider()
        msg = [ChatMessage(role="user", content="streaming smoke test")]
        blocking = provider.chat(messages=msg)
        chunks = list(provider.chat(messages=msg, stream=True))
        joined = "".join(c.delta for c in chunks)
        self.assertEqual(joined, blocking.text)
        self.assertIsInstance(chunks[-1], ChatChunk)
        self.assertEqual(chunks[-1].finish_reason, "stop")
        self.assertIsNotNone(chunks[-1].usage)

    def test_response_format_returns_valid_json(self):
        import json

        schema = JsonSchema(
            name="eval",
            schema={
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "default": 9},
                    "summary": {"type": "string"},
                },
                "required": ["score", "summary"],
            },
        )
        provider = _make_provider()
        resp = provider.chat(messages=[ChatMessage(role="user", content="rate")], response_format=schema)
        parsed = json.loads(resp.text)
        self.assertEqual(parsed["score"], 9)
        self.assertIn("summary", parsed)

    def test_health_check_is_true(self):
        self.assertTrue(_make_provider().health_check())
