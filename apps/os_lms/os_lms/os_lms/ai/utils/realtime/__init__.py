"""Public surface of the realtime (speech-to-speech) layer.

Business code imports from os_lms.os_lms.ai.utils.realtime and never reaches
into adapter modules. resolve_realtime_provider() reads the shared
OsLmsSettings (same loader as the LLM/audio layers) and returns a configured
RealtimeProvider; build_realtime_config() is the single wiring point.
"""

from __future__ import annotations

# Side-effect: register all built-in adapters.
from . import providers as _providers  # noqa: F401
from .config import RealtimeProviderConfig
from .errors import (
	RealtimeError,
	RealtimeInvalidAuth,
	RealtimeInvalidInput,
	RealtimeRateLimit,
	RealtimeServerError,
	RealtimeTimeout,
	RealtimeUnsupported,
)
from .provider import (
	RealtimeProvider,
	RealtimeSession,
	RealtimeSessionConfig,
	TranscriptEvent,
)
from .registry import (
	get_realtime_provider,
	list_realtime_providers,
	register_realtime,
)

__all__ = [
	"RealtimeError",
	"RealtimeInvalidAuth",
	"RealtimeInvalidInput",
	"RealtimeProvider",
	"RealtimeProviderConfig",
	"RealtimeRateLimit",
	"RealtimeServerError",
	"RealtimeSession",
	"RealtimeSessionConfig",
	"RealtimeTimeout",
	"RealtimeUnsupported",
	"TranscriptEvent",
	"build_realtime_config",
	"get_realtime_provider",
	"list_realtime_providers",
	"register_realtime",
	"resolve_realtime_provider",
]

# Sensible defaults if a settings field is blank.
_DEFAULT_MODEL = {"openai": "gpt-realtime-2", "gemini": "gemini-live-2.5-flash-native-audio"}
_DEFAULT_VOICE = {"openai": "marin", "gemini": "Puck"}


def resolve_realtime_provider(*, override: str | None = None) -> RealtimeProvider:
	"""Return a configured RealtimeProvider.

	The provider is chosen from settings.realtime_provider (default "openai");
	`override` (e.g. a Scenario field) takes precedence.
	"""
	settings = _load_settings()
	name = override or settings.realtime_provider or "openai"
	config = build_realtime_config(name, settings)
	return get_realtime_provider(config)


def build_realtime_config(name: str, settings) -> RealtimeProviderConfig:
	"""Map (provider name, OsLmsSettings) to a RealtimeProviderConfig.

	Single place to wire a new realtime provider. Reuses the per-provider keys
	already configured for the chat layer.
	"""
	max_seconds = getattr(settings, "realtime_max_session_seconds", 0) or 300
	turn_detection = getattr(settings, "turn_detection", "") or "server_vad"

	if name == "mock":
		return RealtimeProviderConfig(name="mock", default_model="mock-realtime")

	if name == "openai":
		return RealtimeProviderConfig(
			name="openai",
			api_key=getattr(settings, "openai_key", "") or "",
			default_model=getattr(settings, "realtime_model", "") or _DEFAULT_MODEL["openai"],
			voice=getattr(settings, "realtime_voice", "") or _DEFAULT_VOICE["openai"],
			turn_detection=turn_detection,
			max_session_seconds=max_seconds,
			base_url=getattr(settings, "openai_base_url", "") or None,
		)

	if name == "gemini":
		return RealtimeProviderConfig(
			name="gemini",
			api_key=getattr(settings, "gemini_key", "") or "",
			default_model=getattr(settings, "realtime_model", "") or _DEFAULT_MODEL["gemini"],
			voice=getattr(settings, "realtime_voice", "") or _DEFAULT_VOICE["gemini"],
			turn_detection=turn_detection,
			max_session_seconds=max_seconds,
		)

	raise ValueError(f"No realtime provider config wiring for {name!r}")


def _load_settings():
	"""Reuse the LLM layer's settings loader (single OsLmsSettings source)."""
	from os_lms.os_lms.ai.utils.llm import load_settings

	return load_settings()
