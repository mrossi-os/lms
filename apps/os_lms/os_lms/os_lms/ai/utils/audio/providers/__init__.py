"""Concrete AudioProvider adapters.

Importing this package triggers registration of all built-in adapters via the
@register_audio decorator at module load time.

Encapsulation rule: a provider's official SDK (if ever introduced) is allowed
only inside its own adapter module — never re-exported here.
"""
from . import (  # noqa: F401 — side-effect registration
    gemini,
    mock,
    openai,
)
