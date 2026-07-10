# Single-call audio chat (STT → LLM → TTS) for tutor + simulation

**Date:** 2026-07-02
**Status:** Approved design, pending implementation plan
**Area:** `apps/os_lms` (backend) + `frontend/src/oslms` (frontend)

## Problem

Today, using voice in the AI tutor chat and the simulation chat costs three separate
round-trips orchestrated by the client: `transcribe` (STT) → `ask`/`send_message` (LLM) →
`synthesize` (TTS). This is slow and chatty. We want a single backend call that receives the
input (audio or text), runs STT (if audio) → the existing chat logic → TTS, and returns the
transcribed question, the answer text, and the answer audio together.

## Goals

1. One combined endpoint per section (tutor, simulation) that internally does
   STT (if audio) → LLM → TTS (if enabled) and returns `{question_text, answer_text,
   audio_base64, mime}` in a single response.
2. The mic sends the recorded audio **directly** (no editable transcription step).
3. Typed messages also use the combined call when TTS is enabled, so the reply audio comes
   back in the same call (text → LLM → TTS).
4. While an audio message is in flight, the user's bubble shows an audio icon + `…` loading
   placeholder, replaced by the transcription (`question_text`) when the response arrives.
5. Reuse the answer audio returned by the server for playback and for the per-message read
   button (no re-synthesis).

## Non-goals

- No change to the realtime voice (speech-to-speech) simulation modality.
- No change to the STT/TTS provider layer (`ai/utils/audio`) or the existing standalone
  `transcribe`/`synthesize` endpoints (kept for the per-message read button).

## Decisions (from brainstorming)

- Mic = direct one-call send (loses the editable-transcription preview). Confirmed.
- Combined call applies to **both** voice input and typed input (when TTS enabled). Confirmed.
- Audio input requires `stt_enabled`; audio output requires `tts_enabled` (else text-only).
- Pending-audio user bubble: audio icon + `…`, replaced by `question_text` on response.

## Existing pieces reused (unchanged)

- Audio provider layer: `resolve_audio_provider("stt"|"tts")` →
  `transcribe(audio, *, mime, language) -> TranscriptionResult(.text)` /
  `synthesize(text, *, voice) -> SpeechResult(.audio, .mime)`.
- Tutor chat: `TutorAi(course, lesson, user).ask(question, history) -> str`
  (`ai/tutor/tutor_ai.py`); handles its own RAG + audit logging. History shape:
  `[{"from": "user"|"assistant", "message": str}]`.
- Simulation chat: `SessionOrchestrator.send_message(session_id, user_text) -> frappe._dict`
  with `.assistant_turn.text`, `.user_turn.name`, `.assistant_turn.name`; persists both turns
  and publishes the realtime `simulation:turn_complete` event.
- Settings: `load_settings()` → `stt_enabled`, `tts_enabled`, `tts_voice`, `tts_autoplay_on_stt`.
  Client flags via `get_lms_settings` → `useSettings` store.
- Base64 helpers: backend `_decode_audio` (25 MB guard, `data:` prefix), frontend
  `blobToBase64` / `base64ToBytes` in `utils/audioApi.js`.

---

## Backend

### 1. Shared pipeline helper — `apps/os_lms/os_lms/os_lms/ai/audio/pipeline.py` (new)

```python
def run_audio_turn(
    *,
    audio: str | None,
    text: str | None,
    mime: str,
    language: str,
    produce_answer,          # Callable[[str], str]
    want_audio: bool,
) -> dict:
    """STT (if audio) -> produce_answer(question) -> TTS (if enabled). Pure of chat
    specifics: the caller supplies produce_answer. Returns
    {question_text, answer_text, audio_base64|None, mime|None}."""
```

Logic:
1. `settings = load_settings()`.
2. If `audio`: require `settings.stt_enabled` (else `PermissionError`); `raw = _decode_audio(audio)`;
   `question_text = resolve_audio_provider("stt").transcribe(raw, mime=mime or "audio/webm",
   language=language or None).text`. Else: `question_text = (text or "").strip()` (throw if empty).
3. `answer_text = produce_answer(question_text)`.
4. `audio_base64 = None; out_mime = None`. If `want_audio and settings.tts_enabled`:
   try `speech = resolve_audio_provider("tts").synthesize(answer_text,
   voice=settings.tts_voice or "alloy")`; `audio_base64 = base64.b64encode(speech.audio).decode()`;
   `out_mime = speech.mime`. On `AudioError` (any subclass): `frappe.log_error(...)` and leave audio
   `None` (graceful text-only degradation).
5. Return `{"question_text": question_text, "answer_text": answer_text,
   "audio_base64": audio_base64, "mime": out_mime}`.

STT errors propagate (mapped to user-facing throws in the endpoint, mirroring `audio/api.py`).
Move/extract `_decode_audio` + `MAX_AUDIO_BYTES` so both `audio/api.py` and `pipeline.py` share
them (import from a common location; do not duplicate).

### 2. Tutor endpoint — `ai/tutor/api.py::ask_audio`

```python
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
    if isinstance(history, str):
        history = json.loads(history)
    user = frappe.session.user
    return run_audio_turn(
        audio=audio, text=question, mime=mime, language=language, want_audio=want_audio,
        produce_answer=lambda q: TutorAi(course, lesson or None, user).ask(q, history or []),
    )
```
Returns `{question_text, answer_text, audio_base64, mime}`.

