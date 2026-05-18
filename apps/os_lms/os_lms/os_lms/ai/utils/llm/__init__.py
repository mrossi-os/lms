"""Public surface of the LLM layer.

Business code imports from os_lms.os_lms.ai.utils.llm and never reaches into
adapter modules. resolve_provider() reads LMSA Settings + OsLmsSettings and
returns a configured LLMProvider.
"""
from __future__ import annotations

from typing import Literal

from .config import ProviderConfig
from .errors import (
    LLMContextWindow,
    LLMError,
    LLMInvalidAuth,
    LLMRateLimit,
    LLMServerError,
    LLMTimeout,
    LLMUnsupported,
    ProviderSdkNotInstalled,
)
from .provider import (
    ChatChunk,
    ChatMessage,
    ChatResponse,
    FinishReason,
    JsonSchema,
    LLMProvider,
    Role,
    Usage,
)
from .registry import get_provider, list_providers, register

# Side-effect: register all built-in adapters.
from . import providers as _providers  # noqa: F401

Purpose = Literal["chat", "debrief"]


__all__ = [
    "ChatChunk",
    "ChatMessage",
    "ChatResponse",
    "FinishReason",
    "JsonSchema",
    "LLMContextWindow",
    "LLMError",
    "LLMInvalidAuth",
    "LLMProvider",
    "LLMRateLimit",
    "LLMServerError",
    "LLMTimeout",
    "LLMUnsupported",
    "ProviderConfig",
    "ProviderSdkNotInstalled",
    "Purpose",
    "Role",
    "Usage",
    "build_provider_config",
    "chat_with_fallback",
    "fallback_order",
    "get_provider",
    "list_providers",
    "register",
    "resolve_provider",
]


def resolve_provider(
    purpose: Purpose = "chat",
    *,
    override: str | None = None,
) -> LLMProvider:
    """Return a configured LLMProvider for the given purpose.

    Reads LMSA Settings + OsLmsSettings. The `override` argument (typically
    from a Scenario field) takes precedence over the global settings.
    """
    # Local import to avoid a hard dependency on frappe at module import time,
    # so the layer remains importable in pure unit tests with the mock provider.
    from os_lms.os_lms.ai.utils.oslms_settings import OsLmsSettings  # noqa: F401

    settings = _load_settings()
    name = override or _pick_provider_name(settings, purpose)
    config = build_provider_config(name, settings, purpose=purpose)
    return get_provider(config)


def build_provider_config(
    name: str,
    settings,
    *,
    purpose: Purpose = "chat",
) -> ProviderConfig:
    """Map (provider name, OsLmsSettings) to a ProviderConfig instance.

    Single place to add a new provider's wiring: API key, default model, base URL.
    """
    if name == "mock":
        return ProviderConfig(name="mock", default_model="mock-1")

    if name == "openai":
        model = _model_for(settings, purpose, fallback=settings.simulation_chat_model or "gpt-4.1")
        return ProviderConfig(
            name="openai",
            api_key=settings.openai_key or "",
            default_model=model,
            base_url=settings.openai_base_url or None,
        )

    if name == "deepseek":
        return ProviderConfig(
            name="deepseek",
            api_key=settings.deepseek_key or "",
            default_model=settings.simulation_chat_model or "deepseek-chat",
            base_url="https://api.deepseek.com/v1",
        )

    if name == "gemini":
        return ProviderConfig(
            name="gemini",
            api_key=settings.gemini_key or "",
            default_model=settings.simulation_chat_model or "gemini-2.5-pro",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        )

    if name == "anthropic":
        model_default = "claude-opus-4-7" if purpose == "debrief" else "claude-sonnet-4-5"
        return ProviderConfig(
            name="anthropic",
            api_key=settings.anthropic_key or "",
            default_model=settings.simulation_chat_model or model_default,
        )

    raise ValueError(f"No provider config wiring for {name!r}")


