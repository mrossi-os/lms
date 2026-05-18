"""Whitelisted endpoints for the LLM layer (Desk-only diagnostics).

Currently exposes a single endpoint: `test_providers`, used by the LMSA
Settings form action "Test Connessione Provider" to verify which providers
are correctly configured.

Audience is restricted to System Manager / LMS Manager — these are the same
roles that can see LMSA Settings, and the response can leak provider names.
"""
from __future__ import annotations

import frappe
from frappe import _

from . import (
    LLMError,
    LLMInvalidAuth,
    ProviderConfig,
    _load_settings,
    build_provider_config,
    fallback_order,
    get_provider,
    list_providers,
)

ALLOWED_ROLES = {"System Manager", "LMS Manager"}


def _ensure_admin() -> None:
    roles = set(frappe.get_roles())
    if not (roles & ALLOWED_ROLES):
        frappe.throw(
            _("Only System Manager and LMS Manager can run provider diagnostics"),
            frappe.PermissionError,
        )


@frappe.whitelist()
def test_providers() -> dict:
    """Return a per-provider report: configured/ok/error.

    For each registered adapter, build its config from LMSA Settings and:
    - skip with "not_configured" if the API key is missing,
    - call health_check() and surface the boolean as "ok",
    - return the error message string when health_check raises.

    The Mock provider is always "ok" — it requires no key.
    """
    _ensure_admin()

    settings = _load_settings()
    results: list[dict] = []
    for name in list_providers():
        try:
            config = build_provider_config(name, settings)
        except ValueError as e:
            results.append({"provider": name, "status": "error", "detail": str(e)})
            continue

        if name != "mock" and not config.api_key:
            results.append(
                {
                    "provider": name,
                    "status": "not_configured",
                    "detail": _("API key missing in LMSA Settings"),
                }
            )
            continue

        try:
            provider = get_provider(config)
            ok = provider.health_check()
            results.append(
                {
                    "provider": name,
                    "status": "ok" if ok else "error",
                    "detail": "" if ok else _("health_check returned False"),
                }
            )
        except LLMInvalidAuth as e:
            results.append({"provider": name, "status": "invalid_auth", "detail": str(e)})
        except LLMError as e:
            results.append({"provider": name, "status": "error", "detail": str(e)})
        except Exception as e:  # safety net
            results.append({"provider": name, "status": "error", "detail": repr(e)})

    return {
        "results": results,
        "fallback_order": fallback_order(settings),
        "default_provider": settings.simulation_provider_default,
        "chat_provider": settings.simulation_chat_provider,
        "debrief_provider": settings.simulation_debrief_provider,
    }
