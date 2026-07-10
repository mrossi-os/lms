"""Deterministic mock audio provider for tests and local development.

Mirrors ai/utils/llm/providers/mock: no network, no keys. Useful for unit tests
of the API layer and for Cypress E2E with stt_provider / tts_provider = "mock".
"""
from __future__ import annotations

from ..config import AudioProviderConfig
from ..provider import AudioProvider, SpeechResult, TranscriptionResult
from ..registry import register_audio


@register_audio("mock")
class MockAudioProvider(AudioProvider):
    """Deterministic adapter: fixed transcription / synthesized bytes."""

    def __init__(self, config: AudioProviderConfig):
        self._config = config

    def transcribe(
        self,
        audio: bytes,
        *,
        mime: str,
        language: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> TranscriptionResult:
        return TranscriptionResult(
            text=f"MOCK transcription ({len(audio)} bytes, {mime})",
            model=model or self._config.stt_model or "mock-stt",
            provider=self.name,
            raw={"mock": True},
        )

    def synthesize(
        self,
        text: str,
        *,
        voice: str,
        model: str | None = None,
        fmt: str = "mp3",
        timeout: float = 60.0,
    ) -> SpeechResult:
        return SpeechResult(
            audio=b"MOCK_AUDIO:" + text.encode("utf-8")[:32],
            mime="audio/mpeg",
            model=model or self._config.tts_model or "mock-tts",
            provider=self.name,
        )

    def health_check(self) -> bool:
        return True
