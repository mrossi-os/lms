"""Unit tests for the audio provider abstraction (ai/utils/audio).

Pure tests — no DB, no network. They exercise the registry, config wiring, the
mock adapter, and the OpenAI adapter's request-shaping helpers.
"""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.utils import audio
from os_lms.os_lms.ai.utils.audio.errors import AudioError
from os_lms.os_lms.ai.utils.audio.provider import AudioProvider
from os_lms.os_lms.ai.utils.audio.providers.gemini import (
	GeminiAudioProvider,
	_extract_audio,
	_extract_text,
	_gemini_model_or,
	_pcm_to_wav,
	_rate_from_mime,
	_redact,
)
from os_lms.os_lms.ai.utils.audio.providers.openai import (
	OpenAIAudioProvider,
	_ext_for_mime,
)


@dataclass
class _FakeSettings:
	openai_key: str = "sk-test"
	openai_base_url: str = ""
	gemini_key: str = "gm-test"
	stt_model: str = ""
	tts_model: str = ""
	tts_voice: str = ""
	stt_provider: str = "openai"
	tts_provider: str = "openai"


class TestAudioRegistry(UnitTestCase):
	def test_only_capable_providers_registered(self):
		# DeepSeek and Anthropic have no audio API, so they must be absent.
		self.assertEqual(audio.list_audio_providers(), ["gemini", "mock", "openai"])

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

	def test_gemini_wiring(self):
		# Gemini uses its own key; the OpenAI base URL override does not apply.
		s = _FakeSettings(gemini_key="gm-123", openai_base_url="https://proxy/v1")
		cfg = audio.build_audio_config("gemini", s)
		self.assertEqual(cfg.name, "gemini")
		self.assertEqual(cfg.api_key, "gm-123")
		self.assertIsNone(cfg.base_url)


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


class TestGeminiAdapterShaping(UnitTestCase):
	def _provider(self, **cfg):
		return GeminiAudioProvider(audio.AudioProviderConfig(name="gemini", **cfg))

	def test_base_url_resolution(self):
		prov = self._provider(api_key="gm-x")
		self.assertEqual(
			prov._base_url, "https://generativelanguage.googleapis.com/v1beta"
		)
		prov2 = self._provider(base_url="https://h/v1beta/")
		self.assertEqual(prov2._base_url, "https://h/v1beta")

	def test_model_sanitization(self):
		# Empty or cross-provider (OpenAI) models fall back to the Gemini default;
		# a real Gemini model is honored.
		self.assertEqual(_gemini_model_or("", "gemini-2.5-flash"), "gemini-2.5-flash")
		self.assertEqual(
			_gemini_model_or("gpt-4o-mini-tts", "gemini-2.5-flash"), "gemini-2.5-flash"
		)
		self.assertEqual(
			_gemini_model_or("gemini-2.5-pro", "gemini-2.5-flash"), "gemini-2.5-pro"
		)

	def test_stt_tts_model_defaults(self):
		# Settings still carry the OpenAI defaults -> adapter ignores them.
		prov = self._provider(stt_model="gpt-4o-mini-transcribe", tts_model="tts-1")
		self.assertEqual(prov._stt_model(None), GeminiAudioProvider.DEFAULT_STT_MODEL)
		self.assertEqual(prov._tts_model(None), GeminiAudioProvider.DEFAULT_TTS_MODEL)

	def test_voice_fallback(self):
		prov = self._provider()
		# An OpenAI voice ("alloy") is not a Gemini voice -> default.
		self.assertEqual(prov._voice("alloy"), "Kore")
		self.assertEqual(prov._voice(""), "Kore")
		# Known Gemini voices are honored, case-insensitively (canonical casing).
		self.assertEqual(prov._voice("kore"), "Kore")
		self.assertEqual(prov._voice("Puck"), "Puck")

	def test_rate_from_mime(self):
		self.assertEqual(_rate_from_mime("audio/L16;codec=pcm;rate=24000"), 24000)
		self.assertEqual(_rate_from_mime("audio/L16;rate=16000"), 16000)
		# No rate -> default 24000.
		self.assertEqual(_rate_from_mime("audio/wav"), 24000)
		self.assertEqual(_rate_from_mime(""), 24000)

	def test_pcm_to_wav_wraps_a_riff_header(self):
		pcm = b"\x00\x01" * 100
		wav = _pcm_to_wav(pcm, sample_rate=24000)
		self.assertTrue(wav.startswith(b"RIFF"))
		self.assertIn(b"WAVE", wav[:16])
		# WAV adds a 44-byte header, so the payload is strictly larger.
		self.assertGreater(len(wav), len(pcm))

	def test_extract_text(self):
		payload = {
			"candidates": [
				{"content": {"parts": [{"text": "Ciao "}, {"text": "mondo"}]}}
			]
		}
		self.assertEqual(_extract_text(payload), "Ciao mondo")
		self.assertEqual(_extract_text({}), "")

	def test_redact_masks_long_base64_data(self):
		body = {
			"contents": [
				{"parts": [{"inlineData": {"mimeType": "audio/webm", "data": "A" * 500}}]}
			]
		}
		red = _redact(body)
		blob = red["contents"][0]["parts"][0]["inlineData"]["data"]
		self.assertEqual(blob, "<base64: 500 chars>")
		# Short values and other keys are left untouched.
		self.assertEqual(red["contents"][0]["parts"][0]["inlineData"]["mimeType"], "audio/webm")

	def test_transcribe_returns_text_when_present(self):
		prov = self._provider(api_key="k")
		payload = {"candidates": [{"content": {"parts": [{"text": "ciao mondo"}]}}]}
		with patch.object(GeminiAudioProvider, "_post", return_value=payload):
			out = prov.transcribe(b"0123456789", mime="audio/webm", language="it")
		self.assertEqual(out.text, "ciao mondo")

	def test_transcribe_disables_thinking(self):
		# gemini-2.5-flash otherwise spends the whole output on "thoughts" and
		# returns no transcript, so STT must disable thinking.
		prov = self._provider(api_key="k")
		captured = {}

		def fake_post(self_, model, body, timeout):
			captured["body"] = body
			return {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}

		with patch.object(GeminiAudioProvider, "_post", fake_post):
			prov.transcribe(b"0123456789", mime="audio/webm", language="it")
		self.assertEqual(
			captured["body"]["generationConfig"]["thinkingConfig"]["thinkingBudget"], 0
		)

	def test_transcribe_raises_on_empty_transcript_with_reason(self):
		# Gemini returned a text-less candidate (e.g. the browser's WebM/Opus is
		# not understood): surface finishReason instead of a silent empty string.
		prov = self._provider(api_key="k")
		payload = {"candidates": [{"content": {"role": "model"}, "finishReason": "STOP"}]}
		with patch.object(GeminiAudioProvider, "_post", return_value=payload):
			with self.assertRaises(AudioError) as ctx:
				prov.transcribe(b"0123456789", mime="audio/webm", language="it")
		self.assertIn("finishReason=STOP", str(ctx.exception))

	def test_extract_audio(self):
		payload = {
			"candidates": [
				{
					"content": {
						"parts": [
							{
								"inlineData": {
									"mimeType": "audio/L16;rate=24000",
									"data": "QUJD",
								}
							}
						]
					}
				}
			]
		}
		data, mime = _extract_audio(payload)
		self.assertEqual(data, "QUJD")
		self.assertEqual(mime, "audio/L16;rate=24000")
		self.assertEqual(_extract_audio({}), ("", ""))

	def test_health_check_requires_key(self):
		self.assertTrue(self._provider(api_key="k").health_check())
		self.assertFalse(self._provider().health_check())
