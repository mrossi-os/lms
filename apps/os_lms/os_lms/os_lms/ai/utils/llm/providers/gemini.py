"""Google Gemini adapter (OpenAI-compatible endpoint).

Per decision #2 in PROGRESS.md, we use Google's OpenAI-compat endpoint so
this adapter is a single-line override of base_url. If we ever need
grounding, file API, or other Gemini-specific features, replace this with a
native REST adapter — the import of google-genai SDK would then live in this
module exclusively (encapsulation rule).
"""
from __future__ import annotations

from ..registry import register
from .openai_compatible import OpenAICompatibleProvider


@register("gemini")
class GeminiProvider(OpenAICompatibleProvider):
    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
