# Single-call Audio Chat (STT→LLM→TTS) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the tutor and simulation voice/audio chat into a single backend call that does STT (if audio) → the existing chat logic → TTS (if enabled) and returns question text, answer text, and answer audio together.

**Architecture:** A shared `run_audio_turn` pipeline helper wraps a section's existing chat callback with STT before and TTS after. Two thin whitelisted endpoints (`tutor.api.ask_audio`, `simulations.api.send_message_audio`) pass their own `produce_answer`. On the client, the mic records raw audio and posts it directly; typed messages also use the combined call when TTS is on; the returned audio is played and cached (via `useTextToSpeech.prime`) so no re-synthesis occurs; while an audio turn is in flight the user bubble shows an audio icon + `…` placeholder replaced by the transcription.

**Tech Stack:** Frappe (Python 3.10, `frappe.tests.UnitTestCase`), Vue 3 (`frappe-ui`, Pinia, Vite), the existing `ai/utils/audio` provider layer.

## Global Constraints

- Whitelisted API methods stay thin (validate → gate → delegate → plain dict) and require type-annotated params + return (`require_type_annotated_api_methods = True`).
- Indentation per file: `ai/audio/*`, `ai/tutor/api.py`, `ai/simulations/orchestrator.py` use TABS; `ai/simulations/api.py` and all `tests/*.py` use 4 SPACES. Match the file you edit.
- Comments in English; user-facing SPA strings stay Italian wrapped in `__()`.
- Audio in/out is base64 in the request/response body; the 25 MB guard + `data:` prefix stripping already live in `ai/audio/api.py::_decode_audio` (`MAX_AUDIO_BYTES`). Reuse it — do not duplicate.
- Gating: audio INPUT requires `stt_enabled` (else `PermissionError`); audio OUTPUT requires `tts_enabled` (else `audio_base64` is `None`). TTS failure degrades to text (no hard error). STT/LLM failure propagates.
- Backend tests run INSIDE Docker: `docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost run-tests --app os_lms --module <MODULE>'`. The container is already running.
- Frontend has no JS unit runner — verify with `cd frontend && yarn build` (must exit 0).
- The mock audio provider (used in tests) returns text containing `"MOCK transcription"` for `transcribe` and audio bytes prefixed `b"MOCK_AUDIO:"` with mime `"audio/mpeg"` for `synthesize`.
- Do NOT change the existing `transcribe`/`synthesize` endpoints or the `ai/utils/audio` provider layer — still used by the per-message read button.

---

## File Structure

**Backend**
- Create `apps/os_lms/os_lms/os_lms/ai/audio/pipeline.py` — `run_audio_turn` helper.
- Create `apps/os_lms/os_lms/os_lms/ai/audio/tests/test_pipeline.py`.
- Modify `apps/os_lms/os_lms/os_lms/ai/tutor/api.py` — add `ask_audio`.
- Create `apps/os_lms/os_lms/os_lms/ai/tutor/tests/__init__.py` + `test_api.py`.
- Modify `apps/os_lms/os_lms/os_lms/ai/simulations/api.py` — add `send_message_audio`.
- Modify `apps/os_lms/os_lms/os_lms/ai/simulations/tests/test_api.py`.

**Frontend**
- Modify `frontend/src/oslms/composables/useSpeechToText.js` — `onAudio` option.
- Modify `frontend/src/oslms/components/ai/MicButton.vue` — `raw` prop + `@audio`.
- Modify `frontend/src/oslms/composables/useTextToSpeech.js` — `prime`.
- Modify `frontend/src/oslms/utils/audioApi.js` — export `base64ToObjectUrl`.
- Modify `frontend/src/oslms/components/ai/ChatBot.vue` — tutor combined flow + pending bubble.
- Modify `frontend/src/oslms/composables/useSimulationSession.js` — combined `send`.
- Modify `frontend/src/oslms/components/simulations/ChatSession.vue` — raw mic, pending bubble, drop the old autoplay watcher.
- Modify `frontend/src/oslms/pages/Simulation/SimulationPlay.vue` — wire `@send-audio`.

---

## Task 1: `run_audio_turn` pipeline helper

**Files:**
- Create: `apps/os_lms/os_lms/os_lms/ai/audio/pipeline.py`
- Test: `apps/os_lms/os_lms/os_lms/ai/audio/tests/test_pipeline.py`

