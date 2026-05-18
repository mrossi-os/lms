"""Concrete LLMProvider adapters.

Importing this package triggers registration of all built-in adapters
via the @register decorator at module load time.

Encapsulation rule: each provider's official SDK is allowed only inside its
own adapter module — never re-exported here. See test_provider_encapsulation.py.
"""
from . import (  # noqa: F401 — side-effect registration
    anthropic,
    deepseek,
    gemini,
    mock,
    openai,
)
