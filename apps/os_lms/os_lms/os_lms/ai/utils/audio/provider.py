"""Provider-agnostic audio (STT / TTS) abstraction.

Mirrors the LLM layer (ai/utils/llm): business code consumes AudioProvider
through this module and never reaches into adapter modules. Concrete adapters
live in providers/ and encapsulate any SDK / HTTP detail.

Capabilities are optional: a provider that supports only one of STT / TTS
inherits the AudioUnsupported default for the other, so providers without audio
(DeepSeek, Anthropic) need no code at all — they are simply never registered.
"""
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field

from .errors import AudioUnsupported


@dataclass
class TranscriptionResult:
    text: str
    model: str
    provider: str
    raw: dict = field(default_factory=dict)


@dataclass
class SpeechResult:
    audio: bytes
    mime: str
    model: str
    provider: str


class AudioProvider(ABC):
    """Abstract base for an audio provider adapter.

    Neither capability method is abstract: an adapter implements only what it
    supports. The defaults raise AudioUnsupported, so an uncapable provider
    degrades cleanly instead of crashing.
    """

    name: str = ""

    def transcribe(
        self,
        audio: bytes,
        *,
        mime: str,
        language: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> TranscriptionResult:
        """Speech-to-text. Returns the transcription."""
        raise AudioUnsupported(
            f"{self.name or 'provider'} does not support speech-to-text"
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
        """Text-to-speech. Returns the synthesized audio bytes."""
        raise AudioUnsupported(
            f"{self.name or 'provider'} does not support text-to-speech"
        )

    def health_check(self) -> bool:
        """Lightweight check used to validate configuration."""
        return False