**Interfaces:**
- Produces: `run_audio_turn(*, audio: str | None, text: str | None, mime: str, language: str, produce_answer: Callable[[str], str], want_audio: bool) -> dict` returning `{"question_text", "answer_text", "audio_base64" | None, "mime" | None}`. Module-level names `resolve_audio_provider` and `load_settings` are import targets tests monkeypatch.

- [ ] **Step 1: Write the failing tests** (4-space indent) — `ai/audio/tests/test_pipeline.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.audio.tests.test_pipeline'`
Expected: FAIL — `ModuleNotFoundError: os_lms.os_lms.ai.audio.pipeline`.

- [ ] **Step 3: Implement the pipeline** (TABS) — `ai/audio/pipeline.py`:

```python
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
		question_text = (text or "").strip()
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.audio.tests.test_pipeline'`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/audio/pipeline.py apps/os_lms/os_lms/os_lms/ai/audio/tests/test_pipeline.py
git commit -m "feat(audio): add run_audio_turn pipeline (STT -> chat -> TTS)"
```

---

## Task 2: Tutor `ask_audio` endpoint

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/ai/tutor/api.py`
- Create: `apps/os_lms/os_lms/os_lms/ai/tutor/tests/__init__.py`
- Create: `apps/os_lms/os_lms/os_lms/ai/tutor/tests/test_api.py`

**Interfaces:**
- Consumes: `run_audio_turn` (Task 1); `TutorAi(course, lesson, user).ask(question, history) -> str`.
- Produces: whitelisted `ask_audio(course: str, lesson: str = "", question: str | None = None, audio: str | None = None, mime: str = "audio/webm", language: str = "it", history: list[dict] | None = None, want_audio: bool = True) -> dict` → `{question_text, answer_text, audio_base64, mime}`.

- [ ] **Step 1: Write the failing tests** (4-space indent) — `ai/tutor/tests/test_api.py`:

```python
"""Unit tests for the tutor audio endpoint (ai/tutor/api.py::ask_audio)."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from unittest.mock import patch

import frappe
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

    def test_history_json_string_is_parsed(self):
        self._settings(tts_enabled=False)
        with patch.object(tutor_api, "TutorAi", _FakeTutor):
            out = tutor_api.ask_audio(course="C", lesson="", question="hi", history='[]')
        self.assertEqual(out["answer_text"], "TUTOR:hi")
```

Also create an empty `ai/tutor/tests/__init__.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.tutor.tests.test_api'`
Expected: FAIL — `AttributeError: module ... has no attribute 'ask_audio'`.

- [ ] **Step 3: Add `ask_audio`** (TABS) — append to `ai/tutor/api.py` (keep the existing `ask`, add the import):

```python
from os_lms.os_lms.ai.audio.pipeline import run_audio_turn


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.tutor.tests.test_api'`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/tutor/api.py apps/os_lms/os_lms/os_lms/ai/tutor/tests/
git commit -m "feat(tutor): add ask_audio single-call audio endpoint"
```

---

## Task 3: Simulation `send_message_audio` endpoint

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/ai/simulations/api.py`
- Test: `apps/os_lms/os_lms/os_lms/ai/simulations/tests/test_api.py`

**Interfaces:**
- Consumes: `run_audio_turn` (Task 1); existing `load_session`, `_service()`, `SessionTerminatedError`; `orchestrator.send_message(session_id, user_text) -> frappe._dict` with `.user_turn.name`, `.assistant_turn.name`, `.assistant_turn.text`, `.injection_attempt`.
- Produces: whitelisted `send_message_audio(session_id: str, text: str | None = None, audio: str | None = None, mime: str = "audio/webm", language: str = "it", want_audio: bool = True) -> dict` → `{question_text, answer_text, audio_base64, mime, user_turn, assistant_turn, injection_attempt}`.

- [ ] **Step 1: Write the failing tests** (4-space indent) — add to `ai/simulations/tests/test_api.py`. Import the endpoint and (for audio provider mocking) the pipeline module:

```python
from os_lms.os_lms.ai.audio import pipeline as audio_pipeline
from os_lms.os_lms.ai.simulations.api import send_message_audio
from os_lms.os_lms.ai.utils.audio import build_audio_config, get_audio_provider
```

