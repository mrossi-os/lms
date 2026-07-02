# STT/TTS in the simulation chat (mirror the tutor)

**Date:** 2026-07-02
**Status:** Approved design, pending implementation
**Area:** `frontend/src/oslms` (frontend only)

## Problem

The AI tutor chat (`ChatBot.vue`) supports speech-to-text (a mic record button) and
text-to-speech (reading assistant messages aloud). The simulation **chat** modality
(`ChatSession.vue`) has neither. Students should be able to dictate messages and hear
the AI role-player's replies in simulations too, using the same controls and the same
settings flags as the tutor.

## Goals

1. In the simulation chat, show a mic (STT) button and a per-message read (TTS) button,
   reusing the tutor's existing components.
2. Gate visibility on the existing flags: mic only when `stt_enabled`, read/autoplay
   only when `tts_enabled` (autoplay additionally requires `tts_autoplay_on_stt`).
3. Reproduce the tutor's autoplay behavior: when the student dictated the message and
   `tts_autoplay_on_stt` is on, auto-read the AI reply.
4. Rename the admin settings section label `"Audio nel tutor"` to a generic label, since
   the audio settings now apply to both the tutor and simulations.

## Non-goals

- No new backend endpoints, doctype fields, or composables — the audio stack is already
  feature-agnostic and student-accessible.
- No changes to the voice (realtime speech-to-speech) simulation modality.

## Existing infrastructure reused (no changes)

- Composables: `useSpeechToText` (mic lifecycle, `onTranscript` callback) and
  `useTextToSpeech` (`play`, `prefetch`, `stop`, `isLoading`, singleton audio + cache).
- Components: `frontend/src/oslms/components/ai/MicButton.vue` (props `{disabled, language}`,
  emits `transcript`, self-hides when unsupported) and
  `frontend/src/oslms/components/ai/SpeakButton.vue` (props `{text, id, voice}`).
- HTTP: `frontend/src/oslms/utils/audioApi.js` → whitelisted `os_lms...ai.audio.api.transcribe`
  / `synthesize` (both gate on the settings flags server-side; available to logged-in students).
- Flags reach the client via the overridden `get_lms_settings`
  (`apps/os_lms/os_lms/os_lms/override_api.py`), which surfaces `stt_enabled`, `tts_enabled`,
  `tts_autoplay_on_stt`, consumed through the Pinia `useSettings` store as
  `settingsStore.settings?.data?.*`.

## Changes

### 1. `frontend/src/oslms/utils/settings.js`

Rename the section label `__('Audio nel tutor')` → `__('Audio (dettatura e lettura vocale)')`.
The section's fields (`stt_enabled`, `stt_provider`, `stt_model`, `tts_enabled`,
`tts_provider`, `tts_model`, `tts_voice`, `tts_autoplay_on_stt`) are unchanged.

### 2. `frontend/src/oslms/components/simulations/ChatSession.vue`

Mirror `ChatBot.vue`:

- Imports: `useSettings` from `@/stores/settings`; `MicButton` and `SpeakButton` from
  `@/oslms/components/ai/`; `useTextToSpeech` from `@/oslms/composables/useTextToSpeech`.
- Computeds (off `settingsStore.settings?.data`): `sttEnabled`, `ttsEnabled`,
  `ttsAutoplayOnStt`. Destructure `{ play, prefetch }` from `useTextToSpeech()`.
- Local state: `pendingVoice` ref (default `false`).
- **STT:** in the input flex row, `<MicButton v-if="sttEnabled" :disabled="sending"
  @transcript="onTranscript" />`. `onTranscript(text)` sets `draft = text` and
  `pendingVoice = true`. (The input row is already `v-if="!readOnly && !isTerminal"`, so
  the mic never appears on read-only/terminal sessions.)
- **TTS (manual):** inside each character bubble (`turn.role !== 'user'`),
  `<SpeakButton v-if="ttsEnabled" :text="turn.text_content" :id="turn.name || turn.turn_index" />`.
- **TTS (autoplay):** extend the existing `watch` on the `turns` prop (or add one). Track the
  last-seen turn count. When `turns` grows and the newest turn is an assistant/character turn
  (`role !== 'user'` and not `system`): if `pendingVoice && ttsAutoplayOnStt` →
  `play(turn.text_content, turn.name || turn.turn_index)`; else if `ttsEnabled` →
  `prefetch(turn.text_content)`. Then set `pendingVoice = false`.

## Behavior / gating summary

| Control | Shown when |
|---|---|
| Mic button (dictate) | `stt_enabled` (and not read-only/terminal) |
| Read button per AI message | `tts_enabled` |
| Autoplay AI reply after dictation | `tts_enabled && tts_autoplay_on_stt && pendingVoice` |

## Testing

Frontend has no JS unit runner; verify with `cd frontend && yarn build` (exit 0) and a manual
check. No backend changes, so no backend tests.

## Risks / notes

- The parent (`useSimulationSession` / `SimulationPlay.vue`) owns the send/response cycle and
  delivers replies via the `turns` prop; autoplay is therefore driven by a `turns` watcher in
  `ChatSession.vue` rather than an inline response handler (as in the tutor). This is the only
  structural difference from the tutor.
- Reusing the shared `useTextToSpeech` singleton means playback state is shared with the tutor
  (only one audio plays at a time) — acceptable and consistent.
