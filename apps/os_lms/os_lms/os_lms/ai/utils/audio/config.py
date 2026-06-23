"""Configuration object passed to AudioProvider adapters.

Adapters never read frappe settings directly — they only see an
AudioProviderConfig built by build_audio_config() (in __init__.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AudioProviderConfig:
    """Configuration for a single audio provider adapter instance.

    The `name` field is the registry key (e.g. "openai", "mock"). The factory
    get_audio_provider() uses it to look up the adapter class.
    """

    name: str
    api_key: str = ""
    stt_model: str = ""
    tts_model: str = ""
    tts_voice: str = "alloy"
    base_url: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    timeout: float = 60.0
