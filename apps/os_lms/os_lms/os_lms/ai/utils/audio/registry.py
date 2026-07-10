"""Audio provider registry: decorator-based registration + factory.

Parallel to ai/utils/llm/registry. Concrete adapters in providers/ decorate
their class with @register_audio("name"); business code uses
get_audio_provider(config) and never imports adapter classes.
"""
from __future__ import annotations

from .config import AudioProviderConfig
from .provider import AudioProvider

_AUDIO_PROVIDERS: dict[str, type[AudioProvider]] = {}


def register_audio(name: str):
    """Class decorator that registers an audio adapter under a stable key."""

    def deco(cls: type[AudioProvider]) -> type[AudioProvider]:
        if not issubclass(cls, AudioProvider):
            raise TypeError(f"{cls.__name__} must subclass AudioProvider")
        _AUDIO_PROVIDERS[name] = cls
        cls.name = name
        return cls

    return deco


def get_audio_provider(config: AudioProviderConfig) -> AudioProvider:
    if config.name not in _AUDIO_PROVIDERS:
        available = ", ".join(sorted(_AUDIO_PROVIDERS)) or "<none registered>"
        raise ValueError(
            f"Unknown audio provider: {config.name!r}. Available: {available}"
        )
    return _AUDIO_PROVIDERS[config.name](config)


def list_audio_providers() -> list[str]:
    return sorted(_AUDIO_PROVIDERS)


def _reset_for_tests() -> None:
    """Internal helper: clear the registry. Use only in tests."""
    _AUDIO_PROVIDERS.clear()
