"""Concrete LLMProvider adapters.

Importing this package triggers registration of all built-in adapters
via the @register decorator at module load time.

The official SDK of each provider is allowed only inside its own adapter
module — never re-exported from here. See test_provider_encapsulation.py.
"""
from . import mock  # noqa: F401 — side-effect registration
