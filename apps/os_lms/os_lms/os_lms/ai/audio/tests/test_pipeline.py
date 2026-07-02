"""Unit tests for the combined audio-turn pipeline (ai/audio/pipeline.py).

The provider layer and settings loader are monkeypatched; the chat step is a
stub callback, so no DB rows or network are needed."""
from __future__ import annotations

import base64
from dataclasses import dataclass

import frappe
from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.audio import pipeline
from os_lms.os_lms.ai.utils.audio import AudioError, build_audio_config, get_audio_provider


@dataclass
class _FakeSettings:
    stt_enabled: bool = True
    tts_enabled: bool = True
    tts_voice: str = "alloy"


def _mock_provider(_capability):
    return get_audio_provider(build_audio_config("mock", None))


class _Base(UnitTestCase):
    def setUp(self):
        self._orig_load = pipeline.load_settings
        self._orig_resolve = pipeline.resolve_audio_provider
        pipeline.resolve_audio_provider = _mock_provider

    def tearDown(self):
        pipeline.load_settings = self._orig_load
        pipeline.resolve_audio_provider = self._orig_resolve

    def _settings(self, **kw):
        pipeline.load_settings = lambda: _FakeSettings(**kw)


class TestRunAudioTurn(_Base):
    def test_audio_in_transcribes_and_synthesizes(self):
        self._settings(stt_enabled=True, tts_enabled=True)
        audio = base64.b64encode(b"0123456789").decode()
        out = pipeline.run_audio_turn(
            audio=audio, text=None, mime="audio/webm", language="it",
            produce_answer=lambda q: f"ANS:{q[:4]}", want_audio=True,
        )
        self.assertIn("MOCK transcription", out["question_text"])
        self.assertTrue(out["answer_text"].startswith("ANS:"))
        self.assertTrue(base64.b64decode(out["audio_base64"]).startswith(b"MOCK_AUDIO:"))
        self.assertEqual(out["mime"], "audio/mpeg")

    def test_text_in_no_audio_when_tts_disabled(self):
        self._settings(stt_enabled=True, tts_enabled=False)
        out = pipeline.run_audio_turn(
            audio=None, text="ciao", mime="audio/webm", language="it",
            produce_answer=lambda q: "risposta", want_audio=True,
        )
        self.assertEqual(out["question_text"], "ciao")
        self.assertEqual(out["answer_text"], "risposta")
        self.assertIsNone(out["audio_base64"])

    def test_audio_in_requires_stt_enabled(self):
        self._settings(stt_enabled=False, tts_enabled=True)
        audio = base64.b64encode(b"0123456789").decode()
        with self.assertRaises(frappe.PermissionError):
            pipeline.run_audio_turn(
                audio=audio, text=None, mime="audio/webm", language="it",
                produce_answer=lambda q: "x", want_audio=True,
            )

    def test_empty_text_raises(self):
        self._settings()
        with self.assertRaises(frappe.ValidationError):
            pipeline.run_audio_turn(
                audio=None, text="   ", mime="audio/webm", language="it",
                produce_answer=lambda q: "x", want_audio=True,
            )

    def test_tts_failure_degrades_to_text(self):
        self._settings(stt_enabled=True, tts_enabled=True)

        class _Boom:
            def synthesize(self, *a, **k):
                raise AudioError("boom")

        pipeline.resolve_audio_provider = (
            lambda cap: _Boom() if cap == "tts" else _mock_provider(cap)
        )
        out = pipeline.run_audio_turn(
            audio=None, text="ciao", mime="audio/webm", language="it",
            produce_answer=lambda q: "risposta", want_audio=True,
        )
        self.assertIsNone(out["audio_base64"])
        self.assertEqual(out["answer_text"], "risposta")
