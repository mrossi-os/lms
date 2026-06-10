"""Backward-compatible wrapper for the RAG tutor chatbot.

`Chatbot.ask(question, contexts)` used to issue a raw HTTP call to OpenAI.
It now delegates to OpenAIProvider via the unified LLMProvider layer, so the
RAG tutor benefits from the same retry/error normalization as the simulation
feature without changing any of its call sites (IngestionService).
"""
from __future__ import annotations

from os_lms.os_lms.ai.utils.oslms_settings import OsLmsSettings

from . import ChatMessage, ProviderConfig, get_provider
from .chatbot import Chatbot

DEFAULT_SYSTEM_PROMPT = """You are a helpful teaching assistant for an online learning platform.
Answer the student's question based on the provided lesson content.
If the answer cannot be found in the provided content, say so clearly.
Keep your answers concise and relevant to the question."""


class GptChatbot(Chatbot):
    """RAG tutor implementation backed by the unified OpenAIProvider."""

    _system_prompt: str = DEFAULT_SYSTEM_PROMPT
    _api_key: str = ""
    _model: str = "gpt-4o-mini"

    def set_settings(self, settings: OsLmsSettings) -> None:
        self._api_key = settings.openai_key or ""
        self._model = settings.llm_model or "gpt-4o-mini"

    def ask(
        self, question: str, contexts: list[str], lesson_context: dict | None = None
    ) -> str:
        if not self._api_key:
            import frappe

            frappe.throw("OPENAI_API_KEY not configured in LMSA Settings")

        context_text = "\n\n---\n\n".join(contexts)
        user_prompt = (
            f"Lesson Content:\n{context_text}\n\n"
            f"Question: {question}\n\n"
            "Please answer the question based on the lesson content above."
        )

        provider = get_provider(
            ProviderConfig(name="openai", api_key=self._api_key, default_model=self._model)
        )
        response = provider.chat(
            messages=[ChatMessage(role="user", content=user_prompt)],
            system=self._system_prompt,
            temperature=0.7,
            max_tokens=1000,
        )
        return response.text
