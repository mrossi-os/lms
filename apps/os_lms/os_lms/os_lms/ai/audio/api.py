"""Whitelisted endpoints for the AI tutor's audio features (STT / TTS).

Thin feature layer over the audio provider abstraction (ai/utils/audio),
mirroring ai/tutor/api.py. Consumed by the tutor chat:

- transcribe(): microphone input -> text
- synthesize(): assistant answer -> speech (base64)

Audio is carried as base64 in the request/response body (short clips, no File
doc on disk, privacy-friendly).
"""
from __future__ import annotations

import base64
import binascii

import frappe
from frappe import _

from os_lms.os_lms.ai.utils.audio import (
    AudioError,
    AudioInvalidAuth,
    AudioInvalidInput,
    AudioRateLimit,
    AudioServerError,
    AudioTimeout,
    AudioUnsupported,
    resolve_audio_provider,
)
from os_lms.os_lms.ai.utils.llm import load_settings

# OpenAI's per-file limit is 25 MB; guard the decoded payload against it.
MAX_AUDIO_BYTES = 25 * 1024 * 1024


@frappe.whitelist()
def transcribe(audio: str, mime: str = "audio/webm", language: str = "it") -> dict:
    """Transcribe a base64-encoded audio clip to text (speech-to-text)."""
    settings = load_settings()
    if not settings.stt_enabled:
        frappe.throw(_("Speech-to-text is not enabled."), frappe.PermissionError)

    raw = _decode_audio(audio)

    try:
        provider = resolve_audio_provider("stt")
        result = provider.transcribe(raw, mime=mime or "audio/webm", language=language or None)
        return {"text": result.text}
    except AudioInvalidInput as e:
        frappe.throw(_("Invalid audio: {0}").format(str(e)))
    except AudioInvalidAuth:
        _throw_provider(_("the transcription provider is not configured correctly"))
    except (AudioRateLimit, AudioServerError, AudioTimeout):
        _throw_provider(_("the transcription service is temporarily unavailable"))
    except AudioUnsupported:
        _throw_provider(_("the selected provider does not support transcription"))
    except AudioError as e:
        # Surface the provider's own message (e.g. invalid model) — it's the
        # actionable part for an admin mis-configuration.
        _throw_provider(str(e) or _("transcription failed"))


@frappe.whitelist()
def synthesize(text: str, voice: str | None = None) -> dict:
    """Synthesize speech from text (text-to-speech). Returns base64 audio."""
    settings = load_settings()
    if not settings.tts_enabled:
        frappe.throw(_("Text-to-speech is not enabled."), frappe.PermissionError)

    clean = (text or "").strip()
    if not clean:
        frappe.throw(_("Nothing to read aloud."))

    try:
        provider = resolve_audio_provider("tts")
        result = provider.synthesize(clean, voice=voice or settings.tts_voice or "alloy")
        return {
            "audio": base64.b64encode(result.audio).decode("ascii"),
            "mime": result.mime,
        }
    except AudioInvalidAuth:
        _throw_provider(_("the speech provider is not configured correctly"))
    except (AudioRateLimit, AudioServerError, AudioTimeout):
        _throw_provider(_("the speech service is temporarily unavailable"))
    except AudioUnsupported:
        _throw_provider(_("the selected provider does not support speech synthesis"))
    except AudioError as e:
        # Surface the provider's own message (e.g. invalid model) — it's the
        # actionable part for an admin mis-configuration.
        _throw_provider(str(e) or _("speech synthesis failed"))


def _decode_audio(audio: str) -> bytes:
    if not audio:
        frappe.throw(_("No audio provided."))
    # Accept an optional data URL prefix ("data:audio/webm;base64,....").
    if audio.strip().lower().startswith("data:") and "," in audio:
        audio = audio.split(",", 1)[1]
    try:
        raw = base64.b64decode(audio, validate=True)
    except (binascii.Error, ValueError):
        frappe.throw(_("Audio payload is not valid base64."))
    if not raw:
        frappe.throw(_("Audio payload is empty."))
    if len(raw) > MAX_AUDIO_BYTES:
        frappe.throw(_("Audio is too large (max 25 MB)."))
    return raw


def _throw_provider(reason: str) -> None:
    frappe.log_error(title="LMSA audio error")
    frappe.throw(_("Audio error: {0}.").format(reason))
