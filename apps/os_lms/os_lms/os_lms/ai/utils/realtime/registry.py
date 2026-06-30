"""Realtime provider registry: decorator-based registration + factory.

Parallel to ai/utils/audio/registry. Adapters in providers/ decorate their
class with @register_realtime("name"); business code uses
get_realtime_provider(config) and never imports adapter classes.
"""
from __future__ import annotations

from .config import RealtimeProviderConfig
from .provider import RealtimeProvider

_REALTIME_PROVIDERS: dict[str, type[RealtimeProvider]] = {}


def register_realtime(name: str):
	"""Class decorator that registers a realtime adapter under a stable key."""

	def deco(cls: type[RealtimeProvider]) -> type[RealtimeProvider]:
		if not issubclass(cls, RealtimeProvider):
			raise TypeError(f"{cls.__name__} must subclass RealtimeProvider")
		_REALTIME_PROVIDERS[name] = cls
		cls.name = name
		return cls

	return deco


def get_realtime_provider(config: RealtimeProviderConfig) -> RealtimeProvider:
	if config.name not in _REALTIME_PROVIDERS:
		available = ", ".join(sorted(_REALTIME_PROVIDERS)) or "<none registered>"
		raise ValueError(
			f"Unknown realtime provider: {config.name!r}. Available: {available}"
		)
	return _REALTIME_PROVIDERS[config.name](config)


def list_realtime_providers() -> list[str]:
	return sorted(_REALTIME_PROVIDERS)


def _reset_for_tests() -> None:
	"""Internal helper: clear the registry. Use only in tests."""
	_REALTIME_PROVIDERS.clear()
