# Realtime Voice Simulations — Design Spec

> Status: design approved, ready for implementation planning.
> Date: 2026-06-30.
> Supersedes the open decisions in `docs/ai-coach-realtime/1 REALTIME_ARCHITECTURE.md`
> and confirms the recommendation in `docs/ai-coach-realtime/2 REALTIME_PROVIDER_COMPARISON.md`.

## 1. Goal

Add a **voice-to-voice, real-time** modality to the existing AI simulations (e.g. job
interview role-play), as an alternative to the current turn-based text chat. The AI must
**perceive** the candidate's tone, hesitation, rhythm and confidence — which requires a
native **speech-to-speech** model (OpenAI Realtime / Gemini Live), not a chained STT→LLM→TTS
pipeline.

The feature must work from both the **web SPA** (Vue, browser) and the **Flutter mobile app**
(Android/iOS). The Flutter app lives in a separate repository and is out of scope here; the
backend endpoints are designed to be consumed identically by both clients.

## 2. Scope (this iteration)

In scope (repo `elite-lms`):

- Provider-agnostic **realtime abstraction** (`ai/utils/realtime/`): ABC + registry + config + errors.
- Concrete adapters: **OpenAI Realtime**, **Gemini Live**, and a deterministic **mock**.
- **Control-plane feature layer** (`ai/realtime/api.py`): whitelisted endpoints.
- **Web client** (Vue): transport-agnostic composable + `VoiceSession.vue`.
- Additive **doctype / settings** fields.

Out of scope (this iteration):

- The **Flutter client** (separate repo; consumes the same endpoints).
- **Raw audio capture / retention** and the soft-skill "delivery" judge (additive, future).
- **Server-side authoritative transcript relay** (high-stakes exam trust model).

## 3. Key decisions

| Decision | Choice | Rationale |
|---|---|---|
| Mobile app stack | Flutter (separate repo) | Same control-plane HTTP endpoints; only the WebRTC/WS client differs per platform. |
| Work boundary | Backend control plane + web client | Flutter consumes the same API later. |
| Trust model | Practice — client relays transcript (model A) | Direct client↔provider audio, low latency. Acceptable for practice, not for high-stakes exams. |
| Providers | OpenAI Realtime + Gemini Live + mock | Provider-agnostic by policy; both adapters from the start, complexity isolated per adapter. |
| Audio retention | None — transcript-only | Privacy-friendly MVP; debrief reuses the existing text pipeline. |
| Default | OpenAI `gpt-realtime-2`, WebRTC | GA, 60-min session (no resumption), transcript events map 1:1 to existing `_persist_turn`. |

## 4. Architecture

### 4.1 Principle

Frappe stays the **control plane**, never the **data plane**. Audio always travels **directly
client↔provider**. Frappe handles only: gating (enabled / published / quota), persona
generation (text, reusing the existing pipeline), ephemeral token minting, transcript
persistence, and the debrief job.

### 4.2 Unified topology (web + Flutter)

```
                  (1) start_voice_session                      (3) direct audio stream
  Client      ──────────────────────────────►  Frappe   ─ ─ ─ (ephemeral token) ─ ─ ─►  Provider
 web / Flutter ◄──────────────────────────────  (control)                              OpenAI Realtime (WebRTC)
   │  mic/spk      { session_id, transport,                                            Gemini Live  (WebSocket)
   │               connect_url, client_secret,
   │               voice, model, expires_at,
   │               max_seconds }
   │
   │  (4) persist_transcript_turn(session_id, role, text, ts)   [whitelisted]
   └──────────────────────────────────────────►  Frappe  ──►  LMSA Simulation Turn
                                                    │
                            (5) end_voice_session ──┴──►  submit + enqueue debrief (reused)
```

Rationale: Frappe (request/response workers) is unsuited to long-lived bidirectional audio
relay. Direct WebRTC/WS gives conversational latency; the backend is the control plane, not
the data plane.

### 4.3 Two-transport strategy (key approach choice)

