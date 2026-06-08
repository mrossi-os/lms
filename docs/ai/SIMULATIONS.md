# AI Sales Simulations

Il modulo simulazioni implementa un sistema di **role-play conversazionale** dove lo studente (umano) si esercita parlando con un cliente AI, e una pipeline di **valutazione automatica** che permette al docente di testare la qualità degli scenari prima di pubblicarli.

Sorgenti principali:
- Frontend: `frontend/src/oslms/components/simulations/`
- Backend orchestrazione: `apps/os_lms/os_lms/os_lms/ai/simulations/`
- Backend eval: `apps/os_lms/os_lms/os_lms/ai/simulations/eval/`
- Documentazione correlata: [TUTOR.md](TUTOR.md), [INGESTION.md](INGESTION.md)

## I due ruoli

```
┌─────────────────────────┐      ┌─────────────────────────┐
│ STUDENTE                │      │ DOCENTE                 │
│                         │      │                         │
│ - Sceglie scenario      │      │ - Crea/edita scenari    │
│ - Conversa col cliente  │      │ - Definisce schemi di   │
│   AI in chat            │      │   valutazione           │
│ - Vede il debrief AI    │      │ - Lancia "Test          │
│ - Eventuale review del  │      │   simulazione" per      │
│   docente               │      │   verificare qualità    │
│                         │      │ - Rivede debrief e      │
│                         │      │   approva/corregge      │
└─────────────────────────┘      └─────────────────────────┘
         │                                  │
         ▼                                  ▼
   start_session             ScenarioEditor + run_simulation_test
   send_message / end_session     + Golden runs (regression manuale)
```

Lo studente vede la "vera" simulazione live (`SimulationLauncher` → `ChatSession`). Il docente ha sia tool di authoring (`ScenarioEditor`, `EvaluationSchemaEditor`) sia tool di QA pre-pubblicazione (`SimulationTestDialog`, `GoldenRunsModal`, `EvaluationResultsDialog`).

## Architettura ad alto livello

```
                 frontend/src/oslms/components/simulations/
                 ┌──────────────────────────────────────────┐
   STUDENTE ───►│  SimulationLauncherButton                 │
                │   └─► SimulationLauncher (pick scenario)  │
                │        └─► route: SimulationPlay          │
                │             └─► ChatSession (live UI)     │
                │                                            │
   DOCENTE ────►│  ScenarioEditor (CRUD scenario)            │
                │   ├─► SimulationTestDialog                 │
                │   │    └─► run_simulation_test (eval API)  │
                │   ├─► EvaluationSchemaEditor               │
                │   │    └─► CriterionEditor (rubrica)       │
                │   ├─► GoldenRunsModal                      │
                │   │    ├─► GoldenRunEditor                 │
                │   │    └─► GoldenTurnEditor                │
                │   └─► EvaluationResultsDialog              │
                │        ├─► EvaluationTraceCard             │
                │        │    └─► DimensionScoreBar          │
                │        └─► TranscriptDrawer (read-only)    │
                └──────────────────────────────────────────┘
                              │
                              ▼
                 apps/os_lms/os_lms/os_lms/ai/simulations/
                 ┌──────────────────────────────────────────┐
                 │  api.py  (whitelisted endpoints)          │
                 │    start_session, send_message,           │
                 │    end_session, get_session,              │
                 │    generate_debrief, instructor_review_*  │
                 │                                            │
                 │  orchestrator.SessionOrchestrator         │
                 │    drive del ciclo umano↔AI               │
                 │                                            │
                 │  customer.py (pure services)              │
                 │    ScenarioVariantGenerator               │
                 │    CustomerTurnService                    │
                 │                                            │
                 │  prompts/                                  │
                 │    role_play.py, scenario_generator.py,   │
                 │    debrief.py, defense.py                 │
                 │                                            │
                 │  eval/  (parallel quality pipeline)        │
                 │    authoring_runner.AuthoringEvaluation…  │
                 │    runner.run_synthetic_llm_student       │
                 │    judges/ (4 dimensioni)                 │
                 │    student/ (golden + llm_student)        │
                 └──────────────────────────────────────────┘
```

## Flusso A — Studente che gioca una simulazione

### 1. Entrata: `SimulationLauncherButton.vue`

