"""Public surface of the audio (STT / TTS) layer.

Business code imports from os_lms.os_lms.ai.utils.audio and never reaches into
adapter modules. resolve_audio_provider() reads the shared OsLmsSettings (same
loader as the LLM layer) and returns a configured AudioProvider for a given
capability ("stt" / "tts").

OpenAI and Gemini are wired. DeepSeek and Anthropic have no audio API, so they
are intentionally absent from the registry.
"""
from __future__ import annotations

from typing import Literal

from .config import AudioProviderConfig
from .errors import (
    AudioError,
    AudioInvalidAuth,
    AudioInvalidInput,
    AudioRateLimit,
    AudioServerError,
    AudioTimeout,
    AudioUnsupported,
)
from .provider import AudioProvider, SpeechResult, TranscriptionResult
from .registry import get_audio_provider, list_audio_providers, register_audio

# Side-effect: register all built-in adapters.
from . import providers as _providers  # noqa: F401

Capability = Literal["stt", "tts"]


__all__ = [
    "AudioError",
    "AudioInvalidAuth",
    "AudioInvalidInput",
    "AudioProvider",
    "AudioProviderConfig",
    "AudioRateLimit",
    "AudioServerError",
    "AudioTimeout",
    "AudioUnsupported",
    "Capability",
    "SpeechResult",
    "TranscriptionResult",
    "build_audio_config",
    "get_audio_provider",
    "list_audio_providers",
    "register_audio",
    "resolve_audio_provider",
]


def resolve_audio_provider(
    capability: Capability,
    *,
    override: str | None = None,
) -> AudioProvider:
    """Return a configured AudioProvider for the given capability.

    The provider is chosen from stt_provider / tts_provider (default "openai");
    `override` takes precedence.
    """
    settings = _load_settings()
    name = override or _pick_provider_name(settings, capability)
    config = build_audio_config(name, settings)
    return get_audio_provider(config)


def build_audio_config(name: str, settings) -> AudioProviderConfig:
    """Map (provider name, OsLmsSettings) to an AudioProviderConfig.

    Single place to wire a new audio provider. Audio reuses the OpenAI key /
    base URL already configured for the chat layer.
    """
    if name == "mock":
        return AudioProviderConfig(name="mock", stt_model="mock-stt", tts_model="mock-tts")

    if name == "openai":
        return AudioProviderConfig(
            name="openai",
            api_key=settings.openai_key or "",
            stt_model=settings.stt_model or "gpt-4o-mini-transcribe",
            tts_model=settings.tts_model or "gpt-4o-mini-tts",
            tts_voice=settings.tts_voice or "alloy",
            base_url=settings.openai_base_url or None,
        )

    if name == "gemini":
        # Gemini speaks its own native endpoint (the OpenAI base URL override
        # does not apply). The shared stt_model / tts_model / tts_voice settings
        # are passed through as-is; the adapter sanitizes any value left over
        # from another provider (see GeminiAudioProvider._gemini_model_or / _voice).
        return AudioProviderConfig(
            name="gemini",
            api_key=settings.gemini_key or "",
            stt_model=settings.stt_model or "",
            tts_model=settings.tts_model or "",
            tts_voice=settings.tts_voice or "",
        )

    raise ValueError(f"No audio provider config wiring for {name!r}")


def _load_settings():
    """Reuse the LLM layer's settings loader (single OsLmsSettings source)."""
    from os_lms.os_lms.ai.utils.llm import load_settings

    return load_settings()


def _pick_provider_name(settings, capability: Capability) -> str:
    selected = settings.stt_provider if capability == "stt" else settings.tts_provider
    return selected or "openai"
