"""Provider-agnostic realtime (speech-to-speech) abstraction.

Mirrors ai/utils/audio: business code consumes RealtimeProvider through this
module and never reaches into adapter modules. Concrete adapters live in
providers/ and encapsulate any HTTP detail (SDK-free, via `requests`).

The abstraction is a CONTROL-PLANE contract only: create_session mints an
ephemeral token; the audio stream itself is established client-side and never
touches the backend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .errors import RealtimeUnsupported


@dataclass
class RealtimeSession:
	"""What the client needs to open a direct realtime connection.

	`transport` tells the client which strategy to use ("webrtc" | "websocket"
	| "mock"). `client_secret` is the ephemeral token (NEVER the api key).
	`extra` carries opaque provider-specific fields (e.g. Gemini resumption).
	"""

	provider: str
	model: str
	transport: str
	client_secret: str
	connect_url: str
	expires_at: int
	voice: str
	extra: dict = field(default_factory=dict)


@dataclass
class RealtimeSessionConfig:
	"""Built by the feature layer from the Scenario persona + settings."""

	instructions: str
	voice: str
	model: str
	turn_detection: str = "server_vad"
	input_language: str = "it"
	max_session_seconds: int = 300
	session_label: str = ""


@dataclass
class TranscriptEvent:
	"""Normalized transcript output for persistence as a Turn."""

	role: str  # "user" | "assistant"
	text: str
	final: bool


class RealtimeProvider(ABC):
	"""Abstract base for a realtime provider adapter."""

	name: str = ""

	@abstractmethod
	def create_session(self, cfg: RealtimeSessionConfig) -> RealtimeSession:
		"""Mint an ephemeral client token server-side and return everything
		the client needs to connect. The api key stays on the server."""
		raise RealtimeUnsupported(f"{self.name or 'provider'} does not support realtime sessions")

	@abstractmethod
	def parse_transcript_event(self, event: dict) -> TranscriptEvent | None:
		"""Normalize a provider event into a TranscriptEvent, or None if the
		event is not a final transcript (deltas, control frames, etc.)."""

	def health_check(self) -> bool:
		"""Lightweight check used to validate configuration."""
		return False
