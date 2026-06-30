"""OpenAI Realtime adapter (control plane only).

Mints an ephemeral client secret over the OpenAI HTTP API via `requests`
(SDK-free, same encapsulation rule as the OpenAI audio adapter). The audio
stream itself is WebRTC and is established by the client, never the backend.

- create_session -> POST {base_url}/realtime/client_secrets  (mint ek_... token)
- the client then POSTs its SDP offer to {base_url}/realtime/calls with the
  ephemeral token as Bearer.
- parse_transcript_event maps the two final-transcript events to a Turn.
"""
from __future__ import annotations

import requests

from ..config import RealtimeProviderConfig
from ..errors import (
	RealtimeError,
	RealtimeInvalidAuth,
	RealtimeRateLimit,
	RealtimeServerError,
	RealtimeTimeout,
)
from ..provider import (
	RealtimeProvider,
	RealtimeSession,
	RealtimeSessionConfig,
	TranscriptEvent,
)
from ..registry import register_realtime

_USER_EVENT = "conversation.item.input_audio_transcription.completed"
_ASSISTANT_EVENT = "response.output_audio_transcript.done"


@register_realtime("openai")
class OpenAIRealtimeProvider(RealtimeProvider):
	"""OpenAI Realtime over HTTP for token minting; WebRTC for the stream."""

	DEFAULT_BASE_URL = "https://api.openai.com/v1"
	DEFAULT_MODEL = "gpt-realtime-2"

	def __init__(self, config: RealtimeProviderConfig):
		self._config = config
		self._base_url = (config.base_url or self.DEFAULT_BASE_URL).rstrip("/")

	def create_session(self, cfg: RealtimeSessionConfig) -> RealtimeSession:
		if not self._config.api_key:
			raise RealtimeInvalidAuth("OpenAI api key is not configured", provider=self.name)
		url = f"{self._base_url}/realtime/client_secrets"
		headers = {
			"Authorization": f"Bearer {self._config.api_key}",
			"Content-Type": "application/json",
		}
		try:
			r = requests.post(
				url, headers=headers, json=_session_body(cfg, self._config), timeout=30.0
			)
		except requests.Timeout as e:
			raise RealtimeTimeout(str(e), provider=self.name, cause=e) from e
		except requests.RequestException as e:
			raise RealtimeServerError(str(e), provider=self.name, cause=e) from e

		self._check_status(r)
		payload = r.json()
		secret = payload.get("value") or payload.get("client_secret", {}).get("value", "")
		model = cfg.model or self._config.default_model or self.DEFAULT_MODEL
		return RealtimeSession(
			provider=self.name,
			model=model,
			transport="webrtc",
			client_secret=secret,
			connect_url=f"{self._base_url}/realtime/calls",
			expires_at=int(payload.get("expires_at", 0) or 0),
			voice=cfg.voice or self._config.voice or "marin",
			extra={"model": model},
		)

	def parse_transcript_event(self, event: dict) -> TranscriptEvent | None:
		return _parse_event(event)

	def health_check(self) -> bool:
		return bool(self._config.api_key)

	def _check_status(self, r: requests.Response) -> None:
		if 200 <= r.status_code < 300:
			return
		msg = _extract_error(r) or f"HTTP {r.status_code}"
		if r.status_code in (401, 403):
			raise RealtimeInvalidAuth(msg, provider=self.name)
		if r.status_code == 429:
			raise RealtimeRateLimit(msg, provider=self.name)
		if r.status_code >= 500:
			raise RealtimeServerError(msg, provider=self.name)
		raise RealtimeError(msg, provider=self.name)


def _session_body(cfg: RealtimeSessionConfig, config: RealtimeProviderConfig) -> dict:
	"""Build the client_secrets request body. The persona is `instructions`;
	input transcription is enabled so we get the candidate's text for Turns.

	NOTE: the exact field layout of the Realtime session object evolves — keep
	all provider-format coupling in this one helper.
	"""
	model = cfg.model or config.default_model or OpenAIRealtimeProvider.DEFAULT_MODEL
	return {
		"session": {
			"type": "realtime",
			"model": model,
			"instructions": cfg.instructions,
			"audio": {
				"input": {
					"transcription": {"model": "gpt-4o-transcribe", "language": cfg.input_language},
					"turn_detection": {"type": cfg.turn_detection},
				},
				"output": {"voice": cfg.voice or config.voice or "marin"},
			},
		}
	}


def _parse_event(event: dict) -> TranscriptEvent | None:
	etype = event.get("type")
	if etype == _USER_EVENT:
		return TranscriptEvent(role="user", text=event.get("transcript", "") or "", final=True)
	if etype == _ASSISTANT_EVENT:
		return TranscriptEvent(role="assistant", text=event.get("transcript", "") or "", final=True)
	return None


def _extract_error(r: requests.Response) -> str | None:
	try:
		data = r.json()
	except ValueError:
		return (r.text or "")[:200] or None
	if isinstance(data, dict):
		err = data.get("error")
		if isinstance(err, dict):
			return err.get("message") or err.get("type")
		if isinstance(err, str):
			return err
	return None