OpenAI uses **WebRTC**, Gemini uses **WebSocket** (`BidiGenerateContent`). To avoid scattering
`if provider == ...` across the client, the backend returns a **neutral transport descriptor**
and the client selects a strategy:

- `RealtimeSession.transport` ∈ `{"webrtc", "websocket"}`.
- `connect_url`, `client_secret`, and `extra` (opaque provider-specific fields for the client,
  e.g. Gemini session-resumption handle).
- Web: a `RealtimeTransport` interface with two implementations (`WebrtcTransport`,
  `WebsocketTransport`); `useRealtimeSession` is transport-agnostic.
- The same payload shape is consumed by Flutter later (one `RealtimeTransport` per platform).

The OpenAI/Gemini divergence is isolated to exactly one place on each side (Python adapter,
client strategy), consistent with the ABC+registry pattern already used in `utils/llm` and
`utils/audio`.

## 5. New components

### 5.1 Backend — realtime abstraction (new)

```
apps/os_lms/os_lms/os_lms/ai/utils/realtime/
├── __init__.py        # resolve_realtime_provider(), build_realtime_config(), re-export types/errors
├── provider.py        # RealtimeProvider (ABC) + RealtimeSession, RealtimeSessionConfig, TranscriptEvent
├── config.py          # RealtimeProviderConfig (api_key, default_model, voice, turn_detection, ...)
├── registry.py        # @register_realtime, get_realtime_provider, list_realtime_providers
├── errors.py          # RealtimeError, RealtimeUnsupported, RealtimeInvalidAuth, RealtimeRateLimit, ...
└── providers/
    ├── __init__.py        # side-effect registration (import openai_realtime, gemini_live, mock)
    ├── openai_realtime.py # POST /v1/realtime/client_secrets → ephemeral client secret; transport="webrtc"
    ├── gemini_live.py     # auth_tokens.create (ephemeral) → transport="websocket"; resumption in `extra`
    └── mock.py            # deterministic, no network (tests)
```

ABC contract (pure where possible, testable without network):

```python
@dataclass
class RealtimeSession:
    provider: str
    model: str
    transport: str            # "webrtc" | "websocket"
    client_secret: str        # ephemeral token for the client (never the api key)
    connect_url: str
    expires_at: int
    voice: str
    extra: dict               # provider-specific fields the client needs (opaque)

class RealtimeProvider(ABC):
    name: str = ""
    def create_session(self, cfg: RealtimeSessionConfig) -> RealtimeSession: ...   # mints ephemeral token
    def parse_transcript_event(self, event: dict) -> TranscriptEvent | None: ...    # normalize → (role, text, final)
    def health_check(self) -> bool: ...
```

`parse_transcript_event` is pure → unit-testable with recorded events from both providers,
no SDK. `create_session` is the only network point (mockable via `requests`/SDK).

### 5.2 Backend — control-plane feature layer (new)

```
apps/os_lms/os_lms/os_lms/ai/realtime/
├── __init__.py
└── api.py   # create_voice_session(), persist_transcript_turn(), end_voice_session()
```

Thin shell like `simulations/api.py`: validate inputs, gate permissions/quota, delegate to
`SessionOrchestrator`, return plain dicts. **Reuses** `SessionOrchestrator._persist_turn`,
`validate_quota`, `pseudonymize_session_id`, `ScenarioVariantGenerator`,
`build_role_play_system_prompt`, and the existing debrief job.

### 5.3 Frontend web (custom, no Vite override)

```
frontend/src/oslms/
├── composables/
│   ├── useRealtimeSession.js     # lifecycle: start → connect(transport) → transcript events → stop
│   └── realtime/
│       ├── RealtimeTransport.js  # common interface (connect, onTranscript, onState, close)
│       ├── WebrtcTransport.js    # RTCPeerConnection + data channel (OpenAI)
│       └── WebsocketTransport.js # WSS BidiGenerateContent + resumption (Gemini)
└── components/simulations/
    └── VoiceSession.vue          # UI: connection state, audio level, live transcript, timer, stop
```

Hooks onto the `modality="voice"` value already supported on Scenario/Session.

