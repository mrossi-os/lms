"""Unit tests for the audio endpoints (ai/audio/api.py).

The provider layer and settings loader are monkeypatched so the tests exercise
gating, input validation, and response shaping without DB rows or network.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.audio import api
from os_lms.os_lms.ai.utils.audio import build_audio_config, get_audio_provider


@dataclass
class _FakeSettings:
	stt_enabled: bool = True
	tts_enabled: bool = True
	tts_voice: str = "alloy"


def _mock_provider(_capability):
	return get_audio_provider(build_audio_config("mock", None))


class _AudioApiTestBase(UnitTestCase):
	def setUp(self):
		self._orig_load = api.load_settings
		self._orig_resolve = api.resolve_audio_provider
		api.resolve_audio_provider = _mock_provider

	def tearDown(self):
		api.load_settings = self._orig_load
		api.resolve_audio_provider = self._orig_resolve

	def _set_settings(self, **kw):
		api.load_settings = lambda: _FakeSettings(**kw)


class TestTranscribe(_AudioApiTestBase):
	def test_disabled_raises_permission(self):
		self._set_settings(stt_enabled=False)
		audio_b64 = base64.b64encode(b"abc").decode()
		with self.assertRaises(frappe.PermissionError):
			api.transcribe(audio=audio_b64)

	def test_enabled_returns_text(self):
		self._set_settings(stt_enabled=True)
		audio_b64 = base64.b64encode(b"0123456789").decode()
		out = api.transcribe(audio=audio_b64, mime="audio/webm", language="it")
		self.assertIn("MOCK transcription", out["text"])

	def test_empty_audio_raises(self):
		self._set_settings(stt_enabled=True)
		with self.assertRaises(frappe.ValidationError):
			api.transcribe(audio="")

	def test_invalid_base64_raises(self):
		self._set_settings(stt_enabled=True)
		with self.assertRaises(frappe.ValidationError):
			api.transcribe(audio="not valid base64 !!!")

	def test_data_url_prefix_is_stripped(self):
		self._set_settings(stt_enabled=True)
		payload = base64.b64encode(b"0123456789").decode()
		out = api.transcribe(audio=f"data:audio/webm;base64,{payload}")
		self.assertIn("MOCK transcription", out["text"])


class TestSynthesize(_AudioApiTestBase):
	def test_disabled_raises_permission(self):
		self._set_settings(tts_enabled=False)
		with self.assertRaises(frappe.PermissionError):
			api.synthesize(text="ciao")

	def test_empty_text_raises(self):
		self._set_settings(tts_enabled=True)
		with self.assertRaises(frappe.ValidationError):
			api.synthesize(text="   ")

	def test_enabled_returns_base64_audio(self):
		self._set_settings(tts_enabled=True)
		out = api.synthesize(text="ciao", voice="nova")
		decoded = base64.b64decode(out["audio"])
		self.assertTrue(decoded.startswith(b"MOCK_AUDIO:"))
		self.assertEqual(out["mime"], "audio/mpeg")
