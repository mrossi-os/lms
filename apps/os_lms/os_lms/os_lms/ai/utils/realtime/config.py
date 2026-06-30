"""Configuration object passed to RealtimeProvider adapters.

Adapters never read frappe settings directly — they only see a
RealtimeProviderConfig built by build_realtime_config() (in __init__.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RealtimeProviderConfig:
	"""Configuration for a single realtime provider adapter instance.

	`name` is the registry key (e.g. "openai", "gemini", "mock").
	"""

	name: str
	api_key: str = ""
	default_model: str = ""
	voice: str = ""
	turn_detection: str = "server_vad"
	input_language: str = "it"
	max_session_seconds: int = 300
	base_url: str | None = None
	extra: dict = field(default_factory=dict)
