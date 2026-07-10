"""OpenAI audio adapter (STT + TTS).

Speaks the OpenAI audio HTTP API over `requests` (already in the Frappe env),
SDK-free — the same encapsulation rule the LLM adapters follow.

- transcribe -> POST {base_url}/audio/transcriptions   (multipart upload)
- synthesize -> POST {base_url}/audio/speech           (json -> audio bytes)
"""
from __future__ import annotations

import requests

from ..config import AudioProviderConfig
from ..errors import (
    AudioError,
    AudioInvalidAuth,
    AudioRateLimit,
    AudioServerError,
    AudioTimeout,
)
from ..provider import AudioProvider, SpeechResult, TranscriptionResult
from ..registry import register_audio


@register_audio("openai")
class OpenAIAudioProvider(AudioProvider):
    """OpenAI audio over HTTP. Stateless; safe to instantiate per call."""

    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_STT_MODEL = "gpt-4o-mini-transcribe"
    DEFAULT_TTS_MODEL = "gpt-4o-mini-tts"

    def __init__(self, config: AudioProviderConfig):
        self._config = config
        self._base_url = (config.base_url or self.DEFAULT_BASE_URL).rstrip("/")

    # -- speech-to-text --

    def transcribe(
        self,
        audio: bytes,
        *,
        mime: str,
        language: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> TranscriptionResult:
        used_model = model or self._config.stt_model or self.DEFAULT_STT_MODEL
        # OpenAI validates the file extension, so derive it from the mime type.
        files = {"file": (f"audio.{_ext_for_mime(mime)}", audio, mime)}
        data: dict[str, str] = {"model": used_model}
        if language:
            data["language"] = language
        url = f"{self._base_url}/audio/transcriptions"
        try:
            r = requests.post(
                url, headers=self._auth_header(), files=files, data=data, timeout=timeout
            )
        except requests.Timeout as e:
            raise AudioTimeout(str(e), provider=self.name, cause=e) from e
        except requests.RequestException as e:
            raise AudioServerError(str(e), provider=self.name, cause=e) from e

        self._check_status(r)
        try:
            payload = r.json()
        except ValueError as e:
            raise AudioError(
                "Provider returned a non-JSON transcription", provider=self.name, cause=e
            ) from e
        return TranscriptionResult(
            text=payload.get("text", "") or "",
            model=used_model,
            provider=self.name,
            raw=payload,
        )

    # -- text-to-speech --

    def synthesize(
        self,
        text: str,
        *,
        voice: str,
        model: str | None = None,
        fmt: str = "mp3",
        timeout: float = 60.0,
    ) -> SpeechResult:
        used_model = model or self._config.tts_model or self.DEFAULT_TTS_MODEL
        payload = {
            "model": used_model,
            "voice": voice or self._config.tts_voice or "alloy",
            "input": text,
            "response_format": fmt,
        }
        headers = {**self._auth_header(), "Content-Type": "application/json"}
        url = f"{self._base_url}/audio/speech"
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        except requests.Timeout as e:
            raise AudioTimeout(str(e), provider=self.name, cause=e) from e
        except requests.RequestException as e:
            raise AudioServerError(str(e), provider=self.name, cause=e) from e

        self._check_status(r)
        return SpeechResult(
            audio=r.content,
            mime=_MIME_FOR_FMT.get(fmt, "audio/mpeg"),
            model=used_model,
            provider=self.name,
        )

    def health_check(self) -> bool:
        return bool(self._config.api_key)

    # -- internals --

    def _auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._config.api_key}"}

    def _check_status(self, r: requests.Response) -> None:
        if 200 <= r.status_code < 300:
            return
        msg = _extract_error(r) or f"HTTP {r.status_code}"
        if r.status_code in (401, 403):
            raise AudioInvalidAuth(msg, provider=self.name)
        if r.status_code == 429:
            raise AudioRateLimit(msg, provider=self.name)
        if r.status_code >= 500:
            raise AudioServerError(msg, provider=self.name)
        raise AudioError(msg, provider=self.name)


_MIME_FOR_FMT = {
    "mp3": "audio/mpeg",
    "opus": "audio/opus",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "wav": "audio/wav",
    "pcm": "audio/pcm",
}

# OpenAI accepts: flac, m4a, mp3, mp4, mpeg, mpga, oga, ogg, wav, webm.
_EXT_FOR_MIME = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "mp4",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/m4a": "m4a",
    "audio/x-m4a": "m4a",
}


def _ext_for_mime(mime: str) -> str:
    base = (mime or "").split(";")[0].strip().lower()
    return _EXT_FOR_MIME.get(base, "webm")


def _extract_error(r: requests.Response) -> str | None:
    try:
        data = r.json()
    except ValueError:
        return (r.text or "")[:200] or None
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            return err.get("message") or err.get("type")
        if isinstance(err, str):
            return err
    return None