### 5.4 Encapsulation boundary (extend existing test)

`test_provider_encapsulation.py` currently forbids `import openai/anthropic/google.genai/...`
outside `utils/{llm,stt,tts}/providers/`. It **must be extended** to admit realtime SDKs only
under `utils/realtime/providers/`.

## 6. End-to-end flow

```
create_voice_session(scenario_id)                         [whitelisted]
  ├─ gate: simulations_enabled + realtime_enabled + scenario Published + modality∈{voice,both} + validate_quota
  ├─ ScenarioVariantGenerator.generate(seed)              # persona+situation — TEXT LLM (reused, unchanged)
  ├─ create LMSA Simulation Session (modality="voice", generated_persona=...)
  ├─ instructions = build_role_play_system_prompt(persona, situation, difficulty)   # reused
  ├─ provider = resolve_realtime_provider(scenario.provider_override)
  ├─ cfg = build_realtime_config(instructions, voice, turn_detection, input_transcription, max_seconds)
  └─ session = provider.create_session(cfg)               # ephemeral token (api key stays on server)
     return { session_id, transport, connect_url, client_secret, voice, model, expires_at, max_seconds }

CLIENT (useRealtimeSession.js)
  ├─ getUserMedia(mic) → select Transport by `transport` → connect with client_secret
  ├─ real-time voice conversation (barge-in, prosody) — audio NEVER touches Frappe
  ├─ on each FINAL transcript event → persist_transcript_turn(session_id, role, text, ts)
  └─ at max_seconds (client timer) or user stop → end_voice_session

persist_transcript_turn(...)                              [whitelisted]
  └─ _persist_turn (reused) + publish_realtime (live UI)  # filters non-final deltas

end_voice_session(session_id, reason)                     [whitelisted]
  ├─ status=completed/abandoned, ended_at, session_seconds, submit() (immutable)
  └─ enqueue generate_debrief  ← SAME text pipeline as chat
```

The debrief runs **identically** on the text Turns. The soft-skill "delivery" judge stays
**additive and out of MVP**.

## 7. Session duration & closing (currently missing)

`time_limit_minutes` / `max_turns` exist on the Scenario but are **not enforced**. For voice,
where billing is per-minute, we need:

- **`realtime_max_session_seconds`** (Settings, default e.g. 900s), with optional Scenario override.
- Enforcement at **two levels**: a **client** timer (UX: countdown, clean close) plus a
  **server** guard in `persist_transcript_turn` / `end_voice_session` (if
  `now - started_at > max` ⇒ force termination). No long-lived process on Frappe.
- Portable "natural close" pattern (post-MVP, optional): at T-N the client injects a wrap-up
  directive into the live session (`session.update` / `response.create` for OpenAI; a content
  turn for Gemini).

## 8. Doctype / settings changes (all additive)

**LMSA Settings** — new "Realtime / Voice" section:
`realtime_enabled`, `realtime_provider` (`openai`|`gemini`), `realtime_model`,
`realtime_voice`, `turn_detection` (`server_vad`|`semantic_vad`),
`realtime_max_session_seconds`. The **api keys** reuse the existing per-provider encrypted fields.

**LMSA Simulation Scenario** (optional): `voice` (voice override), `voice_instructions`
(acting style). `modality` / `provider_override` already present.

**LMSA Simulation Session** (audit): `realtime_provider_used`, `realtime_model_used`,
`voice_used`, `session_seconds`. `modality="voice"` already supported.

## 9. Provider notes

- **OpenAI**: default `gpt-realtime-2`, WebRTC, 60-min session (15 min fits comfortably → no
  resumption). Events `conversation.item.input_audio_transcription.completed` (user) and
  `response.output_audio_transcript.done` (assistant) → mapped 1:1 to `_persist_turn`. Input
  transcription enabled with `gpt-4o-transcribe`/`whisper-1`, `language:"it"`.
- **Gemini**: WebSocket, connection drops at ~10 min → **session resumption mandatory**
  (handle carried in `extra`); `system_instruction` fixed at connect (closing steering goes
  via a content turn, not by rewriting the persona). Production default on **Vertex** (GA,
  service-account auth); AI Studio is Preview. Behind a flag, OpenAI is default.

