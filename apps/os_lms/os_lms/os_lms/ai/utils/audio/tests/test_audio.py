"""Unit tests for the audio provider abstraction (ai/utils/audio).

Pure tests — no DB, no network. They exercise the registry, config wiring, the
mock adapter, and the OpenAI adapter's request-shaping helpers.
"""
from __future__ import annotations

from dataclasses import dataclass

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.utils import audio
from os_lms.os_lms.ai.utils.audio.provider import AudioProvider
from os_lms.os_lms.ai.utils.audio.providers.openai import (
	OpenAIAudioProvider,
	_ext_for_mime,
)


@dataclass
class _FakeSettings:
	openai_key: str = "sk-test"
	openai_base_url: str = ""
	stt_model: str = ""
	tts_model: str = ""
	tts_voice: str = ""
	stt_provider: str = "openai"
	tts_provider: str = "openai"


class TestAudioRegistry(UnitTestCase):
	def test_only_capable_providers_registered(self):
		# DeepSeek and Anthropic have no audio API, so they must be absent.
		self.assertEqual(audio.list_audio_providers(), ["mock", "openai"])

	def test_unknown_provider_raises(self):
		with self.assertRaises(ValueError):
			audio.get_audio_provider(audio.AudioProviderConfig(name="nope"))


class TestAudioConfigWiring(UnitTestCase):
	def test_openai_defaults(self):
		cfg = audio.build_audio_config("openai", _FakeSettings())
		self.assertEqual(cfg.name, "openai")
		self.assertEqual(cfg.stt_model, "gpt-4o-mini-transcribe")
		self.assertEqual(cfg.tts_model, "gpt-4o-mini-tts")
		self.assertEqual(cfg.tts_voice, "alloy")
		self.assertIsNone(cfg.base_url)

	def test_openai_overrides(self):
		s = _FakeSettings(
			stt_model="whisper-1",
			tts_model="tts-1",
			tts_voice="nova",
			openai_base_url="https://proxy.example/v1",
		)
		cfg = audio.build_audio_config("openai", s)
		self.assertEqual(cfg.stt_model, "whisper-1")
		self.assertEqual(cfg.tts_model, "tts-1")
		self.assertEqual(cfg.tts_voice, "nova")
		self.assertEqual(cfg.base_url, "https://proxy.example/v1")

	def test_pick_provider_name(self):
		s = _FakeSettings(stt_provider="openai", tts_provider="")
		self.assertEqual(audio._pick_provider_name(s, "stt"), "openai")
		# empty -> default
		self.assertEqual(audio._pick_provider_name(s, "tts"), "openai")


class TestMockProvider(UnitTestCase):
	def test_transcribe_and_synthesize(self):
		prov = audio.get_audio_provider(audio.build_audio_config("mock", None))
		tr = prov.transcribe(b"0123456789", mime="audio/webm", language="it")
		self.assertEqual(tr.provider, "mock")
		self.assertIn("MOCK transcription", tr.text)
		sp = prov.synthesize("ciao", voice="alloy")
		self.assertEqual(sp.mime, "audio/mpeg")
		self.assertTrue(sp.audio.startswith(b"MOCK_AUDIO:"))


class TestUnsupportedDefault(UnitTestCase):
	def test_bare_provider_raises_unsupported(self):
		class _Empty(AudioProvider):
			name = "empty"

		with self.assertRaises(audio.AudioUnsupported):
			_Empty().transcribe(b"x", mime="audio/webm")
		with self.assertRaises(audio.AudioUnsupported):
			_Empty().synthesize("x", voice="alloy")


class TestOpenAIAdapterShaping(UnitTestCase):
	def test_base_url_resolution(self):
		cfg = audio.AudioProviderConfig(name="openai", api_key="sk-x")
		self.assertEqual(
			OpenAIAudioProvider(cfg)._base_url, "https://api.openai.com/v1"
		)
		cfg2 = audio.AudioProviderConfig(name="openai", base_url="https://h/v1/")
		self.assertEqual(OpenAIAudioProvider(cfg2)._base_url, "https://h/v1")

	def test_mime_to_extension(self):
		self.assertEqual(_ext_for_mime("audio/webm;codecs=opus"), "webm")
		self.assertEqual(_ext_for_mime("audio/mp4"), "mp4")
		self.assertEqual(_ext_for_mime("audio/ogg"), "ogg")
		# unknown mime falls back to webm
		self.assertEqual(_ext_for_mime("application/octet-stream"), "webm")

	def test_health_check_requires_key(self):
		with_key = OpenAIAudioProvider(
			audio.AudioProviderConfig(name="openai", api_key="k")
		)
		without_key = OpenAIAudioProvider(audio.AudioProviderConfig(name="openai"))
		self.assertTrue(with_key.health_check())
		self.assertFalse(without_key.health_check())
