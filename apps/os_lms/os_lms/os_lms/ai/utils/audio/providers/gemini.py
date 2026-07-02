"""Google Gemini audio adapter (STT + TTS).

Unlike the chat layer — where Gemini reuses Google's OpenAI-compatible endpoint
(see ai/utils/llm/providers/gemini.py) — the OpenAI-compat layer does NOT expose
the audio endpoints (`/audio/transcriptions`, `/audio/speech`). So this adapter
speaks Gemini's *native* `generateContent` REST API over `requests` (SDK-free,
same encapsulation rule the other adapters follow).

Two asymmetric shapes, both on the same endpoint:

- transcribe -> generateContent with the audio as an `inlineData` part plus a
  "transcribe this" text prompt; the transcript is read back from the text part.
- synthesize -> generateContent on a dedicated TTS model with
  `responseModalities: ["AUDIO"]` + a `speechConfig` voice. The response carries
  raw PCM (audio/L16;rate=24000), which we wrap in a WAV header so the browser
  `<audio>` element can play it directly (OpenAI returns ready-to-play mp3).
"""
from __future__ import annotations

import base64
import io
import wave

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


@register_audio("gemini")
class GeminiAudioProvider(AudioProvider):
    """Gemini native audio over HTTP. Stateless; safe to instantiate per call."""

    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    # A normal multimodal model handles transcription (audio understanding).
    DEFAULT_STT_MODEL = "gemini-2.5-flash"
    # TTS needs a dedicated *-tts model.
    DEFAULT_TTS_MODEL = "gemini-2.5-flash-preview-tts"
    DEFAULT_VOICE = "Kore"

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
        used_model = self._stt_model(model)
        prompt = (
            "Transcribe the following audio recording verbatim. "
            "Return only the transcript text, with no preamble, labels, or commentary."
        )
        if language:
            prompt += f" The spoken language is {language}."
        body = {
            "contents": [
                {
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": _normalize_input_mime(mime),
                                "data": base64.b64encode(audio).decode("ascii"),
                            }
                        },
                        {"text": prompt},
                    ]
                }
            ],
            "generationConfig": {"temperature": 0},
        }
        payload = self._post(used_model, body, timeout)
        text = _extract_text(payload)
        if not text:
            # A text-less 200 response is a failure, not a valid empty transcript.
            # The most common cause is that Gemini's audio understanding does not
            # accept the browser's WebM/Opus recording (its documented STT inputs
            # are wav, mp3, aac, ogg, flac, aiff). Surface the reason instead of
            # silently returning "".
            raise AudioError(_empty_transcript_message(payload), provider=self.name)
        return TranscriptionResult(
            text=text,
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
        # `fmt` is ignored: Gemini always returns raw PCM, which we wrap in WAV.
        used_model = self._tts_model(model)
        used_voice = self._voice(voice)
        body = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": used_voice}}
                },
            },
        }
        payload = self._post(used_model, body, timeout)
        data, audio_mime = _extract_audio(payload)
        if not data:
            raise AudioError(
                "Gemini returned no audio data", provider=self.name
            )
        pcm = base64.b64decode(data)
        wav = _pcm_to_wav(pcm, sample_rate=_rate_from_mime(audio_mime))
        return SpeechResult(
            audio=wav,
            mime="audio/wav",
            model=used_model,
            provider=self.name,
        )

    def health_check(self) -> bool:
        return bool(self._config.api_key)

    # -- internals --

    def _post(self, model: str, body: dict, timeout: float) -> dict:
        url = f"{self._base_url}/models/{model}:generateContent"
        headers = {
            "x-goog-api-key": self._config.api_key,
            "Content-Type": "application/json",
        }
        try:
            r = requests.post(url, headers=headers, json=body, timeout=timeout)
        except requests.Timeout as e:
            raise AudioTimeout(str(e), provider=self.name, cause=e) from e
        except requests.RequestException as e:
            raise AudioServerError(str(e), provider=self.name, cause=e) from e

        self._check_status(r)
        try:
            return r.json()
        except ValueError as e:
            raise AudioError(
                "Gemini returned a non-JSON response", provider=self.name, cause=e
            ) from e

    def _stt_model(self, model: str | None) -> str:
        return _gemini_model_or(model or self._config.stt_model, self.DEFAULT_STT_MODEL)

    def _tts_model(self, model: str | None) -> str:
        return _gemini_model_or(model or self._config.tts_model, self.DEFAULT_TTS_MODEL)

    def _voice(self, voice: str | None) -> str:
        # Forgiving: the tts_voice setting is shared with OpenAI, so a stored
        # OpenAI voice ("alloy", ...) would be rejected by Gemini. Fall back to
        # the default unless the value is a known Gemini prebuilt voice.
        canonical = _KNOWN_VOICES_LOWER.get((voice or "").strip().lower())
        return canonical or self.DEFAULT_VOICE

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


