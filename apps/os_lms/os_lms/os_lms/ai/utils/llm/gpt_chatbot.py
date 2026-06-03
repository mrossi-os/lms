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
        self._system_prompt = settings.system_prompt or DEFAULT_SYSTEM_PROMPT
        self._api_key = settings.openai_key

    def ask(
        self, question: str, contexts: list[str], lesson_context: dict | None = None
    ) -> str:
        if not self._api_key:
            frappe.throw("OPENAI_API_KEY not found")

        context_text = "\n\n---\n\n".join(contexts)

        system_prompt = self._system_prompt
        if lesson_context:
            system_prompt = f"{system_prompt}\n\n{self._build_context_prompt(lesson_context)}"

        user_prompt = f"""Materiale (dalla lezione corrente e dalle lezioni già completate):
{context_text}

Domanda: {question}

Rispondi alla domanda basandoti sul materiale qui sopra."""

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
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

    def _build_context_prompt(self, lesson_context: dict) -> str:
        """Build the dynamic part of the system prompt: course title, current
        lesson, the student's progress map and the anti-spoiler guidelines.

        The text is in Italian to stay coherent with the platform language."""
        return f"""Stai facendo da tutor allo studente nel corso "{lesson_context.get('course_title', '')}".
Lo studente è attualmente alla lezione {lesson_context.get('lesson_number', '')} — "{lesson_context.get('lesson_title', '')}".

Mappa del corso e progresso dello studente (✓ = completata, ▶ = lezione corrente, ○ = non ancora svolta):
{lesson_context.get('outline_text', '')}

Linee guida:
- Puoi usare e collegare i contenuti della lezione corrente e di qualsiasi lezione che lo studente ha già completato.
- NON rivelare né anticipare i contenuti delle lezioni che lo studente non ha ancora completato. Se lo studente te lo chiede, di' brevemente che saranno trattati più avanti nel corso.
- Basa la risposta sul materiale fornito. Se l'informazione non è presente, dillo chiaramente.
- Mantieni le risposte concise e pertinenti."""
