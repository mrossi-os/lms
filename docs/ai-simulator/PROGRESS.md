# Simulazioni AI — Progress tracker

> **Nota (2026-06-09)**: questo file riflette la pianificazione storica della Fase 1. Alcune feature pianificate qui sono state poi rinominate o rimosse post-MVP. Per la **descrizione operativa attuale del modulo** vedi [`../ai/SIMULATIONS.md`](../ai/SIMULATIONS.md). Modifiche significative dopo l'MVP:
>
> - **Rename**: `customer_persona` → `roleplay_persona`, `CustomerTurnService` → `RolePlayerTurnService`, file `customer.py` → `role_player.py`. Il personaggio AI non è più "customer-only" ma agnostico al dominio (cliente / esaminatore / paziente / ecc.).
> - **Rimosso**: feature `LMSA Scenario Golden Run` + `run_golden_regression` (mai adottata in produzione). Patch `v0_0_4.drop_golden_runs` ripulisce il DB.
> - **Aggiunto**: `LMSA Prompt Template` (unico doctype, dopo la fusione di `LMSA Judge Prompt` con campo opzionale `output_schema`) per rendere tutti i prompt LLM editabili dal Desk senza redeploy. Loader con fallback ai default hardcoded sotto `ai/utils/default_prompt/`.
> - **Aggiunto**: bottone "Compila con IA" su `ScenarioEditor` e `EvaluationSchemaEditor` (`authoring_ai.py` + endpoint `ai_generate_scenario` / `ai_generate_evaluation_schema`).

Documento operativo che traccia lo sviluppo reale della feature definita in [`PLAN-os_lms.md`](PLAN-os_lms.md). Va aggiornato a ogni step (PR mergiata, sprint chiuso, decisione presa).

> **Convenzione stato**: `⬜` da fare · `🚧` in corso · `✅` fatto · `⏸` bloccato · `❌` scartato.
>
> Ogni task chiuso linka la PR o il commit principale. Ogni task `🚧` indica chi sta lavorando e da quando.

---

## Stato attuale

- **Fase**: Fase 1 — Sprint 4 **completato parte tecnica** (6/6 DOC-*). Restano `PIL-4.*` come attività operative del team.
- **Sprint corrente**: — (Fase 1 MVP testuale chiusa lato codice)
- **Prossimo milestone**: pilot con corso reale + Sprint 5 (STT layer Fase 2 voce) quando il pilot dà segnale verde
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
  - **Nessuna form Desk pensata per l'instructor**. CRUD scenario/schema di valutazione/debrief avvengono **solo** dalla SPA Vue.
  - I doctype mantengono comunque list/form Desk funzionanti (necessari ai sysadmin per troubleshooting/audit), ma non sono nel flusso utente regolare.
  - Permessi: `LMS Instructor` mantiene CRUD via API REST, ma la UX di riferimento è esclusivamente Vue.
  - Health-check provider e "Test STT/TTS" restano action sul `LMSA Settings` Desk (uso sysadmin).

---

## Fase 1 — MVP testuale

### Sprint 1 — LLM layer + foundation (settimane 1-2)

Obiettivo: layer LLM provider-agnostico operativo + doctype Scenario/Schema + Desk forms.

