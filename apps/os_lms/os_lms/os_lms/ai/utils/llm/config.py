"""Configuration object passed to LLMProvider adapters.

Adapters never read frappe.get_single("LMSA Settings") directly. They only
see a ProviderConfig built by build_provider_config() (in __init__.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider adapter instance.

    The `name` field is the registry key (e.g. "openai", "gemini", "deepseek",
    "anthropic", "mock"). The factory get_provider() uses it to look up the
    adapter class.
    """

    name: str
    api_key: str = ""
    default_model: str = ""
    base_url: str | None = None
    organization: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    timeout: float = 60.0
