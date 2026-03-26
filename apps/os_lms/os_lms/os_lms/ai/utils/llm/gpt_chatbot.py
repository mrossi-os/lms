import os

import frappe
import requests

from .chatbot import Chatbot
from os_lms.os_lms.ai.utils.oslms_settings import OsLmsSettings

DEFAULT_SYSTEM_PROMPT = """You are a helpful teaching assistant for an online learning platform.
Answer the student's question based on the provided lesson content.
If the answer cannot be found in the provided content, say so clearly.
Keep your answers concise and relevant to the question."""


class GptChatbot(Chatbot):

    _model: str = "gpt-4o-mini"
    _system_prompt: str = DEFAULT_SYSTEM_PROMPT
    _api_key: str = None

    def set_settings(self, settings: OsLmsSettings):
        self._system_prompt = settings.system_prompt
        self._api_key = settings.openai_key

    def ask(self, question: str, contexts: list[str]) -> str:
        if not self._api_key:
            frappe.throw("OPENAI_API_KEY not found")

        context_text = "\n\n---\n\n".join(contexts)

        user_prompt = f"""Lesson Content:
{context_text}

Question: {question}

Please answer the question based on the lesson content above."""

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": 1000,
                "temperature": 0.7,
            },
            timeout=60,
        )

        if response.status_code != 200:
            frappe.throw(f"OpenAI API error: {response.text}")

        data = response.json()
        return data["choices"][0]["message"]["content"]
