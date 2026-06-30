"""Side-effect registration of built-in realtime adapters.

Importing this package registers every adapter via the @register_realtime
decorator. ai/utils/realtime/__init__.py imports it once.
"""
from __future__ import annotations

from . import mock  # noqa: F401
from . import openai_realtime  # noqa: F401
from . import gemini_live  # noqa: F401
