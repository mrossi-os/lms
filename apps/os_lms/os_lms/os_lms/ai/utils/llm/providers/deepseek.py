"""DeepSeek adapter.

DeepSeek's API is 100% OpenAI Chat Completions compatible, so we just
override the base URL.
"""
from __future__ import annotations

from ..registry import register
from .openai_compatible import OpenAICompatibleProvider


@register("deepseek")
class DeepSeekProvider(OpenAICompatibleProvider):
    DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
