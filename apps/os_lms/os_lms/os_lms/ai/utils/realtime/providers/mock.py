"""Deterministic mock realtime provider for tests and local development.

No network, no keys. Lets the feature layer and frontend be exercised with
realtime_provider = "mock".
"""

from __future__ import annotations

from ..config import RealtimeProviderConfig
from ..provider import (
	RealtimeProvider,
	RealtimeSession,
	RealtimeSessionConfig,
	TranscriptEvent,
)
from ..registry import register_realtime


@register_realtime("mock")
class MockRealtimeProvider(RealtimeProvider):
	"""Deterministic adapter: fixed ephemeral token + passthrough events."""

	def __init__(self, config: RealtimeProviderConfig):
		self._config = config

	def create_session(self, cfg: RealtimeSessionConfig) -> RealtimeSession:
		return RealtimeSession(
			provider=self.name,
			model=cfg.model or self._config.default_model or "mock-realtime",
			transport="mock",
			client_secret=f"mock-secret-{cfg.session_label or 'x'}",
			connect_url="mock://realtime",
			expires_at=0,
			voice=cfg.voice or self._config.voice or "marin",
			extra={"instructions": cfg.instructions},
		)

	def parse_transcript_event(self, event: dict) -> TranscriptEvent | None:
		if not event.get("final"):
			return None
		role = event.get("role")
		if role not in ("user", "assistant"):
			return None
		return TranscriptEvent(role=role, text=event.get("text", "") or "", final=True)

	def health_check(self) -> bool:
		return True