## 10. Testing strategy

(Applies `python-testing-patterns`.)

- **Pure unit (no network, no frappe)**: `parse_transcript_event` for OpenAI and Gemini over
  recorded event fixtures (real JSON) → verify `(role, text, final)` mapping and non-final
  delta filtering. `build_realtime_config` → persona/voice/turn_detection land in the right fields.
- **Adapters with mocked network**: `create_session` with mocked `requests`/SDK → verify the
  api key never leaks, that `client_secret`/`transport`/`connect_url` are correct, and provider
  errors map to `RealtimeError*`.
- **Mock provider (deterministic)**: exercise the feature layer
  (`create_voice_session` → `persist_transcript_turn` → `end_voice_session`) without network:
  gating, quota, turn persistence, submit, debrief enqueue.
- **Architectural test**: extend `test_provider_encapsulation.py` to admit realtime SDKs only
  under `utils/realtime/providers/`.
- **Frontend**: `Transport`s are testable by isolating `RTCPeerConnection`/`WebSocket` behind
  the interface; `useRealtimeSession` tested with a fake transport.

## 11. Implementation phases

Each phase green before the next.

1. **Abstraction** `utils/realtime/` (ABC + config + registry + errors + **mock**) — testable without network.
2. **OpenAI adapter** (`create_session` ephemeral + `parse_transcript_event`) + unit/integration tests.
3. **Feature layer** `ai/realtime/api.py` — reuses `SessionOrchestrator`. Server-side duration enforcement.
4. **Settings + Scenario fields** (Realtime section, voice/voice_instructions) + i18n + Session audit fields.
5. **Web frontend**: `RealtimeTransport` + `WebrtcTransport` + `useRealtimeSession` + `VoiceSession.vue`
   (timer, live transcript, state). MVP on OpenAI.
6. **Gemini Live adapter** + `WebsocketTransport` (resumption) — behind a flag.
7. *(post-MVP, additive)* "delivery" soft-skill judge via realtime-model self-evaluation.

The Flutter app consumes the same endpoints from phase 3 → separate deliverable (other repo),
not part of these phases.

## 12. Risks & informed decisions

- **No streaming failover**: unlike `chat_with_fallback`, a live session cannot fail over
  mid-stream → the provider is **fixed at start**. Selection/validation happens in
  `create_voice_session`.
- **Per-minute cost**: mitigated by `realtime_max_session_seconds` + the reused daily quota +
  `session_seconds` tracked for reporting.
- **Trust model A**: client relays the transcript → suited to *practice*, not high-stakes exams
  (made explicit in this spec).
- **Gemini Preview / resumption**: complexity isolated in the adapter + `WebsocketTransport`;
  OpenAI stays the default, lower-risk path.
- **WebView / mic permissions** (relevant for Flutter later): out of scope now, but the neutral
  payload is designed to avoid rewrites.

## 13. Reuse summary (zero rewrite of existing simulation infra)

| Existing component | Reuse in voice mode |
|---|---|
| LMSA Simulation Scenario (persona, situation, objectives, difficulty, evaluation_schema, provider_override) | Identical; the recruiter persona originates here. |
| ScenarioVariantGenerator (`role_player.py`) | Identical; generates concrete persona+situation from seed before opening the live session. |
| `build_role_play_system_prompt` (`prompts/role_play.py`) | Reused as the realtime session `instructions`. |
| LMSA Simulation Session / Turn | Identical; turns persisted from the realtime transcripts. |
| Debrief job (`tasks.py` → `eval/judges/`) | Reused; works on text Turns. |
| `chat_with_fallback` / `utils/llm` | Reused for variant generation and debrief (stay text). |
| `modality` on Session (default `"chat"`) | New value `"voice"` discriminates the flow. |
| `pseudonymize_session_id` | Reused; session id sent to the provider stays pseudonymized. |
| `validate_quota` (before_insert hook) | Reused; same daily quota for voice sessions. |