Add these tests to the existing class that has `self.scenario` (the one used by `start_session`/`send_message` tests). If that class lacks per-test audio-provider mocking, wrap each test locally:

```python
    def _mock_audio(self):
        # Point the pipeline's audio provider + settings at the mock provider.
        self._orig_resolve = audio_pipeline.resolve_audio_provider
        self._orig_load = audio_pipeline.load_settings
        audio_pipeline.resolve_audio_provider = lambda cap: get_audio_provider(
            build_audio_config("mock", None)
        )

        class _S:
            stt_enabled = True
            tts_enabled = True
            tts_voice = "alloy"

        audio_pipeline.load_settings = lambda: _S()

    def _unmock_audio(self):
        audio_pipeline.resolve_audio_provider = self._orig_resolve
        audio_pipeline.load_settings = self._orig_load

    def test_send_message_audio_text_persists_turns_and_returns_audio(self):
        start = start_session(scenario_id=self.scenario.name)
        self._mock_audio()
        try:
            out = send_message_audio(session_id=start["session"], text="ciao")
        finally:
            self._unmock_audio()
        self.assertEqual(out["question_text"], "ciao")
        self.assertTrue(out["answer_text"])
        self.assertTrue(out["assistant_turn"])
        self.assertTrue(out["user_turn"])
        self.assertTrue(base64.b64decode(out["audio_base64"]).startswith(b"MOCK_AUDIO:"))
        # Turns were persisted by the orchestrator (user + assistant appended).
        detail = get_session(session_id=start["session"])
        self.assertGreaterEqual(len(detail["turns"]), 3)  # opening + user + assistant

    def test_send_message_audio_owner_only(self):
        start = start_session(scenario_id=self.scenario.name)
        other = _make_student("audio-other@example.com")  # reuse the helper used by other owner tests
        frappe.set_user(other)
        try:
            self._mock_audio()
            with self.assertRaises(frappe.PermissionError):
                send_message_audio(session_id=start["session"], text="ciao")
        finally:
            self._unmock_audio()
            frappe.set_user(self.student)
```

