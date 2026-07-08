"""Combined audio-chat pipeline: STT (optional) -> chat -> TTS (optional).

Wraps a section's existing chat logic (passed as `produce_answer`) with a
speech-to-text step on the input and a text-to-speech step on the output, so a
single API call handles a whole voice (or text) turn. Pure of chat specifics.
"""
from __future__ import annotations

import base64
from typing import Callable

import frappe
from frappe import _

# Reuse the shared base64 decode + 25 MB guard from the endpoint layer.
from os_lms.os_lms.ai.audio.api import MAX_AUDIO_BYTES, _decode_audio  # noqa: F401
from os_lms.os_lms.ai.utils.audio import AudioError, resolve_audio_provider
from os_lms.os_lms.ai.utils.llm import load_settings


def run_audio_turn(
	*,
	audio: str | None,
	text: str | None,
	mime: str,
	language: str,
	produce_answer: Callable[[str], str],
	want_audio: bool,
) -> dict:
	"""STT (if `audio`) -> produce_answer(question) -> TTS (if enabled).

	Returns {question_text, answer_text, audio_base64|None, mime|None}. Raises
	PermissionError if audio is given while STT is disabled, ValidationError on
	empty text. A TTS failure is swallowed (text-only degradation).
	"""
	settings = load_settings()

	if audio:
		if not settings.stt_enabled:
			frappe.throw(_("Speech-to-text is not enabled."), frappe.PermissionError)
		raw = _decode_audio(audio)
		question_text = resolve_audio_provider("stt").transcribe(
			raw, mime=mime or "audio/webm", language=language or None
		).text
	else:
		question_text = text

	# Reject empty input for both paths: a typed blank message and a silent
	# recording (non-empty audio that the STT transcribes to nothing) must not
	# reach produce_answer, which would spend a turn on an empty user message.
	question_text = (question_text or "").strip()
	if not question_text:
		frappe.throw(_("Message cannot be empty"))

	answer_text = produce_answer(question_text)

	audio_base64 = None
	out_mime = None
	if want_audio and settings.tts_enabled:
		try:
			speech = resolve_audio_provider("tts").synthesize(
				answer_text, voice=settings.tts_voice or "alloy"
			)
			audio_base64 = base64.b64encode(speech.audio).decode("ascii")
			out_mime = speech.mime
		except AudioError:
			frappe.log_error(title="LMSA audio-turn TTS error")

	return {
		"question_text": question_text,
		"answer_text": answer_text,
		"audio_base64": audio_base64,
		"mime": out_mime,
	}
