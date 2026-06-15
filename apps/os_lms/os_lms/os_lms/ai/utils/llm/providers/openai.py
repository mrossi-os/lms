"""OpenAI adapter.

Thin wrapper over OpenAICompatibleProvider with OpenAI's base URL. If the
openai SDK is ever introduced for advanced features (file API, batch, etc.),
the import must live in this module only — see encapsulation rule.
"""
from __future__ import annotations

from ..registry import register
from .openai_compatible import OpenAICompatibleProvider


@register("openai")
class OpenAIProvider(OpenAICompatibleProvider):
    DEFAULT_BASE_URL = "https://api.openai.com/v1"
