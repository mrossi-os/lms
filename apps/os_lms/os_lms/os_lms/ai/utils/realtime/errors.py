"""Normalized errors raised by realtime adapters.

Parallel to ai/utils/audio/errors: adapters translate provider-specific
failures into these classes so the whitelisted API layer reacts uniformly.
"""

from __future__ import annotations


class RealtimeError(Exception):
	"""Base class for any error raised by a RealtimeProvider adapter."""

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


class RealtimeUnsupported(RealtimeError):
	"""The provider does not support realtime session minting."""


class RealtimeInvalidAuth(RealtimeError):
	"""API key missing or invalid (mis-config)."""


class RealtimeRateLimit(RealtimeError):
	"""429 / quota exhausted."""


class RealtimeServerError(RealtimeError):
	"""5xx from the provider, or a transport-level failure."""


class RealtimeTimeout(RealtimeError):
	"""Request timed out."""


class RealtimeInvalidInput(RealtimeError):
	"""Input rejected before contacting the provider."""
