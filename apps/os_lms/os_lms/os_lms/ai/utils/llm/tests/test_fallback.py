"""Unit tests for the fallback chain (chat_with_fallback)."""
from __future__ import annotations

from unittest.mock import patch

import frappe
import requests
from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.utils.llm import ChatMessage, chat_with_fallback
from os_lms.os_lms.ai.utils.llm.errors import LLMInvalidAuth, LLMRateLimit

from ._http_fakes import FakeResponse


def _err(status: int, msg: str = "x"):
    def handler(url, **kw):
        return FakeResponse(status, json_body={"error": {"message": msg}})

    return handler


def _ok():
    def handler(url, **kw):
        payload = kw.get("json") or {}
        return FakeResponse(
            200,
            json_body={
                "id": "x",
                "model": payload.get("model", "x"),
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    return handler


class TestFallbackChain(UnitTestCase):
    def setUp(self):
        super().setUp()
        self._original = {}
        doc = frappe.get_single("LMSA Settings")
        for f in (
            "simulation_chat_provider",
            "simulation_debrief_provider",
            "simulation_provider_default",
            "simulation_provider_fallback_order",
        ):
            self._original[f] = getattr(doc, f, None)

    def tearDown(self):
        doc = frappe.get_single("LMSA Settings")
        for f, v in self._original.items():
            setattr(doc, f, v)
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        super().tearDown()

    def _configure(self, *, chat="auto", default="openai", fallback="openai,gemini,mock"):
        doc = frappe.get_single("LMSA Settings")
        doc.simulation_chat_provider = chat
        doc.simulation_provider_default = default
        doc.simulation_provider_fallback_order = fallback
        doc.save(ignore_permissions=True)
        frappe.db.commit()

    def test_auto_falls_through_to_mock_when_http_providers_fail(self):
        self._configure(chat="auto")

        def handler(url, **kw):
            if "api.openai.com" in url or "generativelanguage" in url:
                return FakeResponse(503, json_body={"error": {"message": "down"}})
            raise AssertionError(f"unexpected URL: {url}")

        with patch.object(requests, "post", handler):
            resp = chat_with_fallback("chat", [ChatMessage(role="user", content="ping")])
        # Mock provider is the last entry and doesn't hit requests at all.
        self.assertEqual(resp.provider, "mock")

    def test_explicit_pin_disables_fallback(self):
        self._configure(chat="openai")
        with patch.object(requests, "post", _err(429)):
            with self.assertRaises(LLMRateLimit):
                chat_with_fallback("chat", [ChatMessage(role="user", content="ping")])

    def test_auth_error_is_never_eligible_for_fallback(self):
        self._configure(chat="auto")
        with patch.object(requests, "post", _err(401)):
            with self.assertRaises(LLMInvalidAuth):
                chat_with_fallback("chat", [ChatMessage(role="user", content="ping")])

    def test_override_pins_provider_and_skips_fallback(self):
        self._configure(chat="auto")
        with patch.object(requests, "post", _err(429)):
            with self.assertRaises(LLMRateLimit):
                chat_with_fallback(
                    "chat", [ChatMessage(role="user", content="ping")], override="openai"
                )
