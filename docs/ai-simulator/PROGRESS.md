# Simulazioni AI — Progress tracker

Documento operativo che traccia lo sviluppo reale della feature definita in [`PLAN-os_lms.md`](PLAN-os_lms.md). Va aggiornato a ogni step (PR mergiata, sprint chiuso, decisione presa).

> **Convenzione stato**: `⬜` da fare · `🚧` in corso · `✅` fatto · `⏸` bloccato · `❌` scartato.
>
> Ogni task chiuso linka la PR o il commit principale. Ogni task `🚧` indica chi sta lavorando e da quando.

---

## Stato attuale

- **Fase**: Pre-Sprint 1 — pianificazione conclusa, attesa conferma decisioni aperte.
- **Sprint corrente**: —
- **Prossimo milestone**: avvio Sprint 1 (LLM layer + foundation).
- **Owner principale**: —
- **Ultimo aggiornamento**: 2026-05-18

---

## Decisioni aperte (riferimento §11 di `PLAN-os_lms.md`)

| # | Decisione | Stato | Risolta il | Esito |
| --- | --- | --- | --- | --- |
| 1 | Regola SDK encapsulation (SDK consentito solo dentro adapter, extras opzionali, test CI) | ✅ | 2026-05-18 | Confermata dall'utente |
| 2 | Gemini via OpenAI-compat o REST nativo | ✅ | 2026-05-18 | **OpenAI-compat** come default (l'utente non ha specificato il transport ma chiede la versione più performante: `gemini-2.5-pro` come modello default, disponibile su entrambi gli endpoint — si parte da OpenAI-compat per coerenza, si passa a REST nativo solo se servono feature avanzate Google) |
| 3 | STT default fase 2 (`OpenAIWhisper` vs `Deepgram`) | ⬜ | — | — |
| 4 | TTS default fase 2 (`OpenAITTS` vs `ElevenLabs`) | ⬜ | — | — |
| 5 | Formato audio output (`mp3` vs `opus` vs `pcm16`) | ✅ | 2026-05-18 | **mp3** (rivedibile se in pilot emergono problemi di latenza/qualità) |
| 6 | VAD client-side (`@ricky0123/vad-web` vs solo push-to-talk) | ⬜ | — | — |
| 7 | Frappe File vs S3 per audio | ✅ | 2026-05-18 | **Frappe File** (max ~50 utenti concorrenti previsti — vedi nota capacità sotto) |
| 8 | Modello debrief default (`gpt-4.1` proposto) | ✅ | 2026-05-18 | **`gpt-4.1`** via OpenAI |
| 9 | Streaming (WS chat in MVP, TTS streaming in fase 2) | ⬜ | — | — |
| 10 | Pannello docente: SPA Vue vs Desk views | ✅ | 2026-05-18 | **SPA Vue obbligatoria** — Frappe Desk è riservato ai soli sysadmin, instructor non vi accedono |

### Vincoli derivati dalle decisioni

- **Default modelli `LMSA Settings`** (al momento dell'implementazione Sprint 1):
  - `simulation_chat_model` (OpenAI) → `gpt-4.1` o `gpt-4o` — modello da confermare al primo test reale
  - `simulation_debrief_model` (OpenAI) → **`gpt-4.1`**
  - Default modello Gemini → **`gemini-2.5-pro`** (versione più performante)
  - Default modello DeepSeek → `deepseek-chat`
  - Default modello Anthropic → `claude-sonnet-4-5` (chat) / `claude-opus-4-7` (se selezionato per debrief)
  - Tutti i valori sono configurabili da `LMSA Settings` senza redeploy.
- **Capacità target**: max ~50 utenti concorrenti. Decisione #7 (Frappe File) è coerente con questo target; rivedere a S3 solo se il numero cresce sostanzialmente o se i log mostrano contention su `tabFile` / I/O sul bench volume.
- **Audience del Desk**: solo sysadmin. Conseguenze concrete:
  - **Nessuna form Desk pensata per l'instructor**. CRUD scenario/rubrica/debrief avvengono **solo** dalla SPA Vue.
  - I doctype mantengono comunque list/form Desk funzionanti (necessari ai sysadmin per troubleshooting/audit), ma non sono nel flusso utente regolare.
  - Permessi: `LMS Instructor` mantiene CRUD via API REST, ma la UX di riferimento è esclusivamente Vue.
  - Health-check provider e "Test STT/TTS" restano action sul `LMSA Settings` Desk (uso sysadmin).

---

## Fase 1 — MVP testuale

### Sprint 1 — LLM layer + foundation (settimane 1-2)

Obiettivo: layer LLM provider-agnostico operativo + doctype Scenario/Rubric + Desk forms.

- ⬜ **LLM-1.1** — Skeleton modulo `os_lms/os_lms/ai/utils/llm/` (file vuoti: `provider.py`, `registry.py`, `config.py`, `errors.py`, `providers/__init__.py`)
- ⬜ **LLM-1.2** — `LLMProvider` ABC + dataclass (`ChatMessage`, `ChatResponse`, `ChatChunk`, `Usage`, `JsonSchema`, `ProviderConfig`)
- ⬜ **LLM-1.3** — Registry + factory `get_provider(config)` con decorator `@register("name")`
- ⬜ **LLM-1.4** — Errori normalizzati (`LLMRateLimit`, `LLMInvalidAuth`, `LLMContextWindow`, `LLMServerError`, `LLMTimeout`, `LLMUnsupported`, `ProviderSdkNotInstalled`)
- ⬜ **LLM-1.5** — `MockProvider` (deterministico, fingerprint messaggi) + `RecordingProvider` wrapper
- ⬜ **LLM-1.6** — `OpenAICompatibleProvider` base class (httpx, streaming SSE, JSON Schema, tool use)
- ⬜ **LLM-1.7** — `OpenAIProvider` adapter (decisione SDK vs httpx interna all'adapter)
- ⬜ **LLM-1.8** — `DeepSeekProvider` adapter (eredita da OpenAICompatibleProvider, solo override base_url)
- ⬜ **LLM-1.9** — `GeminiProvider` adapter (decisione: OpenAI-compat vs REST nativo — vedi decisione #2)
- ⬜ **LLM-1.10** — `AnthropicProvider` adapter
- ⬜ **LLM-1.11** — `resolve_provider(purpose, override)` + `build_provider_config(name, settings)`
- ⬜ **LLM-1.12** — Fallback chain in orchestrator (catch `LLMRateLimit`/`LLMServerError`, prova prossimo in `simulation_provider_fallback_order`)
- ⬜ **LLM-1.13** — `pyproject.toml`: blocco `[project.optional-dependencies]` con extras per-provider (`provider-openai`, `provider-anthropic`, `provider-gemini`, `all-providers`)
- ⬜ **LLM-1.14** — Test architetturale `test_provider_encapsulation.py` (CI fail su `import openai` fuori da `providers/`)
- ⬜ **LLM-1.15** — Unit test per ogni adapter con `httpx.MockTransport` o `monkeypatch` SDK
- ⬜ **SET-1.1** — Estensione doctype `LMSA Settings` (campi LLM: provider, fallback order, model chat/debrief, chiavi gemini/deepseek/anthropic, openai_base_url)
- ⬜ **SET-1.2** — Estensione dataclass `OsLmsSettings` + `_load_settings` per nuovi campi
- ⬜ **SET-1.3** — Migrazione `GptChatbot` come wrapper sopra `OpenAIProvider` (retro-compat tutor RAG, nessun call site cambia)
- ⬜ **SET-1.4** — Action in Desk `LMSA Settings`: "Test connessione" che invoca `provider.health_check()` per ogni provider configurato
- ⬜ **DT-1.1** — Doctype `LMSA Simulation Scenario` + child `LMSA Simulation Learning Objective` + child `LMSA Simulation Seed Variation`
- ⬜ **DT-1.2** — Doctype `LMSA Evaluation Rubric` + child `LMSA Rubric Criterion` (validazione somma pesi = 1.0)
- ⬜ **DT-1.3** — Permessi base + `permission_query_conditions` (instructor → propri corsi, manager full, student → Published)
- ⬜ **DT-1.4** — Fixture `custom_field.json` aggiornata (campo `simulations_enabled` su LMS Course)

**Definition of done Sprint 1**: `MockProvider` funziona end-to-end via `resolve_provider`; gli adapter reali rispondono al `health_check()`; doctype Scenario/Rubric creabili dal Desk dal docente.

### Sprint 2 — Sessioni testuali end-to-end (settimane 3-4)

Obiettivo: una sessione di chat completa funziona dal POST `start_session` fino all'`end_session`, con streaming.

- ⬜ **ORC-2.1** — Skeleton `os_lms/os_lms/ai/simulations/` (file vuoti)
- ⬜ **ORC-2.2** — `SessionOrchestrator` con lazy properties (`settings`, `logger`, `chatbot`) seguendo Service Pattern di `IngestionService`
- ⬜ **ORC-2.3** — `ScenarioGenerator` (Prompt 1) — JSON output con pydantic schema
- ⬜ **ORC-2.4** — `RolePlayPrompt` (Prompt 2) — costruzione system prompt da Scenario/persona
- ⬜ **ORC-2.5** — `prompt_defense.py` — regex anti-injection + fallback risposta in-character
- ⬜ **ORC-2.6** — Doctype `LMSA Simulation Session` (submittable) + permessi
- ⬜ **ORC-2.7** — Doctype `LMSA Simulation Turn` (document separato, `has_permission` che delega al parent)
- ⬜ **ORC-2.8** — `orchestrator.start_session(scenario_id, modality, seed)` — genera variante + primo turno cliente
- ⬜ **ORC-2.9** — `orchestrator.send_message(session_id, user_text)` — append turno + chiamata LLM + persist
- ⬜ **ORC-2.10** — `orchestrator.end_session(session_id, reason)` — stato + enqueue job debrief
- ⬜ **ORC-2.11** — Hook `before_insert` su Session: `validate_quota` (rate limit per studente)
- ⬜ **ORC-2.12** — Pseudonimizzazione: `_pseudonymize_session_id` (SHA-256 di `frappe.session.user`)
- ⬜ **API-2.1** — Endpoint REST whitelisted in `simulations/api.py`: `start_session`, `send_message`, `end_session`, `get_session`, `list_scenarios`
- ⬜ **API-2.2** — `load_session(session_id)` helper (analogo a `load_lesson` in `ai/api.py`)
- ⬜ **API-2.3** — Eventi `frappe.realtime`: `turn_start`, `turn_chunk`, `turn_complete`, `error` (con `layer`)
- ⬜ **API-2.4** — Streaming token-by-token nel `send_message` via WebSocket per-utente
- ⬜ **TST-2.1** — Unit test orchestrator con `MockProvider` (state machine, fallback, quota)
- ⬜ **TST-2.2** — Integration test endpoint con `frappe.tests` (permessi, payload)

**Definition of done Sprint 2**: `curl` POST a `start_session` + `send_message` produce un turno cliente coerente; WebSocket streamma token; quota giornaliera blocca al limite.

### Sprint 3 — Debrief + UI studente (settimane 5-6)

Obiettivo: lo studente vede il debrief dopo `end_session`. UI dalla lezione al debrief.

- ⬜ **DBR-3.1** — `DebriefEngine` (Prompt 3) — `pydantic` `DebriefSchema` con tutti i child types
- ⬜ **DBR-3.2** — Doctype `LMSA Simulation Debrief` + child (`LMSA Criterion Score`, `LMSA Debrief Strength`, `LMSA Debrief Improvement`, `LMSA Debrief Recommendation`)
- ⬜ **DBR-3.3** — Background job RQ `generate_debrief(session_id)` con retry su parse error
- ⬜ **DBR-3.4** — Riuso `RagDB.search()` per popolare `recommended_content` (lezioni rilevanti dal corso)
- ⬜ **DBR-3.5** — Evento `simulation:debrief_ready`
- ⬜ **DBR-3.6** — Endpoint `get_debrief` (polling fallback)
- ⬜ **FE-3.1** — Pagina `frontend/src/pages/Simulations/SimulationPlay.vue` + rotta `/simulations/:session_id`
- ⬜ **FE-3.2** — `frontend/src/oslms/components/simulations/SimulationLauncher.vue` (modale dalla lezione)
- ⬜ **FE-3.3** — `frontend/src/oslms/components/simulations/ChatSession.vue` (chat UI + streaming + counter turni/tempo)
- ⬜ **FE-3.4** — Composable `useSimulationSession(sessionId)` (socket + buffer streaming)
- ⬜ **FE-3.5** — Pagina `SimulationDebrief.vue` + rotta `/simulations/:session_id/debrief`
- ⬜ **FE-3.6** — Composable `useSimulationDebrief(sessionId)` (WS + polling fallback)
- ⬜ **FE-3.7** — Integrazione in `Lesson.vue` (bottone "Avvia simulazione" se `simulations_enabled`)
- ⬜ **FE-3.8** — Override `get_course_details` / `get_lesson` per esporre scenari pubblicati
- ⬜ **FE-3.9** — Settings expose `simulations_enabled` nel payload `get_lms_settings`
- ⬜ **TST-3.1** — Cypress E2E `cypress/e2e/simulations.cy.js` (happy path con `MockProvider`)

**Definition of done Sprint 3**: dalla lezione → click "Avvia" → chat → "Termina" → debrief visualizzato con punteggio e lezioni consigliate, tutto in <30s end-to-end con `MockProvider`.

### Sprint 4 — Pannello docente + pilot (settimane 7-8)

Obiettivo: il docente crea/modifica scenari e vede i report. Pilot su un corso reale.

- ⬜ **DOC-4.1** — `frontend/src/oslms/components/simulations/ScenarioEditor.vue` (form + preview con `test student`)
- ⬜ **DOC-4.2** — `frontend/src/oslms/components/simulations/RubricEditor.vue` (drag&drop pesi forzati a 1.0)
- ⬜ **DOC-4.3** — Endpoint `instructor_review_debrief`
- ⬜ **DOC-4.4** — Endpoint `instructor_report` (filtri corso/studente/periodo, aggregati)
- ⬜ **DOC-4.5** — Pagina `frontend/src/pages/Simulations/InstructorReports.vue` + rotta `/simulations/admin`
- ⬜ **DOC-4.6** — Drill-down trascrizione (riuso `ChatSession.vue` con `readOnly=true`)
- ⬜ **PIL-4.1** — Selezione corso pilot + 3-5 scenari curati
- ⬜ **PIL-4.2** — Sessione formativa docenti pilot (1h)
- ⬜ **PIL-4.3** — Onboarding 20-30 studenti pilot
- ⬜ **PIL-4.4** — Retrospettiva post-pilot (settimana 2 dopo lancio)

**Definition of done Sprint 4**: il docente del corso pilot crea scenari/rubriche dal SPA, vede le sessioni dei suoi studenti e legge i debrief con citazioni testuali.

---

## Fase 2 — Voce (post-MVP)

### Sprint 5 — STT layer (settimane 1-2 fase 2)

- ⬜ **STT-5.1** — Skeleton modulo `os_lms/os_lms/ai/utils/stt/` (provider.py, registry.py, config.py, errors.py, providers/)
- ⬜ **STT-5.2** — `STTProvider` ABC + dataclass (`TranscriptionResult`, `TranscriptionSegment`, `TranscriptionPartial`)
- ⬜ **STT-5.3** — Errori normalizzati (`STTRateLimit`, `STTInvalidAudio`, `STTUnsupportedLanguage`, `STTUnsupportedMimeType`, `STTAudioTooLong`, `STTServerError`, `STTTimeout`, `STTStreamingNotSupported`)
- ⬜ **STT-5.4** — `MockSTT` deterministico
- ⬜ **STT-5.5** — `OpenAIWhisper` adapter
- ⬜ **STT-5.6** — `Deepgram` adapter (streaming-capable)
- ⬜ **STT-5.7** — `GoogleSTT` adapter (UE region)
- ⬜ **STT-5.8** — Extras `[project.optional-dependencies]`: `provider-deepgram`, `provider-google-cloud`
- ⬜ **STT-5.9** — `resolve_stt_provider(override)` + `build_stt_config(name, settings)`
- ⬜ **STT-5.10** — Estensione `LMSA Settings`: campi STT + chiavi (`deepgram_key`, `google_stt_credentials_json`, `azure_speech_key/region`, `elevenlabs_key`)
- ⬜ **STT-5.11** — Endpoint `test_stt_audio` + Desk action "Test STT" su `LMSA Settings`
- ⬜ **STT-5.12** — Unit test adapter (mock HTTP/SDK, fixtures audio reali piccole)

### Sprint 6 — TTS layer (settimane 3-4 fase 2)

- ⬜ **TTS-6.1** — Skeleton modulo `os_lms/os_lms/ai/utils/tts/`
- ⬜ **TTS-6.2** — `TTSProvider` ABC + dataclass (`SynthesisRequest`, `SynthesisResult`, `AudioChunk`, `Voice`)
- ⬜ **TTS-6.3** — Errori normalizzati (`TTSRateLimit`, `TTSInvalidVoice`, `TTSUnsupportedLanguage`, `TTSUnsupportedFormat`, `TTSTextTooLong`, `TTSServerError`, `TTSTimeout`)
- ⬜ **TTS-6.4** — `MockTTS` deterministico
- ⬜ **TTS-6.5** — `OpenAITTS` adapter (streaming response)
- ⬜ **TTS-6.6** — `ElevenLabsTTS` adapter (streaming SSE, voice cloning)
- ⬜ **TTS-6.7** — `GoogleTTS` adapter
- ⬜ **TTS-6.8** — `DeepgramAura` adapter
- ⬜ **TTS-6.9** — Cache primo turno (Frappe Cache key `tts:{provider}:{voice}:{hash(text)}`, TTL 7gg)
- ⬜ **TTS-6.10** — Estensione `LMSA Settings`: campi TTS + voice default + formato + speaking rate + cache toggle
- ⬜ **TTS-6.11** — Endpoint `list_tts_voices` + `preview_tts_voice`
- ⬜ **TTS-6.12** — Unit test adapter

### Sprint 7 — Voice orchestrator + consenso (settimane 5-6 fase 2)

- ⬜ **VOI-7.1** — `voice_orchestrator.handle_audio_turn` (STT → LLM → TTS streaming)
- ⬜ **VOI-7.2** — Endpoint `send_audio` (multipart upload + dispatch)
- ⬜ **VOI-7.3** — Doctype `LMSA Recording Consent Log` (append-only, IP/UA da request)
- ⬜ **VOI-7.4** — Endpoint `grant_recording_consent` + `revoke_recording_consent` (con purge audio attuale)
- ⬜ **VOI-7.5** — Aggiunta campi audio a `LMSA Simulation Turn` (audio_file, format, duration_ms, stt_segments, latenze, voice_id, provider used)
- ⬜ **VOI-7.6** — Aggiunta campi voce a `LMSA Simulation Scenario` (`stt_provider_override`, `tts_provider_override`, `customer_voice_id/language/speaking_rate`)
- ⬜ **VOI-7.7** — Aggiunta campi a `LMSA Simulation Session` (consent_recording, audio_retention_until)
- ⬜ **VOI-7.8** — Cron `purge_expired_audio` (daily) + `cascade_delete_turns_and_audio` (on_trash Session)
- ⬜ **VOI-7.9** — Eventi WS `simulation:stt_complete`, `simulation:audio_chunk` (con `is_final`)
- ⬜ **VOI-7.10** — Voice integration test end-to-end (Mock STT + Mock LLM + Mock TTS)

### Sprint 8 — Frontend voce + pilot (settimane 7-8 fase 2)

- ⬜ **FEV-8.1** — `frontend/src/oslms/components/simulations/VoiceSession.vue` (MediaRecorder + push-to-talk)
- ⬜ **FEV-8.2** — Integrazione VAD client-side (se decisione #6 = `@ricky0123/vad-web`)
- ⬜ **FEV-8.3** — `frontend/src/oslms/components/simulations/ConsentModal.vue` (3 toggle granulari)
- ⬜ **FEV-8.4** — Riproduzione audio chunk via Web Audio API (concatenazione streaming)
- ⬜ **FEV-8.5** — Trascrizione live (sia user che assistant) + toggle "Solo voce"
- ⬜ **FEV-8.6** — Estensione `ScenarioEditor`: dropdown voci (popolato da `list_tts_voices`) + bottone preview
- ⬜ **FEV-8.7** — Cypress E2E `cypress/e2e/simulations_voice.cy.js` (fixture audio + mock provider)
- ⬜ **FEV-8.8** — Pilot voce su 5-10 studenti con 1 scenario "golden"
- ⬜ **FEV-8.9** — Misurazione latenza reale (TTFB STT, TTFB TTS) e ottimizzazioni

---

## Fase 3 — Avanzato (post pilot)

- ⬜ **F3-1** — Streaming STT vero (`STTProvider.transcribe_stream` su Deepgram/Google) + evento `simulation:stt_partial`
- ⬜ **F3-2** — `OpenAIRealtimeProvider` come adapter unificato (soddisfa contemporaneamente LLM+STT+TTS per il path voce-voce)
- ⬜ **F3-3** — Coach AI on-demand durante simulazione (con penalità score)
- ⬜ **F3-4** — Adaptive difficulty (lo scenario si adatta in tempo reale alle performance)
- ⬜ **F3-5** — Voice cloning ElevenLabs per persone ricorrenti (con consenso istituzionale)
- ⬜ **F3-6** — Benchmark anonimo studente vs coorte
- ⬜ **F3-7** — Integrazione CRM (logging best practice come case study reali)

---

## Cross-cutting / continuo

- ⬜ **DOC-X.1** — Aggiornare `apps/os_lms/CLAUDE.md` con sezione "Simulazioni" appena Sprint 1 mergiato
- ⬜ **DOC-X.2** — Aggiornare `CLAUDE.md` root con cenni a `os_lms.ai.simulations` quando l'API è stabile
- ⬜ **OPS-X.1** — Monitoring costi LLM/STT/TTS (dashboard aggregata `LMSA Simulation Turn` con `tokens_input/output`, `audio_duration_ms`)
- ⬜ **OPS-X.2** — Alert su tasso `injection_attempt_detected` > soglia
- ⬜ **OPS-X.3** — DPIA con DPO prima del lancio pubblico fase 2

---

## Changelog

> Una riga per cambiamento significativo. Formato: `YYYY-MM-DD — autore — descrizione`.

- 2026-05-18 — pianificazione — creato `PLAN-os_lms.md` (adattamento per modulo `os_lms`)
- 2026-05-18 — pianificazione — esteso piano con layer LLM provider-agnostico (§3.3)
- 2026-05-18 — pianificazione — esteso piano per fase 2 con layer STT (§3.4) e TTS (§3.5)
- 2026-05-18 — decisione — confermata regola SDK encapsulation (§3.3.1, decisione #1)
- 2026-05-18 — pianificazione — creato `PROGRESS.md` (questo file)
- 2026-05-18 — decisione — confermata #10: pannello docente in **SPA Vue** (Desk solo sysadmin)
- 2026-05-18 — decisione — confermata #7: audio su **Frappe File** (target ~50 utenti concorrenti)
- 2026-05-18 — decisione — confermata #5: formato audio output **mp3**
- 2026-05-18 — decisione — confermata #8: modello debrief default **`gpt-4.1`**
- 2026-05-18 — decisione — confermata #2: Gemini via **OpenAI-compat**, modello default **`gemini-2.5-pro`** (versione più performante)
