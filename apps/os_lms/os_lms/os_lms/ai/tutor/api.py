import json

import frappe

from os_lms.os_lms.ai.audio.pipeline import run_audio_turn
from os_lms.os_lms.ai.tutor.tutor_ai import TutorAi


@frappe.whitelist()
def ask(
	course: str,
	lesson: str,
	question: str,
	history: list[dict] | None = None,
) -> dict:
	"""Answer a learner's question about a course or lesson."""
	# Frappe forwards complex args as JSON strings when the client posts
	# form-encoded data; normalize before use.
	if isinstance(history, str):
		history = json.loads(history)

	tutor = TutorAi(course=course, lesson=lesson or None, user=frappe.session.user)
	answer = tutor.ask(question, history or [])
	return {"answer": answer}


@frappe.whitelist()
def ask_audio(
	course: str,
	lesson: str = "",
	question: str | None = None,
	audio: str | None = None,
	mime: str = "audio/webm",
	language: str = "it",
	history: list[dict] | None = None,
	want_audio: bool = True,
) -> dict:
	"""Single-call audio (or text) tutor turn: STT? -> TutorAi.ask -> TTS?.

	Returns {question_text, answer_text, audio_base64, mime}.
	"""
	if isinstance(history, str):
		history = json.loads(history)
	user = frappe.session.user

	def _produce(q: str) -> str:
		return TutorAi(course=course, lesson=lesson or None, user=user).ask(q, history or [])

	return run_audio_turn(
		audio=audio,
		text=question,
		mime=mime,
		language=language,
		produce_answer=_produce,
		want_audio=want_audio,
	)
