"""Unit tests for the tutor audio endpoint (ai/tutor/api.py::ask_audio)."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from unittest.mock import patch

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.audio import pipeline
from os_lms.os_lms.ai.tutor import api as tutor_api
from os_lms.os_lms.ai.utils.audio import build_audio_config, get_audio_provider


@dataclass
class _FakeSettings:
    stt_enabled: bool = True
    tts_enabled: bool = True
    tts_voice: str = "alloy"


def _mock_provider(_capability):
    return get_audio_provider(build_audio_config("mock", None))


class _FakeTutor:
    def __init__(self, course, lesson, user):
        pass

    def ask(self, question, history):
        return "TUTOR:" + question


class TestAskAudio(UnitTestCase):
    def setUp(self):
        self._orig_load = pipeline.load_settings
        self._orig_resolve = pipeline.resolve_audio_provider
        pipeline.resolve_audio_provider = _mock_provider

    def tearDown(self):
        pipeline.load_settings = self._orig_load
        pipeline.resolve_audio_provider = self._orig_resolve

    def _settings(self, **kw):
        pipeline.load_settings = lambda: _FakeSettings(**kw)

    def test_text_question(self):
        self._settings(tts_enabled=False)
        with patch.object(tutor_api, "TutorAi", _FakeTutor):
            out = tutor_api.ask_audio(course="C", lesson="", question="ciao")
        self.assertEqual(out["question_text"], "ciao")
        self.assertEqual(out["answer_text"], "TUTOR:ciao")
        self.assertIsNone(out["audio_base64"])

    def test_audio_question_returns_audio(self):
        self._settings(stt_enabled=True, tts_enabled=True)
        audio = base64.b64encode(b"0123456789").decode()
        with patch.object(tutor_api, "TutorAi", _FakeTutor):
            out = tutor_api.ask_audio(course="C", lesson="L", audio=audio)
        self.assertIn("MOCK transcription", out["question_text"])
        self.assertTrue(out["answer_text"].startswith("TUTOR:"))
        self.assertTrue(base64.b64decode(out["audio_base64"]).startswith(b"MOCK_AUDIO:"))

    def test_history_list_is_accepted(self):
        self._settings(tts_enabled=False)
        history = [{"from": "user", "message": "prev"}]
        with patch.object(tutor_api, "TutorAi", _FakeTutor):
            out = tutor_api.ask_audio(course="C", lesson="", question="hi", history=history)
        self.assertEqual(out["answer_text"], "TUTOR:hi")