### 3. Simulation endpoint — `ai/simulations/api.py::send_message_audio`

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
    session = load_session(session_id)
    if session.student != frappe.session.user:
        frappe.throw(_("Only the session owner can send messages"), frappe.PermissionError)
    holder = {}
    def produce(q: str) -> str:
        r = _service().send_message(session_id=session.name, user_text=q)
        holder["user_turn"] = r.user_turn.name
        holder["assistant_turn"] = r.assistant_turn.name
        holder["injection_attempt"] = bool(r.injection_attempt)
        return r.assistant_turn.text
    try:
        result = run_audio_turn(audio=audio, text=text, mime=mime, language=language,
                                want_audio=want_audio, produce_answer=produce)
    except SessionTerminatedError:
        frappe.throw(_("This session is no longer accepting messages"), frappe.ValidationError)
    return {**result, **holder}
```
Returns `{question_text, answer_text, audio_base64, mime, user_turn, assistant_turn,
injection_attempt}`. Turn persistence + realtime event are unchanged (inside
`orchestrator.send_message`).

---

## Frontend

### 4. `composables/useSpeechToText.js`

Add an `onAudio` option. In `onStop`, if `onAudio` is provided, call `onAudio(blob)` and
**skip** the internal `transcribeAudio` call; otherwise keep the current `onTranscript` behavior.
Public API and existing callers unchanged.

### 5. `components/ai/MicButton.vue`

Add a `raw: Boolean` prop (default `false`). When `raw`, pass `onAudio` to `useSpeechToText`
and emit `@audio` (the Blob); when not `raw`, keep emitting `@transcript`. Both chats use
`<MicButton raw @audio="…" />`.

### 6. `composables/useTextToSpeech.js`

Add `prime(text, base64, mime)`: build a Blob/object URL from the base64 payload and insert it
into the existing text→URL cache keyed by `text`, so a subsequent `play(text, id)` (and the
`SpeakButton`, which plays by the same `text`) reuse it without calling `synthesize` again.

### 7. `utils/audioApi.js`

Add thin callers for the two combined endpoints (posting `{audio?/text?, mime, language,
want_audio, …context}`) returning the parsed `{question_text, answer_text, audio_base64, mime,
…}`. Reuse `blobToBase64` for audio input and `base64ToBytes` for priming.

### 8. Tutor — `components/ai/ChatBot.vue`

- Mic in `raw` mode → on `@audio(blob)`: push an optimistic user message
  `{ role: 'user', audioPending: true }`, call `ask_audio` with the base64 audio + `history`;
  on response set that message's `content = question_text`, push
  `{ role: 'assistant', content: answer_text }`, and if `audio_base64`
  → `prime(answer_text, audio_base64, mime)` + `play(answer_text, id)`.
- Typed send: if `ttsEnabled` → call `ask_audio` with `question` (no audio, `want_audio: true`),
  same response handling; else keep the existing `ask` path.
- Template: a user bubble with `audioPending` renders an audio/mic icon + `…` (LoadingIndicator)
  instead of text.

### 9. Simulation — `components/simulations/ChatSession.vue` + `composables/useSimulationSession.js`

- Send routing (in the composable): if an audio Blob is present, or `ttsEnabled` for a typed
  message → call `send_message_audio`; else keep `send_message`.
- Mic in `raw` mode → optimistic user turn `{ role: 'user', _audioPending: true }` (no
  `text_content`); on response set it to `question_text`; then existing `load()` reconciles to
  the authoritative persisted turns. Mark the returned `assistant_turn` as already-seen so the
  autoplay watcher does not double-play; instead `prime(answer_text, audio_base64, mime)` +
  `play(answer_text, assistant_turn)` from the response.
- Template: a user bubble with `_audioPending` renders the audio icon + `…` instead of
  `text_content`.

### Client send-path decision (both sections)

| Input | Condition | Call |
|---|---|---|
| Voice (mic) | always (mic shown ⇒ `stt_enabled`) | combined (`audio`) |
| Typed | `tts_enabled` | combined (`text`, `want_audio: true`) |
| Typed | `!tts_enabled` | existing text endpoint |

---

## Error handling

- STT failure → user-facing error (mirrors `audio/api.py` mapping); the optimistic
  audio-pending bubble is removed / marked failed.
- LLM failure → existing chat-layer error handling (tutor/orchestrator).
- TTS failure → response returns text only (`audio_base64: null`); client shows the messages
  without audio. No hard failure.

## Testing

- Backend (mock audio + mock LLM/mock orchestrator providers):
  - `run_audio_turn`: audio-in happy path; text-in happy path; `stt_enabled=false` + audio →
    PermissionError; `tts_enabled=false` → `audio_base64 is None`; TTS raises `AudioError` →
    graceful `audio_base64 is None` + answer_text present.
  - `ask_audio`: audio path returns `{question_text, answer_text}`; text path.
  - `send_message_audio`: persists both turns (reuses orchestrator), returns `user_turn`/
    `assistant_turn`; owner gate; `SessionTerminatedError` mapping.
- Frontend: `cd frontend && yarn build` (no JS unit runner) + manual check of the
  pending-audio bubble and autoplay.

## Risks / notes

- Latency: the combined call now blocks for STT+LLM+TTS. The audio-pending bubble + the
  existing "sta rispondendo" indicator cover the wait.
- Double-play guard (simulation): the returned `assistant_turn` name must be recorded in the
  ChatSession autoplay watcher's `seenAssistantId` before/at reconciliation so the watcher
  doesn't re-play the server audio.
- `_decode_audio`/`MAX_AUDIO_BYTES` are currently module-private in `audio/api.py`; extract to a
  shared location for reuse by `pipeline.py` (no behavior change).
- Keeping the standalone `transcribe`/`synthesize` endpoints: still used by the per-message
  `SpeakButton` (read a past message) and by any non-combined path.
