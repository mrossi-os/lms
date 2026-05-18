"""Normalized errors raised by LLM adapters.

Adapters translate provider-specific exceptions into these classes so that
business code can react uniformly (e.g. fallback chain).
"""
from __future__ import annotations


class LLMError(Exception):
    """Base class for any error raised by an LLMProvider adapter."""

    def __init__(self, message: str = "", *, provider: str | None = None, cause: Exception | None = None):
        super().__init__(message)
        self.provider = provider
        self.cause = cause


class LLMRateLimit(LLMError):
    """429 / quota exhausted. Eligible for fallback or retry-after."""


class LLMServerError(LLMError):
    """5xx from the provider. Eligible for fallback."""


class LLMInvalidAuth(LLMError):
    """API key missing or invalid. NOT eligible for fallback (mis-config)."""


class LLMContextWindow(LLMError):
    """Request exceeds the model context window."""


class LLMTimeout(LLMError):
    """Request timed out."""


class LLMUnsupported(LLMError):
    """Feature not supported by the provider (e.g. structured output, streaming)."""


class ProviderSdkNotInstalled(LLMError):
    """The provider's optional SDK is not installed.

    Adapters that use an official SDK should catch the ImportError and raise
    this with a message that tells the user how to install it.
    """