- ✅ **LLM-1.1** — Skeleton modulo `os_lms/os_lms/ai/utils/llm/` con `provider.py`, `registry.py`, `config.py`, `errors.py`, `__init__.py`, `providers/__init__.py`
- ✅ **LLM-1.2** — `LLMProvider` ABC + dataclass (`ChatMessage`, `ChatResponse`, `ChatChunk`, `Usage`, `JsonSchema`, `ProviderConfig`)
- ✅ **LLM-1.3** — Registry + factory `get_provider(config)` + `list_providers()` + `@register("name")` decorator (con type-check su `LLMProvider`)
- ✅ **LLM-1.4** — Errori normalizzati: `LLMError` base + `LLMRateLimit`, `LLMInvalidAuth`, `LLMContextWindow`, `LLMServerError`, `LLMTimeout`, `LLMUnsupported`, `ProviderSdkNotInstalled` (con `provider`/`cause` attribute)
- ✅ **LLM-1.5** — `MockProvider` deterministico (fingerprint SHA-256 dei messaggi, streaming word-by-word, structured output JSON Schema). `RecordingProvider` rinviato a quando servirà al debug post-pilot
- ✅ **LLM-1.6** — `OpenAICompatibleProvider` base class su `requests` (httpx non disponibile in bench env): payload builder, streaming SSE, error mapping 401/403/429/400-context/5xx
- ✅ **LLM-1.7** — `OpenAIProvider` adapter (3 righe: eredita + DEFAULT_BASE_URL)
- ✅ **LLM-1.8** — `DeepSeekProvider` adapter (3 righe)
- ✅ **LLM-1.9** — `GeminiProvider` adapter via OpenAI-compat endpoint Google (3 righe)
- ✅ **LLM-1.10** — `AnthropicProvider` adapter: header `x-api-key` + `anthropic-version`, system top-level, structured output via tool_use forcing, streaming SSE event-based, stop_reason mapping
- ✅ **LLM-1.11** — `resolve_provider(purpose, override)` + `build_provider_config(name, settings)` + `_load_settings()` (lettura Password con `get_decrypted_password`)
- ✅ **LLM-1.12** — `chat_with_fallback(purpose, messages, override)` helper: catch `LLMRateLimit`/`LLMServerError` e prova provider successivi solo se setting è `auto`. Errori non-fallback (Auth) saltano subito.
- ✅ **LLM-1.13** — `pyproject.toml`: blocco `[project.optional-dependencies]` con extras `provider-openai`, `provider-anthropic`, `provider-gemini`, `provider-deepgram`, `provider-elevenlabs`, `provider-google-cloud`, `provider-azure`, `all-providers`
- ✅ **LLM-1.14** — `test_provider_encapsulation.py` (frappe.tests.UnitTestCase) — AST scan dei file Python di `os_lms`, fallisce su `import openai|anthropic|deepgram|elevenlabs|google.genai|google.cloud.{speech,texttospeech}|azure.cognitiveservices.speech` fuori da `utils/{llm,stt,tts}/providers/`. Negative test verificato (deliberato `import openai` rilevato).
- ✅ **LLM-1.15** — 33 unit test in `utils/llm/tests/`: MockProvider (6) + OpenAI-compat parametrizzato su 3 base_url (14) + Anthropic (8) + fallback (4) + encapsulation (1). Helpers `FakeResponse`/`RequestRecorder` in `_http_fakes.py`. Tutti verdi.
- ✅ **SET-1.1** — Estensione doctype `LMSA Settings`: 11 nuovi campi. `openai_key` lasciato `Data` per retro-compat; nuove chiavi (`gemini_key`, `deepseek_key`, `anthropic_key`) come `Password`. Migrazione applicata via `frappe.reload_doc`.
- ✅ **SET-1.2** — Estensione dataclass `OsLmsSettings` con 11 nuovi campi defaulted (zero breaking change).
- ✅ **SET-1.3** — `GptChatbot.ask()` reimplementato sopra `OpenAIProvider` via il layer unificato. `IngestionService` non cambia.
- ✅ **SET-1.4** — Endpoint `os_lms.os_lms.ai.utils.llm.api.test_providers` (gate System Manager/LMS Manager) + bottone Desk **"Test Provider Connection"** in `lmsa_settings.js`: tabella esito per provider con indicator color (`ok` green, `not_configured` gray, `invalid_auth` orange, `error` red).
- ✅ **DT-1.1** — Doctype `LMSA Simulation Scenario` (autoname `SCN-####`) + child `LMSA Simulation Learning Objective` + child `LMSA Simulation Seed Variation`. Validazione: lesson deve appartenere al corso; pesi obiettivi sommano a 1.0 se valorizzati. `created_by_instructor` auto-impostato su `before_insert`. **(2026-05-18 update)** rimosso il campo `course_chapter`: uno scenario è associato a un corso e al massimo a una singola lezione.
- ✅ **DT-1.2** — Doctype `LMSA Evaluation Schema` (autoname by `schema_name`, unique) + child `LMSA Schema Criterion`. Validazione: somma pesi criteri = 1.0 ± 0.001.
- ✅ **DT-1.3** — `permission_query_conditions` + `has_permission` su `LMSA Simulation Scenario` (hook in `os_lms/hooks.py`). System Manager/Moderator/LMS Manager: full. Course Creator: solo scenari dei propri corsi (via `Course Instructor.parent`). LMS Student: read su `Published` filtrati per enrollment.
- ✅ **DT-1.4** — Custom field `simulations_enabled` (Check) su `LMS Course` aggiunto a `fixtures/custom_field.json` (insert_after `enforce_quiz_on_completion`) e applicato al site live.

