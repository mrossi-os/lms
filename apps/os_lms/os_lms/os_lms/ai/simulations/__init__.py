"""AI Simulations sub-module of os_lms.

Public surface:
- SessionOrchestrator: drives a session lifecycle (start → turn → end).
- prompts: pure-function builders for scenario generation, role-play, defense.

Business code outside this package should depend only on names re-exported
here, not on submodule layout.
"""
from .orchestrator import (
    QuotaExceededError,
    SessionOrchestrator,
    SessionTerminatedError,
)

__all__ = ["QuotaExceededError", "SessionOrchestrator", "SessionTerminatedError"]
