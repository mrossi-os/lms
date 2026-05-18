"""Provider registry: decorator-based registration + factory.

Concrete adapters in providers/ decorate their class with @register("name").
Business code uses get_provider(config) and never imports adapter classes.
"""
from __future__ import annotations

from .config import ProviderConfig
from .provider import LLMProvider

_PROVIDERS: dict[str, type[LLMProvider]] = {}


def register(name: str):
    """Class decorator that registers an adapter under a stable key."""

    def deco(cls: type[LLMProvider]) -> type[LLMProvider]:
        if not issubclass(cls, LLMProvider):
            raise TypeError(f"{cls.__name__} must subclass LLMProvider")
        _PROVIDERS[name] = cls
        cls.name = name
        return cls

    return deco


def get_provider(config: ProviderConfig) -> LLMProvider:
    if config.name not in _PROVIDERS:
        available = ", ".join(sorted(_PROVIDERS)) or "<none registered>"
        raise ValueError(
            f"Unknown LLM provider: {config.name!r}. Available: {available}"
        )
    return _PROVIDERS[config.name](config)


def list_providers() -> list[str]:
    return sorted(_PROVIDERS)


def _reset_for_tests() -> None:
    """Internal helper: clear the registry. Use only in tests."""
    _PROVIDERS.clear()
