"""Unit tests for the Phoenix TracingProvider wrapper.

The span tests need the optional ``tracing`` extra (OpenTelemetry SDK) and
are skipped without it; spans go to an in-memory exporter, never to Phoenix.
"""
from __future__ import annotations

import hashlib
import json
import unittest
from unittest.mock import patch

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.utils.llm import ChatMessage, ProviderConfig, get_provider
from os_lms.os_lms.ai.utils.llm import tracing
from os_lms.os_lms.ai.utils.llm.errors import LLMRateLimit

try:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from opentelemetry.trace import StatusCode

    HAS_OTEL = True
except ImportError:
    HAS_OTEL = False


def _mock_provider():
    return get_provider(ProviderConfig(name="mock", default_model="mock-1"))


class TestTracingDisabled(UnitTestCase):
    def test_returns_provider_unchanged_without_endpoint(self):
        provider = _mock_provider()
        with patch.object(tracing, "tracing_config", return_value=(None, None)):
            self.assertIs(tracing.wrap_for_tracing(provider, project="p"), provider)

    def test_returns_provider_unchanged_without_tracing_extra(self):
        provider = _mock_provider()
        with (
            patch.object(tracing, "tracing_config", return_value=("http://x/v1/traces", None)),
            patch.object(tracing, "_get_tracer", return_value=None),
        ):
            self.assertIs(tracing.wrap_for_tracing(provider, project="p"), provider)


@unittest.skipUnless(HAS_OTEL, "os_lms 'tracing' extra not installed")
class TestTracingProvider(UnitTestCase):
    def setUp(self):
        super().setUp()
        self.exporter = InMemorySpanExporter()
        tracer_provider = TracerProvider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        self.tracer = tracer_provider.get_tracer("test")

    def _wrap(self, inner, metadata=None):
        return tracing.TracingProvider(inner, self.tracer, metadata=metadata)

    def test_records_llm_span(self):
        wrapped = self._wrap(_mock_provider(), metadata={"case_id": "c1", "variant": "B"})
        response = wrapped.chat(
            [ChatMessage(role="user", content="Hello coach")],
            system="SYS PROMPT",
            temperature=0.2,
            max_tokens=50,
        )

        [span] = self.exporter.get_finished_spans()
        attrs = span.attributes
        self.assertEqual(attrs["openinference.span.kind"], "LLM")
        self.assertEqual(attrs["llm.provider"], "mock")
        self.assertEqual(attrs["llm.model_name"], "mock-1")
        self.assertEqual(attrs["llm.input_messages.0.message.role"], "system")
        self.assertEqual(attrs["llm.input_messages.0.message.content"], "SYS PROMPT")
        self.assertEqual(attrs["llm.input_messages.1.message.content"], "Hello coach")
        self.assertEqual(attrs["llm.output_messages.0.message.content"], response.text)
        self.assertEqual(attrs["llm.token_count.total"], response.usage.total_tokens)
        self.assertEqual(json.loads(attrs["llm.invocation_parameters"])["temperature"], 0.2)

        metadata = json.loads(attrs["metadata"])
        self.assertEqual(metadata["case_id"], "c1")
        self.assertEqual(metadata["variant"], "B")
        self.assertEqual(
            metadata["system_prompt_sha256"], hashlib.sha256(b"SYS PROMPT").hexdigest()
        )

    def test_returns_inner_response_unchanged(self):
        inner = _mock_provider()
        messages = [ChatMessage(role="user", content="ping")]
        self.assertEqual(self._wrap(inner).chat(messages), inner.chat(messages))

    def test_error_is_recorded_and_reraised(self):
        inner = _mock_provider()
        with patch.object(inner, "chat", side_effect=LLMRateLimit("slow down")):
            with self.assertRaises(LLMRateLimit):
                self._wrap(inner).chat([ChatMessage(role="user", content="x")])

        [span] = self.exporter.get_finished_spans()
        self.assertEqual(span.status.status_code, StatusCode.ERROR)
        self.assertEqual(span.events[0].name, "exception")

    def test_streaming_is_not_traced(self):
        chunks = list(
            self._wrap(_mock_provider()).chat([ChatMessage(role="user", content="a b")], stream=True)
        )
        self.assertTrue(chunks)
        self.assertEqual(self.exporter.get_finished_spans(), ())

    def test_attribute_failure_does_not_break_the_call(self):
        wrapped = self._wrap(_mock_provider())
        with patch.object(tracing.TracingProvider, "_request_attributes", side_effect=ValueError):
            response = wrapped.chat([ChatMessage(role="user", content="x")])
        self.assertTrue(response.text)

    def test_delegates_other_attributes(self):
        inner = _mock_provider()
        wrapped = self._wrap(inner)
        self.assertEqual(wrapped.name, "mock")
        self.assertEqual(wrapped.health_check(), inner.health_check())
