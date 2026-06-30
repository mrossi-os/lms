"""Gemini Live adapter (control plane only).

Mints an ephemeral auth token (v1alpha) via `requests` and returns a WebSocket
transport descriptor. The persona (`system_instruction`) is fixed at connect,
so it is handed to the client in `extra` to include in its
BidiGenerateContentSetup. Session resumption is the client's responsibility;
the `resumption_handle` slot is provided so the client can persist/restore it.

SDK-free, same encapsulation rule as the audio adapters.
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

_BASE = "https://generativelanguage.googleapis.com/v1alpha"
_WS_URL = (
	"wss://generativelanguage.googleapis.com/ws/"
	"google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"
)


@register_realtime("gemini")
class GeminiLiveProvider(RealtimeProvider):
	"""Gemini Live over WebSocket; ephemeral token minted over REST."""

	DEFAULT_MODEL = "gemini-live-2.5-flash-native-audio"

	def __init__(self, config: RealtimeProviderConfig):
		self._config = config

	def create_session(self, cfg: RealtimeSessionConfig) -> RealtimeSession:
		if not self._config.api_key:
			raise RealtimeInvalidAuth("Gemini api key is not configured", provider=self.name)
		url = f"{_BASE}/auth_tokens?key={self._config.api_key}"
		try:
			r = requests.post(
				url,
				headers={"Content-Type": "application/json"},
				json=_token_request(cfg, self._config),
				timeout=30.0,
			)
		except requests.Timeout as e:
			raise RealtimeTimeout(str(e), provider=self.name, cause=e) from e
		except requests.RequestException as e:
			raise RealtimeServerError(str(e), provider=self.name, cause=e) from e

		self._check_status(r)
		payload = r.json()
		token = payload.get("name", "") or payload.get("token", "")
		model = cfg.model or self._config.default_model or self.DEFAULT_MODEL
		return RealtimeSession(
			provider=self.name,
			model=model,
			transport="websocket",
			client_secret=token,
			connect_url=_WS_URL,
			expires_at=0,  # Gemini returns RFC3339 expireTime; the client tracks it.
			voice=cfg.voice or self._config.voice or "Puck",
			extra={
				"model": model,
				"instructions": cfg.instructions,
				"voice": cfg.voice or self._config.voice or "Puck",
				"input_language": cfg.input_language,
				"resumption_handle": "",
				"expire_time": payload.get("expireTime", ""),
			},
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


def _token_request(cfg: RealtimeSessionConfig, config: RealtimeProviderConfig) -> dict:
	"""Build the ephemeral-token request. Keep all provider-format coupling here."""
	return {
		"uses": 1,
		"liveConnectConstraints": {
			"model": cfg.model or config.default_model or GeminiLiveProvider.DEFAULT_MODEL,
		},
	}


def _parse_event(event: dict) -> TranscriptEvent | None:
	content = event.get("serverContent") or {}
	itx = content.get("inputTranscription") or {}
	if itx.get("text"):
		return TranscriptEvent(role="user", text=itx["text"], final=True)
	otx = content.get("outputTranscription") or {}
	if otx.get("text"):
		return TranscriptEvent(role="assistant", text=otx["text"], final=True)
	return None


def _extract_error(r: requests.Response) -> str | None:
	try:
		data = r.json()
	except ValueError:
		return (r.text or "")[:200] or None
	if isinstance(data, dict):
		err = data.get("error")
		if isinstance(err, dict):
			return err.get("message") or err.get("status")
	return None
