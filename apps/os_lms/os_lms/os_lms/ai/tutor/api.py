import json

import frappe
from frappe import _

from os_lms.os_lms.access_guards import (
	assert_course_readable,
	assert_lesson_readable,
	per_user_rate_limit,
)
from os_lms.os_lms.ai.audio.pipeline import run_audio_turn
from os_lms.os_lms.ai.tutor.tutor_ai import TutorAi

# Every question is a paid LLM call carrying the course's lessons in its prompt.
TUTOR_CALLS_PER_HOUR = 60
MAX_QUESTION_CHARS = 4000
# The history comes from the client: keep it to a conversation's worth, so a
# request cannot carry an arbitrarily long (and costly) prompt.
MAX_HISTORY_TURNS = 20
MAX_HISTORY_TURN_CHARS = 4000


def _authorize(course: str, lesson: str | None) -> None:
	"""Only who may read the course, and the lesson as it stands for them now: the
	tutor puts the lesson's text in its prompt and can be asked to repeat it."""
	if lesson:
		assert_lesson_readable(lesson, course)
	else:
		assert_course_readable(course)


def _clean_history(history) -> list[dict]:
	# Frappe forwards complex args as JSON strings when the client posts
	# form-encoded data; normalize before use.
	if isinstance(history, str):
		history = json.loads(history)
	if not isinstance(history, list):
		return []
	turns = [turn for turn in history if isinstance(turn, dict)][-MAX_HISTORY_TURNS:]
	return [
		{"from": turn.get("from"), "message": str(turn.get("message") or "")[:MAX_HISTORY_TURN_CHARS]}
		for turn in turns
	]


def _check_question(question: str | None) -> None:
	if question and len(question) > MAX_QUESTION_CHARS:
		frappe.throw(_("The question is too long."))


@frappe.whitelist(methods=["POST"])
@per_user_rate_limit(limit=TUTOR_CALLS_PER_HOUR, seconds=60 * 60)
def ask(
	course: str,
	lesson: str,
	question: str,
	history: list[dict] | None = None,
) -> dict:
	"""Answer a learner's question about a course or lesson."""
	_authorize(course, lesson or None)
	_check_question(question)
	tutor = TutorAi(course=course, lesson=lesson or None, user=frappe.session.user)
	answer = tutor.ask(question, _clean_history(history))
	return {"answer": answer}


@frappe.whitelist(methods=["POST"])
@per_user_rate_limit(limit=TUTOR_CALLS_PER_HOUR, seconds=60 * 60)
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
	# Checked before the speech-to-text call, which is billed too.
	_authorize(course, lesson or None)
	_check_question(question)
	history = _clean_history(history)
	user = frappe.session.user

	def _produce(q: str) -> str:
		_check_question(q)
		return TutorAi(course=course, lesson=lesson or None, user=user).ask(q, history)

	return run_audio_turn(
		audio=audio,
		text=question,
		mime=mime,
		language=language,
		produce_answer=_produce,
		want_audio=want_audio,
	)