Il fab button (in basso a destra nella vista lezione) carica i scenari disponibili per il corso/lezione corrente via `os_lms.os_lms.ai.simulations.api.list_my_scenarios` e apre `SimulationLauncher`.

### 2. Selezione: `SimulationLauncher.vue`

Dialog con la lista degli scenari pubblicati. Lo studente sceglie e clicca "Avvia" → POST `start_session(scenario_id, modality)`. Al successo, router push a `SimulationPlay` con il `sessionId` ritornato.

Backend lato:
- `SessionOrchestrator.start_session(scenario_id, modality)` (`orchestrator.py:98-160`):
  1. Controlla `LMSA Settings.simulations_enabled`
  2. Genera la `ScenarioVariant` (persona + situazione) via `ScenarioVariantGenerator.generate` (structured output + retry)
  3. Crea `LMSA Simulation Session` con persona, situazione, seed, prompt_version
  4. Persiste il primo turno cliente con `_first_customer_line` (deterministico — "Buongiorno, sono X, Y di Z. Mi dica.")
  5. Logga + ritorna `(session_name, first_turn)`

### 3. Chat live: `ChatSession.vue` (riusata da `SimulationPlay`)

Renderer chat bidirezionale:
- Visualizza la persona del cliente (header con `persona.name`, `role di company`)
- Lista dei turni con bubble layout: user a destra (blu), assistant a sinistra (grigio)
- Badge ⚠️ sui turn con `injection_attempt_detected`
- Textarea con shortcut Cmd/Ctrl+Enter per inviare
- Button "Termina" che emette `end` (gestito dal parent)