def _load_settings():
    """Load OsLmsSettings from the LMSA Settings doctype.

    Lazy import of frappe so unit tests can monkeypatch this function.
    Password-typed fields are read via get_decrypted_password.
    """
    import frappe
    from frappe.utils.password import get_decrypted_password

    from os_lms.os_lms.ai.utils.oslms_settings import OsLmsSettings

    doc = frappe.get_single("LMSA Settings")

    def _password(fieldname: str) -> str:
        if not getattr(doc, fieldname, None):
            return ""
        try:
            return (
                get_decrypted_password("LMSA Settings", "LMSA Settings", fieldname, raise_exception=False)
                or ""
            )
        except Exception:
            return ""

    return OsLmsSettings(
        # legacy fields (RAG tutor)
        enabled=getattr(doc, "enabled", False),
        embedding_model=getattr(doc, "embedding_model", "") or "text-embedding-3-small",
        chunk_size=getattr(doc, "chunk_size", 0) or 1000,
        chunk_overlap=getattr(doc, "chunk_overlap", 0) or 200,
        top_k=getattr(doc, "top_k", 0) or 6,
        llm_model=getattr(doc, "llm_model", "") or "gpt-4o-mini",
        system_prompt=getattr(doc, "system_prompt", "") or "",
        # openai_key remains a Data field for backward compatibility with the
        # legacy RAG tutor — see SET-1.1 note in PROGRESS.md.
        openai_key=getattr(doc, "openai_key", "") or "",
        # simulation-era fields (added in SET-1.1)
        simulations_enabled=bool(getattr(doc, "simulations_enabled", 0)),
        simulation_chat_provider=getattr(doc, "simulation_chat_provider", "") or "auto",
        simulation_debrief_provider=getattr(doc, "simulation_debrief_provider", "") or "auto",
        simulation_provider_default=getattr(doc, "simulation_provider_default", "") or "openai",
        simulation_provider_fallback_order=getattr(doc, "simulation_provider_fallback_order", "")
        or "openai,gemini,deepseek",
        simulation_chat_model=getattr(doc, "simulation_chat_model", "") or "",
        simulation_debrief_model=getattr(doc, "simulation_debrief_model", "") or "gpt-4.1",
        openai_base_url=getattr(doc, "openai_base_url", "") or "",
        gemini_key=_password("gemini_key"),
        deepseek_key=_password("deepseek_key"),
        anthropic_key=_password("anthropic_key"),
    )


def _pick_provider_name(settings, purpose: Purpose) -> str:
    selected = (
        settings.simulation_chat_provider
        if purpose == "chat"
        else settings.simulation_debrief_provider
    )
    if not selected or selected == "auto":
        return settings.simulation_provider_default or "openai"
    return selected


def _model_for(settings, purpose: Purpose, *, fallback: str) -> str:
    if purpose == "debrief":
        return settings.simulation_debrief_model or fallback
    return settings.simulation_chat_model or fallback


def fallback_order(settings) -> list[str]:
    """Parse CSV settings.simulation_provider_fallback_order into a clean list."""
    raw = settings.simulation_provider_fallback_order or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


def chat_with_fallback(
    purpose: Purpose,
    messages: list[ChatMessage],
    *,
    override: str | None = None,
    **chat_kwargs,
) -> ChatResponse:
    """Try the configured provider; on rate-limit / server-error, fall back
    through `simulation_provider_fallback_order` IF the corresponding setting
    is "auto". Explicit provider pinning (e.g. simulation_chat_provider="openai"
    or a Scenario override) disables fallback — the call site is asking for a
    specific provider on purpose and should see the error.

    Streaming responses do not use fallback in this MVP: by the time we know
    the upstream is failing, the stream may have already yielded partial data.
    Callers that want streaming + fallback should orchestrate that themselves.

    Raises the last LLMError if every candidate failed. Raises non-fallback
    errors (LLMInvalidAuth, LLMContextWindow, ...) immediately on the first
    occurrence — no point trying other providers for a mis-config.
    """
    if chat_kwargs.get("stream"):
        raise LLMUnsupported(
            "chat_with_fallback does not support streaming; use resolve_provider().chat(...) directly."
        )

    settings = _load_settings()
    setting_value = (
        settings.simulation_chat_provider
        if purpose == "chat"
        else settings.simulation_debrief_provider
    )
    primary_name = override or _pick_provider_name(settings, purpose)
    fallback_enabled = (override is None) and (setting_value == "auto")

    candidates: list[str] = [primary_name]
    if fallback_enabled:
        for name in fallback_order(settings):
            if name and name not in candidates:
                candidates.append(name)

    last_error: LLMError | None = None
    for name in candidates:
        try:
            config = build_provider_config(name, settings, purpose=purpose)
            provider = get_provider(config)
            return provider.chat(messages=messages, **chat_kwargs)
        except (LLMRateLimit, LLMServerError) as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    raise LLMError("No LLM provider available")
