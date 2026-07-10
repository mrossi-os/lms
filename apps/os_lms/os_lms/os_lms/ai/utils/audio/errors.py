"""Normalized errors raised by audio adapters.

Parallel to ai/utils/llm/errors: adapters translate provider-specific failures
into these classes so callers (and the whitelisted API layer) react uniformly.
"""
from __future__ import annotations


class AudioError(Exception):
    """Base class for any error raised by an AudioProvider adapter."""

    def __init__(
        self,
        message: str = "",
        *,
        provider: str | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.cause = cause


class AudioUnsupported(AudioError):
    """The requested capability (STT or TTS) is not supported by the provider."""


class AudioInvalidAuth(AudioError):
    """API key missing or invalid (mis-config)."""


class AudioRateLimit(AudioError):
    """429 / quota exhausted."""


class AudioServerError(AudioError):
    """5xx from the provider, or a transport-level failure."""


class AudioTimeout(AudioError):
    """Request timed out."""


class AudioInvalidInput(AudioError):
    """Input rejected before contacting the provider (empty / too large / bad format)."""