Emit eventi `send(text)` e `end(reason)` consumati dal parent (la page `SimulationPlay` che li mappa su:
- `send_message(session_id, text)` → `SessionOrchestrator.send_message` (`orchestrator.py:162-241`): detect injection → in_character_refusal (canned) OPPURE `CustomerTurnService.ask` via `chat_with_fallback("chat", ...)`. Persiste user+assistant turn, publish `simulation:turn_start`/`turn_complete` realtime.
- `end_session(session_id, reason)` → `SessionOrchestrator.end_session` (`orchestrator.py:243-275`): submit del doc (immutabilità per audit), enqueue `generate_debrief` job.

Vedi la sezione "ChatSession come read-only" più avanti — lo stesso componente viene riusato dentro `TranscriptDrawer` per mostrare conversazioni passate.

### 4. Debrief automatico

`end_session` enqueua `os_lms.os_lms.ai.simulations.tasks.generate_debrief(session_id)` (in `simulations/tasks.py`). Il job carica la trascrizione + lo schema di valutazione del scenario e fa una LLM call con `build_debrief_messages` (`prompts/debrief.py`) — output strutturato con `overall_score`, `passed`, `criterion_scores`, `strengths`, `improvements`. Persiste su `LMSA Simulation Debrief`.

Il frontend polla via `get_debrief(session_id)` e mostra i risultati.

### 5. Review docente (opzionale)

`instructor_review_debrief(session_id, review)` permette al docente di aggiungere una nota sopra il debrief AI (campo `instructor_review` su `LMSA Simulation Debrief`).

## Flusso B — Docente che crea/testa scenari

### 1. CRUD scenario: `ScenarioEditor.vue`

Form completo per `LMSA Simulation Scenario`:
- Header con breadcrumbs + bottoni "Test simulazione" / "Golden runs" / "Salva"
- Sezioni: identità (nome, difficoltà), corso/lezione (Link autocomplete su `LMS Course` + `Course Lesson`), persona base del cliente, template situazione, obiettivi formativi (child table), seed variations (variabili randomizzate)
- Link al schema di valutazione (`LMSA Evaluation Schema`)

Il salvataggio scrive su `LMSA Simulation Scenario`. La pubblicazione (`status = "Published"`) lo rende disponibile agli studenti via `list_my_scenarios`.

### 2. Schema di valutazione: `EvaluationSchemaEditor.vue` + `CriterionEditor.vue`

`LMSA Evaluation Schema` è una rubrica riusabile fra scenari. `EvaluationSchemaEditor` permette di:
- Creare/duplicare/esportare schemi (JSON)
- Aggiungere/ordinare criteri (`CriterionEditor` come accordion per ogni criterio)
- Ogni criterio ha: nome, descrizione, peso, indicatori positivi/negativi

Lo schema viene poi consumato dal **debrief judge** della pipeline eval (e dal `generate_debrief` job).

### 3. Test simulazione: `SimulationTestDialog.vue`

Apre il dialog di QA pre-pubblicazione. Campi:
- **Profilo studente** (`competent` | `novice` | `aggressive` | etc., da `list_student_profiles`)
- **Numero conversazioni** (1-3, hard cap su `MAX_VARIANTS` in `eval/api.py`)
- **Brief del ruolo dello studente** (textarea opzionale, sovrascrive l'apertura del system prompt dell'LLM-student)

POST `run_simulation_test(scenario, student_profile, num_variants, student_scenario_brief?)`. L'endpoint crea un `LMSA Quality Evaluation` con `run_mode="simulation_test"` e fa partire `AuthoringEvaluationRunner(doc.name).run()` (vedi sezione dedicata sotto).

### 4. Risultati: `EvaluationResultsDialog.vue` + `EvaluationTraceCard.vue` + `DimensionScoreBar.vue`

- Polling su `get_evaluation_status` finché `status == "complete"`, poi `get_evaluation_result`
- Mostra:
  - Header con 4 `DimensionScoreBar` (persona, coverage, debrief, difficulty) — aggregate scores
  - Lista di `EvaluationTraceCard` espandibili: 1 card per trace (= 1 variant)
  - Ogni card mostra: punteggi per dimensione, summary del giudice, evidence_quotes, warnings
  - Pulsante per aprire il transcript completo della trace in `TranscriptDrawer` (riusa `ChatSession` in modalità read-only)

### 5. Golden runs: `GoldenRunsModal.vue` + `GoldenRunEditor.vue` + `GoldenTurnEditor.vue`

Feature di **regression testing manuale**. Il docente compone a mano una conversazione "ideale" (`LMSA Scenario Golden Run`):
- `GoldenRunsModal`: lista dei golden run definiti per lo scenario
- `GoldenRunEditor`: form con `name_label`, `expected_outcomes`, lista di `LMSA Golden Turn`
- `GoldenTurnEditor`: editor di un singolo turno (`role: user | assistant`, testo)

Lanciare `run_golden_regression(scenario, golden_name?)` esegue i 4 judges sui golden senza generare nuovi transcript (replay deterministico). Utile per verificare che modifiche ai prompt o ai judges non rompano risultati validati a mano.

## L'`AuthoringEvaluationRunner` in dettaglio

`AuthoringEvaluationRunner` (`eval/authoring_runner.py`) è la classe che orchestra il `simulation_test`. Service Pattern con lazy properties:

```
AuthoringEvaluationRunner(eval_id)
  ├─ evaluation (frappe doc loaded in __init__)
  ├─ provider     (lazy — _get_provider, wrappata in LoggingProvider se debug ENABLED)
  ├─ model        (lazy — _get_eval_model, da LMSA Settings.simulation_debrief_model)
  ├─ scenario     (lazy — _scenario_ref dal doc Frappe)
  └─ lesson_context (lazy — RAG search via IngestionService, 1 sola call cached)

  .run()
    ├─ _mark_running    (status="running", save, commit)
    ├─ _read_params     (student_profile + num_variants)
    ├─ loop num_variants × _run_one_variant
    │    ├─ run_synthetic_llm_student (1 variant + N turni alternati)
    │    │   ├─ ScenarioVariantGenerator.generate (1 LLM call, structured output)
    │    │   ├─ for turn in max_turns:
    │    │   │   - even: build_student_messages → provider.chat (student turn)
    │    │   │   - odd:  CustomerTurnService.ask (customer turn, stesso path di prod)
    │    │   └─ ritorna transcript
    │    ├─ _build_trace (crea LMSA Evaluation Trace con transcript_json)
    │    ├─ evaluate_transcript → 4 judges in parallelo
    │    └─ _persist_trace_scores (dimension_scores_json sul trace)
    ├─ _compute_aggregates (media per dimensione)
    ├─ status="complete" (o "failed" in except)
    └─ finally: save + commit + _publish (simulation:eval_complete realtime)
```

Vedi `runner.py` per i dettagli del loop di alternanza studente/cliente, `customer.py` per le pure services condivise con la simulation di produzione, `judges/` per le 4 dimensioni.

## Componenti frontend — inventario

### Top-level (`simulations/`)

| File | Ruolo | Endpoint chiamati |
|---|---|---|
| `SimulationLauncherButton.vue` | Fab button nello studente view; carica scenari del corso | `list_my_scenarios` |
| `SimulationLauncher.vue` | Dialog di selezione scenario; start della sessione | `start_session` |
| `ChatSession.vue` | UI chat bidirezionale; riusata in live e read-only | `send_message`, `end_session` (via parent) |
| `ScenarioEditor.vue` | Form CRUD scenario; hub di azioni docente | `list_scenarios`, scenario CRUD via frappe.client |
| `EvaluationSchemaEditor.vue` | CRUD schemi di valutazione (rubrica criteri) | LMSA Evaluation Schema CRUD |
| `CriterionEditor.vue` | Accordion singolo criterio dentro lo schema | (nessuno — child editor) |
| `TranscriptDrawer.vue` | Dialog read-only trascrizione + debrief | `get_session`, `get_debrief` |

### Sotto `simulations/eval/`

| File | Ruolo | Endpoint chiamati |
|---|---|---|
| `SimulationTestDialog.vue` | Dialog "Test simulazione" (profile + num_variants + brief) | `list_student_profiles`, `run_simulation_test` |
| `EvaluationResultsDialog.vue` | Display risultati eval (polling + view) | `get_evaluation_status`, `get_evaluation_result` |
| `EvaluationTraceCard.vue` | Card espandibile per singolo trace | (nessuno — render-only) |
| `DimensionScoreBar.vue` | Barra grafica punteggio 0-1 per dimensione | (nessuno — render-only) |
| `GoldenRunsModal.vue` | Modal lista golden runs | LMSA Scenario Golden Run CRUD |
| `GoldenRunEditor.vue` | Form singolo golden run | LMSA Scenario Golden Run save |
| `GoldenTurnEditor.vue` | Editor singolo turno del golden | (nessuno — child editor) |

## Backend touchpoints — endpoint chiave

`simulations/api.py` (whitelisted, lifecycle + studente):
- `start_session(scenario_id, modality)`
- `send_message(session_id, text)`
- `end_session(session_id, reason)`
- `get_session(session_id)`
- `get_debrief(session_id)` / `generate_debrief(session_id)` (manuale)
- `instructor_review_debrief(session_id, review)`
- `list_my_scenarios(course?)` (per studente)
- `list_scenarios(course?)` (per istruttore — pubblicati + bozze del proprio corso)
- `instructor_report(...)` (analytics per docente)

`simulations/eval/api.py` (whitelisted, autoring + QA):
- `run_simulation_test(scenario, student_profile, num_variants, student_scenario_brief?)`
- `run_golden_regression(scenario, golden_name?)`
- `run_production_evaluation(session_id)` (valutare una sessione reale a posteriori)
- `get_evaluation_status(eval_id)` / `get_evaluation_result(eval_id)`
- `list_evaluations_for_scenario(scenario)` / `list_evaluations_for_session(session_id)`
- `list_student_profiles()`

## Doctypes coinvolti

| Doctype | Ruolo |
|---|---|
| `LMSA Simulation Scenario` | Definizione di uno scenario di simulazione (persona base, situation template, learning_objectives, seed_variations, course_lesson, evaluation_schema) |
| `LMSA Simulation Session` | Una sessione di gioco umano↔AI. Immutabile dopo `submit` (lifecycle: In Progress → Completed/Abandoned/Error) |
| `LMSA Simulation Turn` | Turn-by-turn della sessione. Ogni doc è una battuta (user o assistant) con prompt metadata, latenza, token usage |
| `LMSA Simulation Debrief` | Debrief AI post-sessione. Child tables: criteri valutati, strengths, improvements |
| `LMSA Evaluation Schema` | Rubrica riusabile di criteri di valutazione |
| `LMSA Quality Evaluation` | Run di valutazione (simulation_test / production / golden_regression). Child: `LMSA Evaluation Trace` |
| `LMSA Evaluation Trace` | Una singola conversazione judged (transcript_json + dimension_scores_json + judge_versions_json) |
| `LMSA Scenario Golden Run` | Conversazione canonica composta a mano per regression testing |
| `LMSA Golden Turn` | Singolo turno di un golden run |

## Configurazione

Da `LMSA Settings`:

| Campo | Uso |
|---|---|
| `simulations_enabled` | Gate globale: `SessionOrchestrator.start_session` throw se False |
| `simulation_chat_provider` | Provider per i turni cliente (`auto` → routing + fallback) |
| `simulation_debrief_provider` | Provider per debrief + eval judges |
| `simulation_chat_model` / `simulation_debrief_model` | Override modello concreto |
| `simulation_provider_fallback_order` | CSV: catena di fallback su rate-limit/server-error |
| `simulation_daily_quota_per_user` | Hook `validate_quota` su Simulation Session insert (0 = illimitato) |

Da `site_config.json`: nessuna chiave specifica per simulations (eredita la config provider LLM globale).

## Note operative

- **Real-time eventi**: `SessionOrchestrator` pubblica `simulation:turn_start` / `simulation:turn_complete` / `simulation:error` su `frappe.publish_realtime`, scoped allo studente. Il frontend può subscribere per progressive UI.
- **Quota**: `validate_quota` (hook `before_insert` su `LMSA Simulation Session`) blocca lo studente che ha esaurito la quota giornaliera.
- **Injection defense**: ogni `user_text` in `send_message` passa per `detect_injection` (`prompts/defense.py`); attacchi rilevati ricevono una risposta canned **in carattere** (`in_character_refusal(persona.name)`) e il turn user viene flaggato (`injection_attempt_detected = 1`) per audit.
- **Prompt versioning**: ogni sessione persiste `prompt_version = "{SCENARIO_GEN_VERSION}+{ROLE_PLAY_VERSION}"` (es. `gen.v1+rp.v1`). Bumpare un version constant nei prompt builder permette di tracciare quale prompt ha generato quale sessione.
- **Pseudonymizazione**: `SessionOrchestrator.pseudonymize_session_id(user)` ritorna SHA-256 dello user — usato quando si inviano payload a provider esterni per evitare di esporre email.
- **LLM call logging (debug)**: `eval/authoring_runner.py` wrappa il provider con `LoggingProvider` se `utils/llm/logger.ENABLED = True`. Tutti i call dell'eval finiscono in `{site}/private/files/llm_logs/{eval_id}.jsonl`. Disabilitato di default — vedi commento nel modulo logger.
- **Asimmetria student/customer nell'eval**: il customer turn passa per `CustomerTurnService` (stesso codepath della produzione), lo student turn è inline nel runner (non c'è analogo lato prod perché lì lo studente è umano). Il customer è quindi cover-tested anche dall'eval; lo student turn no.