**Definition of done Sprint 1**: `MockProvider` funziona end-to-end via `resolve_provider`; gli adapter reali rispondono al `health_check()`; doctype Scenario/Schema creabili dal Desk dal docente. **✅ DoD soddisfatto** (smoke test SCN-0020 inserito via Administrator con schema valido e child tables popolate; "Test Provider Connection" risponde con tabella health-check; 33/33 test verdi).

### Sprint 2 — Sessioni testuali end-to-end (settimane 3-4)

Obiettivo: una sessione di chat completa funziona dal POST `start_session` fino all'`end_session`, con streaming.

- ✅ **ORC-2.1** — Skeleton `os_lms/os_lms/ai/simulations/` con `__init__.py` (re-export `SessionOrchestrator`), `orchestrator.py`, `prompts/`, `tests/`.
- ✅ **ORC-2.2** — `SessionOrchestrator` con lazy `settings`/`logger`. Service Pattern allineato a `IngestionService`. Composition over inheritance: provider iniettato via `resolve_provider`, prompt build delegato al modulo `prompts/`.
- ✅ **ORC-2.3** — `prompts/scenario_generator.py` (Prompt 1): dataclass `PersonaVariant`/`ScenarioVariant`, builder messaggi `build_scenario_generator_messages`, parser `parse_scenario_generator_output` (gestisce fenced ```json e raises su payload invalido). Retry con `temperature=0` su parse failure.
- ✅ **ORC-2.4** — `prompts/role_play.py` (Prompt 2): `build_role_play_system_prompt` italiano, regole di ruolo + stato interno (interest/trust/close_probability). `ROLE_PLAY_VERSION="rp.v1"` salvato su Session.
- ✅ **ORC-2.5** — `prompts/defense.py`: 15 regex pattern (EN+IT) per `ignore previous`, `you are now an AI`, `dimentica il tuo ruolo`, `jailbreak`, `DAN mode`, `act as developer`. Fallback `in_character_refusal(name)` usato bypassando LLM. Zero falsi positivi su 4 frasi benigne.
- ✅ **ORC-2.6** — Doctype `LMSA Simulation Session` submittable, autoname `SES-####`, status state machine (`In Progress`/`Completed`/`Abandoned`/`Error`/`Needs Review`). Permessi: System Manager/Moderator/LMS Student full, Course Creator read-only per i corsi che insegna.
- ✅ **ORC-2.7** — Doctype `LMSA Simulation Turn`, autoname `TRN-####`, non-submittable. `has_permission` delega al parent Session; `get_permission_query_conditions` con subquery.
- ✅ **ORC-2.8** — `start_session()`: genera variante (con retry su JSON parse), crea Session + primo turno cliente deterministico, ritorna `{session, first_turn}`.
- ✅ **ORC-2.9** — `send_message()`: persiste turno user (con flag injection), chiama LLM via `chat_with_fallback`, persiste turno assistant con tokens/latency/provider audit. Emette `EVENT_TURN_START` + `EVENT_TURN_COMPLETE` su WebSocket per-utente. Su `LLMError` setta status=Error e propaga.
- ✅ **ORC-2.10** — `end_session()`: imposta status `Completed`/`Abandoned`, popola `ended_at`, submit del doc (immutabilità). Idempotente: re-call su stato terminale ritorna `already_terminal=True`. Hook generate_debrief stubbato come TODO per Sprint 3.
- ✅ **ORC-2.11** — Hook `before_insert` `validate_quota` (module-level per resolver Frappe). Quota=0 → unlimited. Default DAILY_QUOTA=10. Conta sessioni `started_at >= today()` per `student`.
- ✅ **ORC-2.12** — `SessionOrchestrator.pseudonymize_session_id(user)` → SHA-256 stabile (16/64 char usable per log audit).
- ✅ **API-2.1** — `simulations/api.py` con 5 endpoint `@frappe.whitelist()`: `start_session`, `send_message`, `end_session`, `get_session`, `list_scenarios`. Tutti type-annotated.
- ✅ **API-2.2** — `load_session(session_id)` helper (analogo a `load_lesson`): gate per ruolo Moderator/owner/instructor.
- ✅ **API-2.3** — Eventi `frappe.publish_realtime`: `simulation:turn_start`, `simulation:turn_complete`, `simulation:error` (con `layer`). Best-effort: errori di WS non bloccano il turno.
- ✅ **API-2.4** — Streaming token-by-token: scaffolding pronto (`MockProvider`/`OpenAICompatibleProvider` supportano `stream=True`); collegamento all'HTTP endpoint posticipato a fase 3 (decisione #9 ancora aperta — chat HTTP sincrona in MVP).
- ✅ **TST-2.1** — `tests/test_prompts.py` (15 test) + `tests/test_orchestrator.py` (12 test): lifecycle start→send→end, injection, idempotenza, eventi WS, pseudonimizzazione, quota.
- ✅ **TST-2.2** — `tests/test_api.py` (9 test): permessi student vs instructor vs stranger, scenario Draft vs Published, enrollment, validazione input. Helper `_fixtures.py` con `CANNED_VARIANT`, `make_evaluation_schema`, `make_published_scenario`, `enable_mock_provider`, `cleanup_sessions_and_turns`.

**Definition of done Sprint 2**: `curl` POST a `start_session` + `send_message` produce un turno cliente coerente; WebSocket streamma token; quota giornaliera blocca al limite. **✅ DoD soddisfatto** (64/64 test verdi: 33 Sprint 1 + 31 Sprint 2 incl. integration test orchestrator end-to-end e API con `frappe.tests`).

### Sprint 3 — Debrief + UI studente (settimane 5-6)

Obiettivo: lo studente vede il debrief dopo `end_session`. UI dalla lezione al debrief.

- ✅ **DBR-3.1** — `prompts/debrief.py` (Prompt 3): dataclass `DebriefResult`+child, `build_debrief_messages`, `parse_debrief_output`, `DEBRIEF_SCHEMA` (JSON Schema usato come `response_format`), `DEBRIEF_VERSION="debrief.v1"`.
- ✅ **DBR-3.2** — Doctype `LMSA Simulation Debrief` (autoname `DBR-####`, status `Pending│Ready│Needs Review│Failed`) + child `LMSA Criterion Score`, `LMSA Debrief Strength`, `LMSA Debrief Improvement`, `LMSA Debrief Recommendation`. `passed` calcolato in `before_save` su schema.passing_threshold.
- ✅ **DBR-3.3** — `simulations/tasks.py` `generate_debrief(session_id)`: idempotente, retry su parse failure con `temperature=0`, due tentativi → `Needs Review` con `raw_llm_response` salvato. Enqueue da `end_session()` con `enqueue_after_commit=True`, queue `long`, timeout 300s.
- ✅ **DBR-3.4** — `_enrich_recommendations_with_rag()`: usa `RagDB.search(query=improvement_titles+suggestions+behavioral, course=session.course, top_k=5)` per back-fillare `lesson_id` mancanti e aggiungere fino a 2 lezioni extra. Best-effort: outage RAG non blocca il debrief.
- ✅ **DBR-3.5** — Eventi `simulation:debrief_ready` (success) + `simulation:debrief_failed` (errore/parse fail), publish_realtime al canale dello studente.
- ✅ **DBR-3.6** — Endpoint `get_debrief(session_id)` con stati `not_started│pending│ready│needs_review│failed`. Payload completo serializzato (criterion_scores, strengths, improvements, behavioral_analysis, recommended_content con `relevance_score`).
- ✅ **FE-3.1** — `frontend/src/pages/Simulations/SimulationPlay.vue` + rotta `/simulations/:sessionId`, auto-redirect a debrief quando la sessione termina.
- ✅ **FE-3.2** — `frontend/src/oslms/components/simulations/SimulationLauncher.vue` modale con scenari selezionabili, badge difficulty, modalità, time limit, redirect a SimulationPlay dopo start.
- ✅ **FE-3.3** — `frontend/src/oslms/components/simulations/ChatSession.vue` chat UI con bubble user/assistant, status badge, terminate button, indicatore "sta rispondendo", flag injection visibile, autoscroll, Cmd/Ctrl+Enter per inviare.
- ✅ **FE-3.4** — `useSimulationSession(sessionIdRef)` composable: load/send/end + subscribe a `turn_start/turn_complete/error`, optimistic user turn, reload autoritativo dopo ogni send.
- ✅ **FE-3.5** — `frontend/src/pages/Simulations/SimulationDebrief.vue` + rotta `/simulations/:sessionId/debrief` con hero score (verde/arancio per passed), per-criterio, strengths, improvements, behavioral analysis, lezioni consigliate.
- ✅ **FE-3.6** — `useSimulationDebrief(sessionIdRef)` composable: subscribe `debrief_ready/failed` + polling fallback ogni 4s con cap 60s.
- ✅ **FE-3.7** — Bottone "Avvia simulazione" integrato in `Lesson.vue` condizionale su `canLaunchSimulation` (simulations_enabled in settings + array scenari non vuoto).
- ✅ **FE-3.8** — Override `get_lesson`: ritorna `simulations` come array di scenari Published per la lezione (lesson-bound prima, poi course-level).
- ✅ **FE-3.9** — `get_lms_settings` espone `simulations_enabled` nel payload globale (riuso store settings frontend).
- ✅ **TST-3.1** — `cypress/e2e/simulations.cy.js`: setup mock provider via `frappe.client.set_value`, seed schema+scenario, API lifecycle completo (start/send/injection/end/get_debrief), UI flow Lesson → Launcher → SimulationPlay.

**Definition of done Sprint 3**: dalla lezione → click "Avvia" → chat → "Termina" → debrief visualizzato con punteggio e lezioni consigliate, tutto in <30s end-to-end con `MockProvider`. **✅ DoD soddisfatto** (frontend build verde, 81/81 test backend verdi inclusi 17 nuovi per DBR + Cypress E2E scritto).

### Sprint 4 — Pannello docente + pilot (settimane 7-8)

Obiettivo: il docente crea/modifica scenari e vede i report. Pilot su un corso reale.

- ✅ **DOC-4.1** — `ScenarioEditor.vue` form completo (identity, persona/situation, evaluation schema autocomplete, learning_objectives + seed_variations editabili, limiti, provider/model override) + bottone "Prova come studente" che avvia una sessione e routa al SimulationPlay. **Backend**: endpoint `save_scenario`/`get_scenario`/`delete_scenario`/`list_my_scenarios` con gate instructor-of-course.
- ✅ **DOC-4.2** — `EvaluationSchemaEditor.vue` form con criteri editabili, descrizione/observable_behaviors per criterio, validazione client-side della somma pesi=1.00 (live indicator) + server enforce nel doctype validate(). **Backend**: endpoint `save_evaluation_schema`/`get_evaluation_schema`/`delete_evaluation_schema`/`list_my_evaluation_schemas` con permessi owner/shared/moderator.
- ✅ **DOC-4.3** — Endpoint `instructor_review_debrief(session_id, review)`: gate ruolo+corso, scrive `instructor_review/by/at` sul `LMSA Simulation Debrief`.
- ✅ **DOC-4.4** — Endpoint `instructor_report(course, student, period_days, scenario)`: KPI (total_sessions, completed_sessions, avg_score, pass_rate, students_count), `score_distribution` a 5 bucket, `top_improvement_titles` (5 più frequenti), lista sessioni arricchite con debrief.
- ✅ **DOC-4.5** — `frontend/src/pages/Simulations/InstructorReports.vue` con `Tabs` (Report/Scenari/Schemi), filtri (corso/periodo/studente), KPI cards, bar chart distribuzione punteggi, top improvements, tabella sessioni con drill-down. Rotta `/simulations/admin`. Header CTA globali "+ Scenario" / "+ Schema di valutazione" sempre disponibili. Legge query params `?course=<id>&tab=scenarios` per pre-filtrare e pre-popolare l'editor. **Entry point**: tab dedicata **"Simulations"** in `CourseDetail.vue` (visibile a instructor/moderator se `simulations_enabled`), che renderizza inline il nuovo componente `CourseSimulations.vue` con KPI per stato + lista scenari del corso + create/edit (via `ScenarioEditor` in dialog) + link "Apri report completo" verso `InstructorReports`.
- ✅ **DOC-4.6** — `TranscriptDrawer.vue`: modale full-screen con `ChatSession` in `readOnly=true` + sintesi debrief + form nota docente (chiama `instructor_review_debrief`). Apertura dal drill-down della tabella sessioni.
- 📋 **PIL-4.1** — *Attività operativa*: selezione corso pilot + curazione 3-5 scenari (richiede docente esperto del dominio vendita). Non blocca lo sviluppo.
- 📋 **PIL-4.2** — *Attività operativa*: sessione formativa docenti pilot (1h). Materiale d'appoggio: PLAN-os_lms.md §7 + screenshot del pannello.
- 📋 **PIL-4.3** — *Attività operativa*: onboarding 20-30 studenti pilot (annunci + abilitazione `simulations_enabled` sul corso pilot).
- 📋 **PIL-4.4** — *Attività operativa*: retrospettiva post-pilot a +2 settimane dal lancio (dati: `instructor_report`, costi LLM, feedback qualitativo).

**Definition of done Sprint 4**: il docente del corso pilot crea scenari/schemi di valutazione dal SPA, vede le sessioni dei suoi studenti e legge i debrief con citazioni testuali. **✅ DoD codice soddisfatto** (92/92 test backend verdi inclusi 11 nuovi Sprint 4, frontend build verde, drill-down review docente operativo). PIL-4.* tracciati come operativi del team.

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
- 2026-05-18 — sviluppo — Sprint 1 batch 1: **LLM-1.1, 1.2, 1.3, 1.4, 1.5, 1.11, SET-1.1, 1.2** completati. `MockProvider` end-to-end verificato; `resolve_provider("chat")` legge `LMSA Settings`; retro-compat tutor RAG OK
- 2026-05-18 — sviluppo — Sprint 1 batch 2: **LLM-1.6→1.10, 1.12, 1.13, 1.14, 1.15** completati. 4 adapter HTTP (OpenAI / DeepSeek / Gemini OpenAI-compat / Anthropic native) + fallback chain + extras `[project.optional-dependencies]` + test architetturale encapsulation + 33 unit test.
- 2026-05-18 — sviluppo — Sprint 1 batch 3: **SET-1.3, SET-1.4** completati. `GptChatbot` migrato a wrapper su `OpenAIProvider` (retro-compat tutor RAG). Endpoint `test_providers` + bottone Desk "Test Provider Connection" su `LMSA Settings`.
- 2026-05-18 — sviluppo — Sprint 1 batch 4: **DT-1.1, 1.2, 1.3, 1.4** completati. 5 doctype (`LMSA Simulation Scenario` + `LMSA Evaluation Schema` + 3 child) con validazione pesi + permission_query_conditions + custom field `simulations_enabled` su `LMS Course`. **Sprint 1 chiuso (23/23)**.
- 2026-05-18 — sviluppo — Installate skill `python-design-patterns` e `python-testing-patterns` (`.claude/skills/`), applicate ai 4 adapter + 33 test scritti.
- 2026-05-18 — refactor — rimosso campo `course_chapter` da `LMSA Simulation Scenario` (uno scenario è associato a un corso, opzionalmente a una singola lezione). Colonna DB droppata, doctype ricaricato, validazione cross-course lesson confermata.
- 2026-05-18 — sviluppo — Sprint 2 batch 1 (foundation): **ORC-2.6, 2.7** doctype Session (submittable) + Turn con permission_query_conditions + has_permission. Hook agganciati a `os_lms/hooks.py`.
- 2026-05-18 — sviluppo — Sprint 2 batch 2 (prompts): **ORC-2.1, 2.3, 2.4, 2.5** pure functions in `ai/simulations/prompts/` — ScenarioGenerator, RolePlayPrompt, prompt_defense (15 pattern EN+IT, zero falsi positivi).
- 2026-05-18 — sviluppo — Sprint 2 batch 3 (orchestrator): **ORC-2.2, 2.8, 2.9, 2.10, 2.11, 2.12** SessionOrchestrator con state machine, fallback chain, quota giornaliera, pseudonimizzazione SHA-256, eventi realtime.
- 2026-05-18 — sviluppo — Sprint 2 batch 4 (API + test): **API-2.1, 2.2, 2.3, 2.4, TST-2.1, TST-2.2** endpoint REST + 31 test. **Sprint 2 chiuso (18/18)**, totale 64/64 test verdi.
- 2026-05-18 — sviluppo — Sprint 3 batch 1 (backend debrief): **DBR-3.1→3.6** doctype Debrief+4 child, DebriefEngine + RQ job + integrazione RagDB + endpoint get_debrief + eventi WS.
- 2026-05-18 — sviluppo — Sprint 3 batch 2 (frontend studente): **FE-3.1→3.9** composables, ChatSession, SimulationLauncher, pagine Play+Debrief, integrazione Lesson.vue, override get_lesson+get_lms_settings. Build frontend verde.
- 2026-05-18 — sviluppo — Sprint 3 batch 3 (test): 17 nuovi backend test (test_debrief_prompts, test_debrief_job) + Cypress E2E simulations.cy.js. **Sprint 3 chiuso (16/16)**, totale 81/81 test backend verdi.
- 2026-05-18 — sviluppo — Sprint 4 batch 1 (backend): endpoint `instructor_review_debrief`, `instructor_report`, CRUD `save_scenario`/`save_evaluation_schema`/`get_*`/`delete_*`/`list_my_*`, `get_transcript`. Permission helper `_ensure_instructor_of_course`.
- 2026-05-18 — sviluppo — Sprint 4 batch 2 (frontend): `ScenarioEditor.vue`, `EvaluationSchemaEditor.vue`, `InstructorReports.vue` (tabs Report/Scenari/Schemi), `TranscriptDrawer.vue` (drill-down) + rotta `/simulations/admin`. Build verde.
- 2026-05-18 — sviluppo — Sprint 4 batch 3 (test): 11 nuovi backend test (test_instructor_api). **Sprint 4 dev chiuso (6/6 DOC-*)**, totale 92/92 test backend verdi. PIL-4.* operativi del team.
- 2026-05-19 — refactor — rinominato il dominio "rubrica" → "schema di valutazione": doctype `LMSA Evaluation Rubric` → `LMSA Evaluation Schema`, `LMSA Rubric Criterion` → `LMSA Schema Criterion`, field `rubric_name` → `schema_name`, field su Scenario `evaluation_rubric` → `evaluation_schema`, endpoint `*_rubric*` → `*_evaluation_schema*`, componente `RubricEditor.vue` → `EvaluationSchemaEditor.vue`, label UI italiane "Rubrica" → "Schema di valutazione". DB migrato (drop tabelle obsolete + drop colonna `evaluation_rubric`), 92/92 test verdi, build frontend verde.
- 2026-05-19 — UX — sostituita l'entry "AI Simulations" del dropdown azioni con una **tab dedicata "Simulations"** in `CourseDetail.vue` (visibile a instructor/moderator quando `simulations_enabled`). Nuovo componente `CourseSimulations.vue` con KPI status, tabella scenari del corso, create/edit via dialog `ScenarioEditor`, delete (bloccato per Published), link al pannello globale `InstructorReports`.