# Gemini prebuilt TTS voices (https://ai.google.dev/gemini-api/docs/speech-generation).
_KNOWN_VOICES = (
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
    "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
    "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
)
_KNOWN_VOICES_LOWER = {v.lower(): v for v in _KNOWN_VOICES}


def _gemini_model_or(candidate: str | None, default: str) -> str:
    """Return `candidate` only if it looks like a Gemini model.

    The stt_model / tts_model settings are shared across providers, so a value
    left over from OpenAI ("gpt-4o-mini-tts") must not be sent to Gemini. All
    Gemini models are prefixed "gemini-", so anything else falls back to default.
    """
    name = (candidate or "").strip()
    return name if name.startswith("gemini") else default


def _normalize_input_mime(mime: str) -> str:
    """Strip codec params from the recorder mime (e.g. "audio/webm;codecs=opus").

    Note: Gemini's documented STT input formats are wav, mp3, aac, ogg, flac,
    aiff — NOT webm. Chrome's MediaRecorder produces webm/opus, which Gemini may
    reject; the provider error is surfaced to the admin. Transcoding is out of
    scope for this iteration (see PLAN.md).
    """
    base = (mime or "").split(";")[0].strip().lower()
    return base or "audio/webm"


def _extract_text(payload: dict) -> str:
    parts = _first_candidate_parts(payload)
    chunks = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
    return "".join(chunks).strip()


def _empty_reason(payload: dict) -> str:
    """Best-effort explanation of why a Gemini response carried no text."""
    bits = []
    candidates = payload.get("candidates") or []
    if candidates:
        finish = candidates[0].get("finishReason")
        if finish:
            bits.append(f"finishReason={finish}")
    else:
        bits.append("no candidates")
    feedback = payload.get("promptFeedback") or {}
    block = feedback.get("blockReason")
    if block:
        bits.append(f"blockReason={block}")
    return ", ".join(bits) or "empty response"


def _empty_transcript_message(payload: dict) -> str:
    return (
        f"Gemini returned no transcript ({_empty_reason(payload)}). This usually "
        "means the audio format is unsupported: Gemini STT does not accept the "
        "browser's WebM/Opus recording — send a supported format (wav, mp3, aac, "
        "ogg, flac) or use the OpenAI STT provider."
    )


def _extract_audio(payload: dict) -> tuple[str, str]:
    """Return (base64_data, mime) of the first inline audio part, or ("", "")."""
    for p in _first_candidate_parts(payload):
        if not isinstance(p, dict):
            continue
        inline = p.get("inlineData") or p.get("inline_data")
        if isinstance(inline, dict) and inline.get("data"):
            mime = inline.get("mimeType") or inline.get("mime_type") or ""
            return inline["data"], mime
    return "", ""


def _first_candidate_parts(payload: dict) -> list:
    candidates = payload.get("candidates") or []
    if not candidates:
        return []
    return (candidates[0].get("content") or {}).get("parts") or []


def _rate_from_mime(mime: str) -> int:
    """Parse the sample rate from "audio/L16;codec=pcm;rate=24000" (default 24000)."""
    for part in (mime or "").split(";"):
        part = part.strip().lower()
        if part.startswith("rate="):
            try:
                return int(part.split("=", 1)[1])
            except (ValueError, IndexError):
                return 24000
    return 24000


def _pcm_to_wav(
    pcm: bytes,
    *,
    sample_rate: int = 24000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """Wrap raw 16-bit PCM in a WAV container so a browser can play it."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def _extract_error(r: requests.Response) -> str | None:
    try:
        data = r.json()
    except ValueError:
        return (r.text or "")[:200] or None
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            return err.get("message") or err.get("status")
        if isinstance(err, str):
            return err
    return None