(Use whatever second-user helper the existing owner tests use — mirror `test_send_message` / the isolation test added earlier. Ensure `base64` is imported at the top of the test file.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.simulations.tests.test_api'`
Expected: FAIL — `ImportError: cannot import name 'send_message_audio'`.

- [ ] **Step 3: Add the endpoint** (4-space indent) in `ai/simulations/api.py`, next to `send_message`. Add the import near the top:

```python
from os_lms.os_lms.ai.audio.pipeline import run_audio_turn
```

```python
@frappe.whitelist()
def send_message_audio(
    session_id: str,
    text: str | None = None,
    audio: str | None = None,
    mime: str = "audio/webm",
    language: str = "it",
    want_audio: bool = True,
) -> dict:
    """Single-call audio (or text) simulation turn: STT? -> role-player -> TTS?.

    Reuses the orchestrator's send_message (persists both turns + fires the
    realtime event). Returns question/answer text, answer audio, and the turn
    names for client reconciliation.
    """
    session = load_session(session_id)
    if session.student != frappe.session.user:
        frappe.throw(_("Only the session owner can send messages"), frappe.PermissionError)

    holder: dict = {}

    def _produce(q: str) -> str:
        r = _service().send_message(session_id=session.name, user_text=q)
        holder["user_turn"] = r.user_turn.name
        holder["assistant_turn"] = r.assistant_turn.name
        holder["injection_attempt"] = bool(r.injection_attempt)
        return r.assistant_turn.text

    try:
        result = run_audio_turn(
            audio=audio, text=text, mime=mime, language=language,
            want_audio=want_audio, produce_answer=_produce,
        )
    except SessionTerminatedError:
        frappe.throw(_("This session is no longer accepting messages"), frappe.ValidationError)
    return {**result, **holder}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.simulations.tests.test_api'`
Expected: PASS (existing + 2 new). If the isolated live-worker debrief race appears in an unrelated module, ignore — it is not this module.

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/simulations/api.py apps/os_lms/os_lms/os_lms/ai/simulations/tests/test_api.py
git commit -m "feat(simulations): add send_message_audio single-call audio endpoint"
```

---

## Task 4: Frontend audio foundation (raw mic + TTS cache priming)

**Files:**
- Modify: `frontend/src/oslms/composables/useSpeechToText.js`
- Modify: `frontend/src/oslms/components/ai/MicButton.vue`
- Modify: `frontend/src/oslms/utils/audioApi.js`
- Modify: `frontend/src/oslms/composables/useTextToSpeech.js`

**Interfaces:**
- Produces: `useSpeechToText({ language, onTranscript, onAudio })` — when `onAudio` is given, delivers the raw `Blob` and skips transcription. `MicButton` gains `raw: Boolean`; in raw mode emits `@audio` (Blob) instead of `@transcript`. `audioApi.base64ToObjectUrl(base64, mime) -> string`. `useTextToSpeech().prime(text, base64, mime)` inserts a pre-synthesized clip into the text→URL cache.

- [ ] **Step 1: `useSpeechToText` — add `onAudio`** — change the options destructure and `onStop`:

Signature (line 23):
```javascript
export function useSpeechToText({ language = 'it', onTranscript, onAudio } = {}) {
```
In `onStop`, replace the block from `if (!blob.size) return` onward with:
```javascript
		if (!blob.size) return
		// Raw mode: hand back the recorded clip and skip transcription — the
		// caller sends the audio to a combined endpoint that does STT itself.
		if (onAudio) {
			onAudio(blob)
			return
		}
		isTranscribing.value = true
		try {
			const text = await transcribeAudio(blob, { language })
			if (text) onTranscript?.(text)
		} catch (e) {
			toast.error(e?.message || __('Transcription failed.'))
		} finally {
			isTranscribing.value = false
		}
```

- [ ] **Step 2: `MicButton` — add `raw` prop + `@audio`** — update props, emits, and the composable call:

```javascript
const props = defineProps({
	disabled: { type: Boolean, default: false },
	language: { type: String, default: 'it' },
	raw: { type: Boolean, default: false },
})
const emit = defineEmits(['transcript', 'audio'])

const { isRecording, isTranscribing, isSupported, toggle } = useSpeechToText({
	language: props.language,
	...(props.raw
		? { onAudio: (blob) => emit('audio', blob) }
		: { onTranscript: (text) => emit('transcript', text) }),
})
```

- [ ] **Step 3: `audioApi` — export `base64ToObjectUrl`** — add (reusing the existing private `base64ToBytes`):

```javascript
/** Build a playable object URL from a base64 audio payload. */
export function base64ToObjectUrl(base64, mime) {
	const bytes = base64ToBytes(base64)
	return URL.createObjectURL(new Blob([bytes], { type: mime || 'audio/mpeg' }))
}
```

- [ ] **Step 4: `useTextToSpeech` — add `prime`** — import the helper and add the function:

Change the import line:
```javascript
import { synthesizeSpeech, base64ToObjectUrl } from '@/oslms/utils/audioApi'
```
Inside `useTextToSpeech()`, add before the `return`:
```javascript
	// Insert a server-synthesized clip into the cache so a later play(text)/
	// SpeakButton reuses it without calling synthesize again.
	function prime(text, base64, mime) {
		const clean = (text || '').trim()
		if (!clean || !base64 || !audioEl) return
		if (urlCache.has(clean)) return
		urlCache.set(clean, base64ToObjectUrl(base64, mime))
	}
```
And return it:
```javascript
	return { playingId, isSynthesizing, play, stop, isLoading, prefetch, prime }
```

- [ ] **Step 5: Verify the build**

Run: `cd frontend && yarn build`
Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/oslms/composables/useSpeechToText.js frontend/src/oslms/components/ai/MicButton.vue frontend/src/oslms/utils/audioApi.js frontend/src/oslms/composables/useTextToSpeech.js
git commit -m "feat(audio-ui): raw-blob mic mode and TTS cache priming"
```

---

## Task 5: Tutor `ChatBot.vue` combined flow + pending bubble

**Files:**
- Modify: `frontend/src/oslms/components/ai/ChatBot.vue`

**Interfaces:**
- Consumes: `ask_audio` (Task 2); `MicButton raw @audio` (Task 4); `useTextToSpeech.prime` (Task 4); `blobToBase64` (existing).

- [ ] **Step 1: Script — imports, prime, remove old transcript wiring** — in `<script setup lang="ts">`:

Add to the frappe-ui import: keep `call, toast`. Add:
```javascript
import { Send, Mic } from 'lucide-vue-next'
import { blobToBase64 } from '@/oslms/utils/audioApi'
```
Change the TTS destructure:
```javascript
const { play, prefetch, prime } = useTextToSpeech()
```
Remove `pendingVoice`, `onTranscript` (lines 142-150) and the `@input="pendingVoice = false"` on the textarea. Extend the `Message` interface:
```javascript
interface Message {
	role: 'user' | 'assistant'
	content: string
	sources?: string[]
	audioPending?: boolean
}
```

- [ ] **Step 2: Script — add `onAudioMessage` and route text sends through `ask_audio` when TTS on**

Add:
```javascript
const onAudioMessage = async (blob: Blob) => {
	if (chat.isLoading) return
	const history = chat.messages.map((m) => ({ from: m.role, message: m.content }))
	chat.addMessage({ role: 'user', content: '', audioPending: true })
	const userIdx = chat.messages.length - 1
	chat.isLoading = true
	try {
		const audio = await blobToBase64(blob)
		const res = await call('os_lms.os_lms.ai.tutor.api.ask_audio', {
			course: props.courseId,
			lesson: props.lessonId,
			audio,
			mime: blob.type || 'audio/webm',
			language: 'it',
			history,
			want_audio: ttsEnabled.value,
		})
		chat.messages[userIdx].content = res.question_text || ''
		chat.messages[userIdx].audioPending = false
		const answer = res.answer_text || __('Sorry, I could not find an answer.')
		chat.addMessage({ role: 'assistant', content: answer, sources: [] })
		if (res.audio_base64) {
			prime(answer, res.audio_base64, res.mime)
			if (ttsAutoplayOnStt.value) play(answer, chat.messages.length - 1)
		}
	} catch (error: any) {
		chat.messages[userIdx].audioPending = false
		const msg = error?.message || error?.exc || __('Failed to get response')
		chat.addMessage({ role: 'assistant', content: __('Error: ') + msg })
		toast.error(msg)
	} finally {
		chat.isLoading = false
	}
}
```

In `sendQuestion`, replace the `try { const response = await call('...ask', {...}) ... }` block's API call + answer handling (lines 201-227) with:
```javascript
	try {
		const useAudio = ttsEnabled.value
		const response = await call(
			`os_lms.os_lms.ai.tutor.api.${useAudio ? 'ask_audio' : 'ask'}`,
			{
				course: props.courseId,
				lesson: props.lessonId,
				question: trimmedQuestion,
				history,
				...(useAudio ? { want_audio: true } : {}),
			},
		)
		const answer =
			(useAudio ? response.answer_text : response.answer) ||
			__('Sorry, I could not find an answer.')
		chat.addMessage({ role: 'assistant', content: answer, sources: [] })
		if (useAudio && response.audio_base64) {
			// Typed message: prime the cache so the read button is instant.
			// (Autoplay is reserved for voice messages via onAudioMessage.)
			prime(answer, response.audio_base64, response.mime)
		}
	} catch (error: any) {
```
Also delete the now-unused `viaVoice`/`pendingVoice` lines (182-185) at the top of `sendQuestion`. Keep `prefetch` imported only if still referenced; if not, drop it from the destructure to avoid an unused-var lint. (After this change `prefetch` is unused → destructure `{ play, prime }` only.)

- [ ] **Step 3: Template — raw mic + pending user bubble**

Change the mic (lines 90-94):
```html
			<MicButton
				v-if="sttEnabled"
				raw
				:disabled="chat.isLoading"
				@audio="onAudioMessage"
			/>
```
Change the user message body (line 46-48) to show the pending placeholder:
```html
				<div v-else class="text-sm text-ink-gray-9 whitespace-pre-wrap">
					<span
						v-if="message.audioPending"
						class="flex items-center gap-2 text-ink-gray-5"
					>
						<Mic class="w-4 h-4" />
						<span class="animate-pulse">…</span>
					</span>
					<template v-else>{{ message.content }}</template>
				</div>
```

- [ ] **Step 4: Verify the build**

Run: `cd frontend && yarn build`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/oslms/components/ai/ChatBot.vue
git commit -m "feat(tutor-ui): single-call audio chat with pending-audio bubble"
```

---

## Task 6: Simulation combined flow + pending bubble

**Files:**
- Modify: `frontend/src/oslms/composables/useSimulationSession.js`
- Modify: `frontend/src/oslms/components/simulations/ChatSession.vue`
- Modify: `frontend/src/oslms/pages/Simulation/SimulationPlay.vue`

**Interfaces:**
- Consumes: `send_message_audio` (Task 3); `MicButton raw @audio`, `useTextToSpeech.prime` (Task 4); `blobToBase64` (existing).
- Produces: `useSimulationSession().send({ text, audioBlob })` (was `send(text)`). `ChatSession` emits `send` (text) and `send-audio` (Blob).

- [ ] **Step 1: `useSimulationSession.js` — combined send** — add imports and state at the top of the composable:

Imports (after the existing ones):
```javascript
import { useSettings } from '@/stores/settings'
import { useTextToSpeech } from '@/oslms/composables/useTextToSpeech'
import { blobToBase64 } from '@/oslms/utils/audioApi'
```
Inside `useSimulationSession(...)`, after `const error = ref(null)`:
```javascript
	const settingsStore = useSettings()
	const ttsEnabled = computed(() =>
		Boolean(settingsStore.settings?.data?.tts_enabled),
	)
	const { play, prime } = useTextToSpeech()
```
Add a resource next to `sendResource`:
```javascript
	const sendAudioResource = createResource({
		url: 'os_lms.os_lms.ai.simulations.api.send_message_audio',
		method: 'POST',
		onError(err) {
			error.value = err?.messages?.[0] || __('Send failed')
			toast.error(error.value)
		},
	})
```
Replace the whole `async function send(text) { ... }` with:
```javascript
	function _nextIndex() {
		return (turns.value[turns.value.length - 1]?.turn_index || 0) + 1
	}

	// text: typed message; audioBlob: recorded voice message. When TTS is on (or
	// an audio blob is present) we use the combined endpoint so the reply audio
	// comes back in the same call.
	async function send({ text = '', audioBlob = null } = {}) {
		if (sending.value) return
		const trimmed = (text || '').trim()
		if (!audioBlob && !trimmed) return
		const useCombined = Boolean(audioBlob) || ttsEnabled.value
		sending.value = true
		try {
			if (!useCombined) {
				await sendResource.submit({ session_id: sessionIdRef.value, text: trimmed })
				turns.value.push({
					role: 'user',
					text_content: trimmed,
					turn_index: _nextIndex(),
					_optimistic: true,
				})
				await load()
				return
			}

			turns.value.push(
				audioBlob
					? { role: 'user', _audioPending: true, turn_index: _nextIndex(), _optimistic: true }
					: { role: 'user', text_content: trimmed, turn_index: _nextIndex(), _optimistic: true },
			)
			const idx = turns.value.length - 1
			const params = audioBlob
				? {
						session_id: sessionIdRef.value,
						audio: await blobToBase64(audioBlob),
						mime: audioBlob.type || 'audio/webm',
						language: 'it',
						want_audio: ttsEnabled.value,
					}
				: {
						session_id: sessionIdRef.value,
						text: trimmed,
						language: 'it',
						want_audio: ttsEnabled.value,
					}
			const res = await sendAudioResource.submit(params)
			if (audioBlob && res?.question_text != null) {
				turns.value[idx].text_content = res.question_text
				turns.value[idx]._audioPending = false
			}
			if (res?.audio_base64) {
				prime(res.answer_text, res.audio_base64, res.mime)
				play(res.answer_text, res.assistant_turn)
			}
			await load()
		} finally {
			sending.value = false
		}
	}
```
(`send` is already in the returned object — no change to the return.)

- [ ] **Step 2: `ChatSession.vue` — raw mic, pending bubble, drop the old autoplay watcher**

In `<script setup>`: remove the audio autoplay block added previously — delete `ttsAutoplayOnStt`, `const { play, prefetch } = useTextToSpeech()`, `pendingVoice`, `onTranscript`, `lastAssistantTurn`, `seenAssistantId`, and the `watch(() => props.turns.length, …)` that drives autoplay. Keep `sttEnabled` and `ttsEnabled`. Remove the now-unused `useTextToSpeech` import. Add `Mic` to imports:
```javascript
import { Mic } from 'lucide-vue-next'
```
Update emits:
```javascript
const emit = defineEmits(['send', 'send-audio', 'end'])
```
`onSend` stays (emits `send` with `draft`). The scroll watcher (`watch(() => props.turns.length, … scroll …)`) stays.

Template — the character/user bubble body. Replace the `<div>{{ turn.text_content }}</div>` + `<SpeakButton …>` block with:
```html
				<div v-if="turn._audioPending" class="flex items-center gap-2 text-ink-gray-5">
					<Mic class="w-4 h-4" />
					<span class="animate-pulse">…</span>
				</div>
				<div v-else>{{ turn.text_content }}</div>
				<SpeakButton
					v-if="ttsEnabled && turn.role !== 'user'"
					:text="turn.text_content"
					:id="turn.name || turn.turn_index"
					class="mt-1 -mb-1 shrink-0"
				/>
```
Input row — make the mic raw and emit `send-audio`; drop the `@input` reset:
```html
				<MicButton
					v-if="sttEnabled"
					raw
					:disabled="sending"
					class="shrink-0"
					@audio="$emit('send-audio', $event)"
				/>
```
(Remove `@input="pendingVoice = false"` from the textarea.)

- [ ] **Step 3: `SimulationPlay.vue` — wire text + audio sends to the new `send` shape**

In the `<ChatSession>` usage add `@send-audio="onSendAudio"` alongside the existing `@send="onSend"`. Update the handlers in `<script setup>`:
```javascript
async function onSend(text) {
	await send({ text })
}
async function onSendAudio(blob) {
	await send({ audioBlob: blob })
}
```
(`send` comes from `useSimulationSession`; it now takes an options object.)

- [ ] **Step 4: Verify the build**

Run: `cd frontend && yarn build`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/oslms/composables/useSimulationSession.js frontend/src/oslms/components/simulations/ChatSession.vue frontend/src/oslms/pages/Simulation/SimulationPlay.vue
git commit -m "feat(simulations-ui): single-call audio chat with pending-audio bubble"
```

---

## Task 7: Regression pass

**Files:** none (verification only).

- [ ] **Step 1: Backend suites**

Run:
```bash
docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.audio.tests.test_pipeline'
docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.audio.tests.test_api'
docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.tutor.tests.test_api'
docker compose -f docker/docker-compose.yml exec -T -u frappe frappe bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.simulations.tests.test_api'
```
Expected: all PASS. (The pre-existing `test_quota` failure lives only in `test_orchestrator`; `test_debrief_job`'s live-worker lock race is unrelated — neither is touched here.)

- [ ] **Step 2: Frontend build**

Run: `cd frontend && yarn build`
Expected: exit 0.

- [ ] **Step 3: Commit any fixups**

```bash
git add -A
git commit -m "test(audio): regression fixups for single-call audio chat"
```

---

## Self-Review (coverage map)

- Spec §Backend `run_audio_turn` → Task 1. `ask_audio` → Task 2. `send_message_audio` → Task 3.
- Spec §Frontend 4 (`useSpeechToText.onAudio`), 5 (`MicButton.raw`), 6 (`useTextToSpeech.prime`), 7 (`audioApi`) → Task 4. §8 tutor → Task 5. §9 simulation → Task 6.
- Gating (audio-in⇒stt, audio-out⇒tts, graceful TTS fail) → Task 1 tests. Pending-audio bubble → Tasks 5 (tutor) & 6 (simulation). Double-play avoided by removing the ChatSession autoplay watcher (Task 6) — playback is driven only by the combined response.
- Client send-path table (voice⇒combined, typed+tts⇒combined, typed+no-tts⇒existing) → Task 5 (`sendQuestion`) & Task 6 (`send`).
- Testing spec → Tasks 1–3, 7.
- Type consistency: response keys `{question_text, answer_text, audio_base64, mime, user_turn, assistant_turn}` are produced identically in Tasks 1/2/3 and consumed identically in Tasks 5/6. `send({text, audioBlob})` defined in Task 6 and called with that shape in Task 6 Step 3. `prime(text, base64, mime)` defined in Task 4 and called in Tasks 5/6.
- Note: `TutorAi` in tutor tests is patched via `patch.object(tutor_api, "TutorAi", _FakeTutor)` so no RAG/embeddings are exercised.
