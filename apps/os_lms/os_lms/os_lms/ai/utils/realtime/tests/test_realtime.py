"""Unit tests for the realtime provider abstraction (ai/utils/realtime).

Pure tests — no DB, no network. Exercise the registry, config wiring, the
mock adapter's create_session, and transcript-event parsing.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

from frappe.tests import UnitTestCase
from os_lms.os_lms.ai.utils import realtime
from os_lms.os_lms.ai.utils.realtime.errors import (
	RealtimeInvalidAuth,
	RealtimeRateLimit,
	RealtimeServerError,
)
from os_lms.os_lms.ai.utils.realtime.provider import (
	RealtimeProvider,
	RealtimeSession,
	RealtimeSessionConfig,
)
from os_lms.os_lms.ai.utils.realtime.providers.gemini_live import (
	GeminiLiveProvider,
)
from os_lms.os_lms.ai.utils.realtime.providers.gemini_live import (
	_parse_event as _gemini_parse_event,
)
from os_lms.os_lms.ai.utils.realtime.providers.openai_realtime import (
	OpenAIRealtimeProvider,
	_parse_event,
	_session_body,
)


@dataclass
class _FakeSettings:
	realtime_enabled: bool = True
	realtime_provider: str = "openai"
	realtime_model: str = ""
	realtime_voice: str = ""
	turn_detection: str = "server_vad"
	realtime_max_session_seconds: int = 300
	openai_key: str = "sk-test"
	openai_base_url: str = ""
	gemini_key: str = "gm-test"


def _cfg() -> RealtimeSessionConfig:
	return RealtimeSessionConfig(
		instructions="You are a recruiter.",
		voice="marin",
		model="mock-realtime",
		turn_detection="server_vad",
		input_language="it",
		max_session_seconds=300,
		session_label="abc123",
	)


class TestRealtimeRegistry(UnitTestCase):
	def test_mock_is_registered(self):
		self.assertIn("mock", realtime.list_realtime_providers())

	def test_unknown_provider_raises(self):
		with self.assertRaises(ValueError):
			realtime.get_realtime_provider(realtime.RealtimeProviderConfig(name="nope"))


class TestMockProvider(UnitTestCase):
	def test_create_session_is_deterministic(self):
		provider = realtime.get_realtime_provider(
			realtime.RealtimeProviderConfig(name="mock", default_model="mock-realtime")
		)
		session = provider.create_session(_cfg())
		self.assertIsInstance(session, RealtimeSession)
		self.assertEqual(session.provider, "mock")
		self.assertEqual(session.transport, "mock")
		self.assertTrue(session.client_secret.startswith("mock-secret-"))
		self.assertEqual(session.voice, "marin")

	def test_parse_transcript_event_user(self):
		provider = realtime.get_realtime_provider(realtime.RealtimeProviderConfig(name="mock"))
		ev = provider.parse_transcript_event({"role": "user", "text": "Hello", "final": True})
		self.assertEqual((ev.role, ev.text, ev.final), ("user", "Hello", True))

	def test_parse_transcript_event_ignores_non_final(self):
		provider = realtime.get_realtime_provider(realtime.RealtimeProviderConfig(name="mock"))
		self.assertIsNone(provider.parse_transcript_event({"role": "user", "text": "He", "final": False}))


class TestConfigWiring(UnitTestCase):
	def test_openai_defaults(self):
		cfg = realtime.build_realtime_config("openai", _FakeSettings())
		self.assertEqual(cfg.name, "openai")
		self.assertEqual(cfg.default_model, "gpt-realtime-2")
		self.assertEqual(cfg.voice, "marin")
		self.assertEqual(cfg.max_session_seconds, 300)
		self.assertEqual(cfg.api_key, "sk-test")

	def test_unknown_config_raises(self):
		with self.assertRaises(ValueError):
			realtime.build_realtime_config("nope", _FakeSettings())


# ---------------------------------------------------------------------------
# Task 2: OpenAI Realtime adapter
# ---------------------------------------------------------------------------


class TestOpenAIParseEvent(UnitTestCase):
	def test_user_transcript_completed(self):
		ev = _parse_event(
			{
				"type": "conversation.item.input_audio_transcription.completed",
				"transcript": "Buongiorno",
			}
		)
		self.assertEqual((ev.role, ev.text, ev.final), ("user", "Buongiorno", True))

	def test_assistant_transcript_done(self):
		ev = _parse_event(
			{
				"type": "response.output_audio_transcript.done",
				"transcript": "Piacere di conoscerla",
			}
		)
		self.assertEqual(ev.role, "assistant")
		self.assertTrue(ev.final)

	def test_delta_is_ignored(self):
		self.assertIsNone(
			_parse_event(
				{
					"type": "response.output_audio_transcript.delta",
					"delta": "Pia",
				}
			)
		)

	def test_unrelated_event_is_ignored(self):
		self.assertIsNone(_parse_event({"type": "response.created"}))


class TestOpenAISessionBody(UnitTestCase):
	def test_body_carries_persona_and_voice(self):
		cfg = _cfg()
		config = realtime.build_realtime_config("openai", _FakeSettings())
		body = _session_body(cfg, config)
		# instructions and voice must reach the provider; api key must not be here.
		self.assertIn("session", body)
		self.assertEqual(body["session"]["instructions"], "You are a recruiter.")
		self.assertEqual(body["session"]["audio"]["output"]["voice"], "marin")


class TestOpenAICreateSession(UnitTestCase):
	def test_create_session_mints_ephemeral_token(self):
		config = realtime.build_realtime_config("openai", _FakeSettings())
		provider = OpenAIRealtimeProvider(config)

		class _Resp:
			status_code = 200

			@staticmethod
			def json():
				return {"value": "ek_abc", "expires_at": 1234567890}

		with patch(
			"os_lms.os_lms.ai.utils.realtime.providers.openai_realtime.requests.post",
			return_value=_Resp(),
		) as mocked:
			session = provider.create_session(_cfg())

		self.assertEqual(session.transport, "webrtc")
		self.assertEqual(session.client_secret, "ek_abc")
		self.assertEqual(session.expires_at, 1234567890)
		self.assertTrue(session.connect_url.endswith("/realtime/calls"))
		# api key sent as Bearer header, never in the returned session.
		_, kwargs = mocked.call_args
		self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sk-test")
		self.assertNotIn("sk-test", session.client_secret)


# ---------------------------------------------------------------------------
# Task 3: Gemini Live adapter
# ---------------------------------------------------------------------------


class TestGeminiParseEvent(UnitTestCase):
	def test_input_transcription(self):
		ev = _gemini_parse_event({"serverContent": {"inputTranscription": {"text": "Salve"}}})
		self.assertEqual((ev.role, ev.text, ev.final), ("user", "Salve", True))

	def test_output_transcription(self):
		ev = _gemini_parse_event({"serverContent": {"outputTranscription": {"text": "Benvenuto"}}})
		self.assertEqual(ev.role, "assistant")

	def test_other_frame_ignored(self):
		self.assertIsNone(_gemini_parse_event({"setupComplete": {}}))


class TestGeminiCreateSession(UnitTestCase):
	def test_create_session_returns_websocket_descriptor(self):
		config = realtime.build_realtime_config("gemini", _FakeSettings())
		provider = GeminiLiveProvider(config)

		class _Resp:
			status_code = 200

			@staticmethod
			def json():
				return {"name": "auth_tokens/abc", "expireTime": "2026-01-01T00:00:00Z"}

		with patch(
			"os_lms.os_lms.ai.utils.realtime.providers.gemini_live.requests.post",
			return_value=_Resp(),
		) as mocked:
			session = provider.create_session(_cfg())

		self.assertEqual(session.transport, "websocket")
		self.assertTrue(session.client_secret)
		self.assertTrue(session.connect_url.startswith("wss://"))
		# Everything is locked into the token server-side.
		_, kwargs = mocked.call_args
		setup = kwargs["json"]["bidiGenerateContentSetup"]
		self.assertEqual(setup["systemInstruction"]["parts"][0]["text"], "You are a recruiter.")
		self.assertEqual(setup["generationConfig"]["responseModalities"], ["AUDIO"])
		# The persona must NOT leak to the client: it only gets what it needs
		# to open the stream and manage its resumption handle.
		self.assertNotIn("instructions", session.extra)
		self.assertNotIn("voice", session.extra)
		self.assertIn("resumption_handle", session.extra)


# ---------------------------------------------------------------------------
# Fix 3: HTTP status → exception type (error-mapping)
# ---------------------------------------------------------------------------


class TestOpenAIStatusMapping(UnitTestCase):
	"""create_session maps HTTP error status codes to typed Realtime exceptions."""

	def _provider(self):
		config = realtime.build_realtime_config("openai", _FakeSettings())
		return OpenAIRealtimeProvider(config)

	def _resp(self, status_code):
		class _Resp:
			def __init__(self):
				self.status_code = status_code

			def json(self):
				return {"error": {"message": f"HTTP {self.status_code}"}}

		return _Resp()

	def test_401_raises_invalid_auth(self):
		with patch(
			"os_lms.os_lms.ai.utils.realtime.providers.openai_realtime.requests.post",
			return_value=self._resp(401),
		):
			with self.assertRaises(RealtimeInvalidAuth):
				self._provider().create_session(_cfg())

	def test_403_raises_invalid_auth(self):
		with patch(
			"os_lms.os_lms.ai.utils.realtime.providers.openai_realtime.requests.post",
			return_value=self._resp(403),
		):
			with self.assertRaises(RealtimeInvalidAuth):
				self._provider().create_session(_cfg())

	def test_429_raises_rate_limit(self):
		with patch(
			"os_lms.os_lms.ai.utils.realtime.providers.openai_realtime.requests.post",
			return_value=self._resp(429),
		):
			with self.assertRaises(RealtimeRateLimit):
				self._provider().create_session(_cfg())

	def test_500_raises_server_error(self):
		with patch(
			"os_lms.os_lms.ai.utils.realtime.providers.openai_realtime.requests.post",
			return_value=self._resp(500),
		):
			with self.assertRaises(RealtimeServerError):
				self._provider().create_session(_cfg())


class TestGeminiStatusMapping(UnitTestCase):
	"""create_session maps HTTP error status codes to typed Realtime exceptions."""

	def _provider(self):
		config = realtime.build_realtime_config("gemini", _FakeSettings())
		return GeminiLiveProvider(config)

	def _resp(self, status_code):
		class _Resp:
			def __init__(self):
				self.status_code = status_code

			def json(self):
				return {"error": {"message": f"HTTP {self.status_code}", "status": "ERROR"}}

		return _Resp()

	def test_401_raises_invalid_auth(self):
		with patch(
			"os_lms.os_lms.ai.utils.realtime.providers.gemini_live.requests.post",
			return_value=self._resp(401),
		):
			with self.assertRaises(RealtimeInvalidAuth):
				self._provider().create_session(_cfg())

	def test_403_raises_invalid_auth(self):
		with patch(
			"os_lms.os_lms.ai.utils.realtime.providers.gemini_live.requests.post",
			return_value=self._resp(403),
		):
			with self.assertRaises(RealtimeInvalidAuth):
				self._provider().create_session(_cfg())

	def test_429_raises_rate_limit(self):
		with patch(
			"os_lms.os_lms.ai.utils.realtime.providers.gemini_live.requests.post",
			return_value=self._resp(429),
		):
			with self.assertRaises(RealtimeRateLimit):
				self._provider().create_session(_cfg())

	def test_500_raises_server_error(self):
		with patch(
			"os_lms.os_lms.ai.utils.realtime.providers.gemini_live.requests.post",
			return_value=self._resp(500),
		):
			with self.assertRaises(RealtimeServerError):
				self._provider().create_session(_cfg())


# ---------------------------------------------------------------------------
# Task 5: OsLmsSettings realtime fields
# ---------------------------------------------------------------------------


class TestRealtimeSettingsDefaults(UnitTestCase):
	def test_oslmssettings_has_realtime_fields_with_defaults(self):
		from os_lms.os_lms.ai.utils.oslms_settings import OsLmsSettings

		s = OsLmsSettings(
			enabled=False,
			embedding_model="x",
			chunk_size=1,
			chunk_overlap=1,
			top_k=1,
			llm_model="x",
			openai_key="",
		)
		self.assertFalse(s.realtime_enabled)
		self.assertEqual(s.realtime_provider, "openai")
		self.assertEqual(s.turn_detection, "server_vad")
		self.assertEqual(s.realtime_max_session_seconds, 300)