## File rilevanti (cheat sheet)

| Layer | File |
|---|---|
| Frontend (studente) | `frontend/src/oslms/components/simulations/SimulationLauncherButton.vue`, `SimulationLauncher.vue`, `ChatSession.vue` |
| Frontend (docente) | `ScenarioEditor.vue`, `EvaluationSchemaEditor.vue`, `CriterionEditor.vue`, `TranscriptDrawer.vue` |
| Frontend (eval/QA) | `eval/SimulationTestDialog.vue`, `eval/EvaluationResultsDialog.vue`, `eval/EvaluationTraceCard.vue`, `eval/DimensionScoreBar.vue`, `eval/GoldenRunsModal.vue`, `eval/GoldenRunEditor.vue`, `eval/GoldenTurnEditor.vue` |
| Backend API | `apps/os_lms/os_lms/os_lms/ai/simulations/api.py`, `simulations/eval/api.py` |
| Orchestrazione prod | `simulations/orchestrator.py` (SessionOrchestrator) |
| Pure services | `simulations/customer.py` (ScenarioVariantGenerator, CustomerTurnService) |
| Prompts | `simulations/prompts/scenario_generator.py`, `role_play.py`, `debrief.py`, `defense.py` |
| Debrief job | `simulations/tasks.py:generate_debrief` |
| Eval orchestration | `simulations/eval/authoring_runner.py`, `eval/jobs.py` |
| Eval transcript gen | `simulations/eval/runner.py` (run_synthetic_llm_student) |
| Eval judges | `simulations/eval/judges/persona.py`, `coverage.py`, `debrief.py`, `difficulty.py` |
| Eval student helpers | `simulations/eval/student/llm_student.py`, `golden.py`, `profiles.py` |
| LLM call logger (debug) | `apps/os_lms/os_lms/os_lms/ai/utils/llm/logger.py` |
| Permessi | `simulations/eval/permissions.py` |
