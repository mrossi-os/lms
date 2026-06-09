# AI Simulations

Il modulo simulazioni implementa un sistema di **role-play conversazionale** dove lo studente (umano) si esercita parlando con un personaggio AI (cliente, esaminatore, paziente, ecc.), e una pipeline di **valutazione automatica** che permette al docente di testare la qualità degli scenari prima di pubblicarli.

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
│ - Conversa col           │      │   (anche via "Compila   │
│   personaggio AI         │      │    con IA")             │
│ - Vede il debrief AI    │      │ - Definisce schemi di   │
│ - Eventuale review del  │      │   valutazione (idem)    │
│   docente                │      │ - Lancia "Test          │
│                         │      │   simulazione" per      │
│                         │      │   verificare qualità    │
│                         │      │ - Rivede debrief e      │
│                         │      │   approva/corregge      │
└─────────────────────────┘      └─────────────────────────┘
         │                                  │
         ▼                                  ▼
   start_session             ScenarioEditor + run_simulation_test
   send_message / end_session
```

Lo studente vede la simulazione live (`SimulationLauncher` → `ChatSession`). Il docente ha sia tool di authoring (`ScenarioEditor`, `EvaluationSchemaEditor`) sia tool di QA pre-pubblicazione (`SimulationTestDialog`, `EvaluationResultsDialog`).

Il personaggio interpretato dall'AI è **agnostico al dominio**: può essere un cliente in vendita, un esaminatore in didattica, un paziente in medical training, un intervistatore — la "persona" che lo definisce vive nel campo `roleplay_persona` del doctype scenario.

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
                │   ├─► Bottone "Compila con IA"             │
                │   ├─► SimulationTestDialog                 │
                │   │    └─► run_simulation_test (eval API)  │
                │   ├─► EvaluationSchemaEditor               │
                │   │    ├─► CriterionEditor (rubrica)       │
                │   │    └─► Bottone "Compila con IA"        │
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
                 │    generate_debrief, instructor_review_*, │
                 │    ai_generate_scenario,                  │
                 │    ai_generate_evaluation_schema          │
                 │                                            │
                 │  orchestrator.SessionOrchestrator         │
                 │    drive del ciclo umano↔AI               │
                 │                                            │
                 │  role_player.py (pure services)           │
                 │    ScenarioVariantGenerator               │
                 │    RolePlayerTurnService                  │
                 │                                            │
                 │  authoring_ai.py                          │
                 │    generate_scenario_payload              │
                 │    generate_evaluation_schema_payload     │
                 │                                            │
                 │  prompts/                                  │
                 │    role_play.py, scenario_generator.py,   │
                 │    debrief.py, defense.py,                │
                 │    judge_loader.py, template_loader.py    │
                 │                                            │
                 │  eval/  (parallel quality pipeline)        │
                 │    authoring_runner.AuthoringEvaluation…  │
                 │    runner.run_synthetic_llm_student       │
                 │    judges/ (4 dimensioni)                 │
                 │    student/llm_student.py + profiles.py   │
                 └──────────────────────────────────────────┘
```

## Flusso A — Studente che gioca una simulazione

### 1. Entrata: `SimulationLauncherButton.vue`

Il fab button (in basso a destra nella vista lezione) carica gli scenari disponibili per il corso/lezione corrente via `list_my_scenarios` e apre `SimulationLauncher`.

### 2. Selezione: `SimulationLauncher.vue`

Dialog con la lista degli scenari pubblicati. Lo studente sceglie e clicca "Avvia" → POST `start_session(scenario_id, modality)`. Al successo, router push a `SimulationPlay` con il `sessionId` ritornato.

Backend lato:
- `SessionOrchestrator.start_session(scenario_id, modality)`:
  1. Controlla `LMSA Settings.simulations_enabled`
  2. Genera la `ScenarioVariant` (persona + situazione) via `ScenarioVariantGenerator.generate` (structured output + retry)
  3. Crea `LMSA Simulation Session` con persona, situazione, seed, prompt_version
  4. Persiste il primo turno del personaggio con `_first_roleplay_line` (deterministico — "Buongiorno, sono X, Y di Z. Mi dica.")
  5. Logga + ritorna `(session_name, first_turn)`

### 3. Chat live: `ChatSession.vue`

Renderer chat bidirezionale:
- Visualizza la persona del personaggio (header con `persona.name`, `role di company`)
- Lista dei turni con bubble layout: user a destra (blu), assistant a sinistra (grigio)
- Badge ⚠️ sui turn con `injection_attempt_detected`
- Textarea con shortcut Cmd/Ctrl+Enter per inviare
- Button "Termina" che emette `end` (gestito dal parent)

Emit `send(text)` e `end(reason)` consumati dal parent (`SimulationPlay`):
- `send_message(session_id, text)` → `SessionOrchestrator.send_message`: detect injection → `in_character_refusal` canned OPPURE `RolePlayerTurnService.ask` via `chat_with_fallback("chat", ...)`. Persiste user+assistant turn, publish `simulation:turn_start`/`turn_complete` realtime.
- `end_session(session_id, reason)` → `SessionOrchestrator.end_session`: submit del doc (immutabilità per audit), enqueue `generate_debrief` job.

Lo stesso `ChatSession` viene riusato dentro `TranscriptDrawer` per mostrare conversazioni passate in modalità read-only.

### 4. Debrief automatico

`end_session` enqueua `simulations.tasks.generate_debrief(session_id)`. Il job carica la trascrizione + lo schema di valutazione del scenario e fa una LLM call con `build_debrief_messages` (`prompts/debrief.py`) — output strutturato con `overall_score`, `passed`, `criterion_scores`, `strengths`, `improvements`. Persiste su `LMSA Simulation Debrief`.

Il frontend polla via `get_debrief(session_id)` e mostra i risultati in `SimulationDebrief.vue`.

### 5. Review docente (opzionale)

`instructor_review_debrief(session_id, review)` permette al docente di aggiungere una nota sopra il debrief AI (campo `instructor_review` su `LMSA Simulation Debrief`).

## Flusso B — Docente che crea/testa scenari

### 1. CRUD scenario: `ScenarioEditor.vue`

Form completo per `LMSA Simulation Scenario`:
- Header con breadcrumbs + bottoni "Compila con IA" / "Test simulazione" / "Salva"
- Sezioni: identità (nome, difficoltà), corso/lezione (Link autocomplete su `LMS Course` + `Course Lesson`), persona del personaggio (`roleplay_persona`), template situazione, obiettivi formativi (child table), seed variations (variabili randomizzate)
- Link allo schema di valutazione (`LMSA Evaluation Schema`)

Il salvataggio scrive su `LMSA Simulation Scenario`. La pubblicazione (`status = "Published"`) lo rende disponibile agli studenti via `list_my_scenarios`.

**Validazioni client-side** in `onSave` (vedi `ScenarioEditor.vue`):
- Campi obbligatori (`scenario_name`, `lms_course`, `roleplay_persona`, `situation_template`)
- `evaluation_schema` deve essere in lista (l'`Autocomplete` di frappe-ui accetta input libero — blocca prima di hit del backend)
- Normalizzazione di `lms_course`/`course_lesson`/`evaluation_schema` da `{label, value}` a stringa pura (Autocomplete scrive object al click utente, stringa quando popolato programmaticamente)
- Variabili `{var}` nel `situation_template` devono esistere nelle seed_variations

### 2. "Compila con IA" — generazione AI dello scenario

Bottone disabilitato finché `model.lms_course` non è selezionato. Click apre dialog inline con campo `hint` opzionale. Endpoint: `ai_generate_scenario(course, lesson?, hint?)` in `simulations/api.py`.

Il backend (`authoring_ai.generate_scenario_payload`):
1. Recupera contesto via RAG (`IngestionService.search_chunks_by_lessons` o `by_course`) — stesso path dell'`AuthoringEvaluationRunner.lesson_context`
2. Carica template prompt da `LMSA Prompt Template.scenario_generator_ai` (fallback ai default in `template_loader.DEFAULTS`)
3. Renderizza con `render_template(...)` sostituendo `{{course_name}}`, `{{lesson_title}}`, `{{lesson_context_block}}`, `{{hint}}`
4. LLM call con `response_format=JsonSchema(...)` strict (`SCENARIO_OUTPUT_SCHEMA`)
5. Ritorna dict pronto per il frontend

Il frontend riceve il payload e sostituisce **tutti** i campi del form (eccetto `lms_course`, `course_lesson`, `evaluation_schema`, `status`, `provider_override`/`model_override`). L'utente rivede e clicca "Salva" — nessun save automatico.

### 3. Schema di valutazione: `EvaluationSchemaEditor.vue` + `CriterionEditor.vue`

`LMSA Evaluation Schema` è una rubrica riusabile fra scenari. `EvaluationSchemaEditor` permette di:
- Creare/duplicare/esportare schemi (JSON)
- Aggiungere/ordinare criteri (`CriterionEditor` come accordion per ogni criterio)
- Ogni criterio ha: nome, descrizione, peso, indicatori positivi/negativi

Lo schema viene consumato dal **debrief judge** della pipeline eval (e dal `generate_debrief` job).

**Bottone "Compila con IA"** sempre attivo (course/lesson opzionali). Endpoint: `ai_generate_evaluation_schema(hint?, course?, lesson?)`. Stesso pattern dello scenario generator: hint testuale obbligatorio, RAG opzionale se viene fornito un corso, output strutturato via `EVAL_SCHEMA_OUTPUT_SCHEMA`. Sostituisce schema_name, description, scoring_scale, passing_threshold, criteria[].

### 4. Test simulazione: `SimulationTestDialog.vue`

Apre il dialog di QA pre-pubblicazione. Campi:
- **Profilo studente** (`competent` | `novice` | `off_topic` | `adversarial`, da `list_student_profiles`)
- **Numero conversazioni** (1-3, hard cap su `MAX_VARIANTS` in `eval/api.py`)
- **Brief dello studente** (textarea opzionale, sostituisce l'apertura del system prompt dell'LLM-student)

POST `run_simulation_test(scenario, student_profile, num_variants, student_scenario_brief?)`. L'endpoint crea un `LMSA Quality Evaluation` con `run_mode="simulation_test"` e fa partire `AuthoringEvaluationRunner(doc.name).run()` (sincrono — vedi sezione dedicata).

### 5. Risultati: `EvaluationResultsDialog.vue` + `EvaluationTraceCard.vue` + `DimensionScoreBar.vue`

- Polling su `get_evaluation_status` finché `status == "complete"`, poi `get_evaluation_result`
- Header con 4 `DimensionScoreBar` (persona, coverage, debrief, difficulty) — aggregate scores
- Lista di `EvaluationTraceCard` espandibili: 1 card per trace (= 1 variant)
- Ogni card mostra: punteggi per dimensione, summary del giudice, evidence_quotes, warnings
- Pulsante per aprire il transcript completo in `TranscriptDrawer` (riusa `ChatSession` read-only)

## Prompt configurabili dal Desk

Tutti i prompt LLM del sottosistema simulazioni sono configurabili dal Desk senza redeploy. Due doctype distinti per separare i prompt statici dai template parametrici:

### `LMSA Judge Prompt` — i 4 judge della valutazione

Doctype editabile dal Desk (System Manager + Moderator), un record per ogni judge:

| `purpose` | Cosa valuta |
|---|---|
| `judge_persona` | Il personaggio AI resta in carattere durante tutta la conversazione |
| `judge_coverage` | La conversazione ha coperto gli obiettivi formativi (per-obiettivo + score complessivo) |
| `judge_debrief` | Il debrief generato è accurato (no allucinazioni, coerenza score↔evidenze) |
| `judge_difficulty` | Difficoltà percepita matcha quella dichiarata (calibration_offset) |

Campi per record: `system_prompt` (Long Text), `output_schema` (Code JSON), `temperature`, `max_tokens`, `version`, `enabled`, `notes`.

`prompts/judge_loader.py` espone `load_judge_prompt(purpose)`: legge dal DB (se `enabled=1`), altrimenti ritorna il default hardcoded importato dai 4 judge module. Nessuna cache — il cost di un PK-lookup è irrilevante rispetto alla LLM call che ne consuma il risultato.

`pipeline._run_judge` chiama `load_judge_prompt(f"judge_{dimension}")` per ottenere system_prompt + output_schema + sampling params, e usa lo schema come `response_format=JsonSchema(...)` strict mode.

### `LMSA Prompt Template` — template parametrici

Doctype editabile dal Desk, un record per ogni template parametrizzato. I template usano sintassi `{{var}}` per i placeholder sostituiti runtime via `template_loader.render_template(template, ctx)` (str.replace; placeholder non trovati restano letterali, non vanno in errore).

Purposes attualmente seeded:

| `purpose` | Usato da | Placeholder disponibili |
|---|---|---|
| `llm_student` | `eval/student/llm_student.py:build_student_messages` | `{{scenario_brief}}`, `{{profile_addendum}}`, `{{scenario_name}}`, `{{difficulty}}`, `{{roleplay_persona}}`, `{{learning_objectives}}`, `{{lesson_block}}`, `{{transcript}}` |
| `scenario_generator_ai` | `authoring_ai.generate_scenario_payload` (bottone "Compila con IA") | `{{course_name}}`, `{{lesson_title}}`, `{{lesson_context_block}}`, `{{hint}}` |
| `evaluation_schema_generator_ai` | `authoring_ai.generate_evaluation_schema_payload` (bottone "Compila con IA") | `{{course_block}}`, `{{hint}}` |

Campi per record: `system_template`, `user_template`, `temperature`, `max_tokens`, `available_placeholders` (doc read-only), `version`, `enabled`.

`prompts/template_loader.py` espone `load_prompt_template(purpose)` con stesso pattern del judge_loader: DB → fallback hardcoded → mai un crash. Le DEFAULTS sono single-source-of-truth: a `bench migrate`, `setup.seed_prompt_templates()` crea i record dal DEFAULTS se mancanti (idempotente).

### Workflow per modificare un prompt
1. Desk → `LMSA Judge Prompt` o `LMSA Prompt Template` → record → modificare
2. Save: la modifica è immediatamente effettiva al prossimo call (no cache, no restart)
3. Bumpare il `version` per tracciare la modifica nel `judge_versions_json` dei trace (audit)
4. Per resettare al default hardcoded: `enabled=0` (soft) o cancellare il record (al prossimo migrate viene ri-seedato dal DEFAULTS)

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
    │    │   │   - odd:  RolePlayerTurnService.ask (role-player turn, stesso path di prod)
    │    │   └─ ritorna transcript
    │    ├─ _build_trace (crea LMSA Evaluation Trace con transcript_json)
    │    ├─ evaluate_transcript → 4 judges in sequenza
    │    ├─ _persist_trace_scores (dimension_scores_json sul trace)
    │    └─ save + commit (intermedio: ogni variant è persistita prima della successiva)
    ├─ _compute_aggregates (media per dimensione)
    ├─ status="complete" (o "failed" in except)
    └─ finally: save + commit + _publish (simulation:eval_complete realtime)
```

Vedi `runner.py` per il loop di alternanza studente/personaggio, `role_player.py` per le pure services condivise con la simulation di produzione, `judges/` per le 4 dimensioni.

## Componenti frontend — inventario

### Top-level (`simulations/`)

| File | Ruolo | Endpoint chiamati |
|---|---|---|
| `SimulationLauncherButton.vue` | Fab button nella view studente; carica scenari del corso | `list_my_scenarios` |
| `SimulationLauncher.vue` | Dialog di selezione scenario; start della sessione | `start_session` |
| `ChatSession.vue` | UI chat bidirezionale; riusata in live e read-only | `send_message`, `end_session` (via parent) |
| `ScenarioEditor.vue` | Form CRUD scenario; hub di azioni docente; bottone "Compila con IA" | `save_scenario`, `get_scenario`, `list_my_evaluation_schemas`, `ai_generate_scenario`, `start_session` (test run) |
| `EvaluationSchemaEditor.vue` | CRUD schemi di valutazione; bottone "Compila con IA" | `save_evaluation_schema`, `get_evaluation_schema`, `ai_generate_evaluation_schema` |
| `CriterionEditor.vue` | Accordion singolo criterio dentro lo schema | (nessuno — child editor) |
| `TranscriptDrawer.vue` | Dialog read-only trascrizione + debrief | `get_session`, `get_debrief` |

### Sotto `simulations/eval/`

| File | Ruolo | Endpoint chiamati |
|---|---|---|
| `SimulationTestDialog.vue` | Dialog "Test simulazione" (profile + num_variants + brief) | `list_student_profiles`, `run_simulation_test` |
| `EvaluationResultsDialog.vue` | Display risultati eval (polling + view) | `get_evaluation_status`, `get_evaluation_result` |
| `EvaluationTraceCard.vue` | Card espandibile per singolo trace | (nessuno — render-only) |
| `DimensionScoreBar.vue` | Barra grafica punteggio 0-1 per dimensione | (nessuno — render-only) |

## Backend touchpoints — endpoint chiave

`simulations/api.py` (whitelisted, lifecycle + studente + authoring AI):
- `start_session(scenario_id, modality)`
- `send_message(session_id, text)`
- `end_session(session_id, reason)`
- `get_session(session_id)`
- `get_debrief(session_id)` / `generate_debrief(session_id)` (manuale)
- `instructor_review_debrief(session_id, review)`
- `list_my_scenarios(course?)` / `list_scenarios(course?)`
- `get_scenario(name)` / `save_scenario(payload)` / `delete_scenario(name)`
- `list_my_evaluation_schemas()` / `get_evaluation_schema(name)` / `save_evaluation_schema(payload)` / `delete_evaluation_schema(name)`
- `ai_generate_scenario(course, lesson?, hint?)`
- `ai_generate_evaluation_schema(hint?, course?, lesson?)`
- `instructor_report(...)` (analytics per docente)

`simulations/eval/api.py` (whitelisted, authoring QA):
- `run_simulation_test(scenario, student_profile, num_variants, student_scenario_brief?)`
- `run_production_evaluation(session_id)` (valuta una sessione reale a posteriori)
- `get_evaluation_status(eval_id)` / `get_evaluation_result(eval_id)`
- `list_evaluations_for_scenario(scenario)` / `list_evaluations_for_session(session_id)`
- `list_student_profiles()`

## Doctypes coinvolti

| Doctype | Ruolo |
|---|---|
| `LMSA Simulation Scenario` | Definizione di uno scenario di simulazione (persona base del personaggio in `roleplay_persona`, situation template, learning_objectives, seed_variations, course_lesson, evaluation_schema) |
| `LMSA Simulation Session` | Una sessione di gioco umano↔AI. Immutabile dopo `submit` (lifecycle: In Progress → Completed/Abandoned/Error) |
| `LMSA Simulation Turn` | Turn-by-turn della sessione. Ogni doc è una battuta (user o assistant) con prompt metadata, latenza, token usage |
| `LMSA Simulation Debrief` | Debrief AI post-sessione. Child tables: criterion_scores, strengths, improvements, recommended_content |
| `LMSA Evaluation Schema` (+ `LMSA Schema Criterion` child) | Rubrica riusabile di criteri di valutazione |
| `LMSA Quality Evaluation` (+ `LMSA Evaluation Trace` child) | Run di valutazione (run_mode: `simulation_test` / `production` / `quick` / `deep`). Ogni trace è un transcript_json + dimension_scores_json + judge_versions_json |
| `LMSA Judge Prompt` | Prompt + output schema dei 4 judge, editabile dal Desk |
| `LMSA Prompt Template` | Template prompt parametrici (`{{var}}`) per `llm_student`, `scenario_generator_ai`, `evaluation_schema_generator_ai` |

## Configurazione

Da `LMSA Settings`:

| Campo | Uso |
|---|---|
| `simulations_enabled` | Gate globale: `SessionOrchestrator.start_session` throw se False |
| `simulation_chat_provider` | Provider per i turni del personaggio (`auto` → routing + fallback) |
| `simulation_debrief_provider` | Provider per debrief + eval judges + AI authoring |
| `simulation_chat_model` / `simulation_debrief_model` | Override modello concreto |
| `simulation_provider_fallback_order` | CSV: catena di fallback su rate-limit/server-error |
| `simulation_daily_quota_per_user` | Hook `validate_quota` su Simulation Session insert (0 = illimitato) |

Da `site_config.json`: nessuna chiave specifica per simulations (eredita la config provider LLM globale).

## Patches schema DB

Patches Frappe registrate in `apps/os_lms/os_lms/patches.txt` (pre_model_sync):

| Patch | Cosa fa |
|---|---|
| `v0_0_2.rename_lms_os_course_tag` | Rinomina doctype tag (storico, non-simulations) |
| `v0_0_3.rename_simulation_scenario_roleplay_persona` | Rinomina colonna `customer_persona` → `roleplay_persona` su `tabLMSA Simulation Scenario` (rename schema da "customer-only" a "role-player generico") |
| `v0_0_4.drop_golden_runs` | Cleanup feature golden run rimossa: cancella Quality Evaluation con `run_mode='golden_regression'`, droppa colonna `source_golden` da Evaluation Trace, cancella DocType `LMSA Scenario Golden Run` |

Tutte idempotenti: girano in `pre_model_sync` controllando l'esistenza prima di agire.

## Setup hooks

Da `setup.py` (chiamati in `hooks.after_migrate`):

| Funzione | Cosa fa |
|---|---|
| `seed_judge_prompts` | Crea i 4 record `LMSA Judge Prompt` dai default in `prompts/judge_loader.DEFAULTS` (idempotente: skip se già presente) |
| `seed_prompt_templates` | Crea i record `LMSA Prompt Template` dai default in `prompts/template_loader.DEFAULTS` (idempotente) |

I default hardcoded restano in modo che la app funzioni anche senza i record DB (fallback ricorsivo a ogni `load_judge_prompt` / `load_prompt_template`).

## Note operative

- **Real-time eventi**: `SessionOrchestrator` pubblica `simulation:turn_start` / `simulation:turn_complete` / `simulation:error` su `frappe.publish_realtime`, scoped allo studente. Eval runner pubblica `simulation:eval_complete`. Il frontend subscriva per UI progressiva.
- **Quota**: `validate_quota` (hook `before_insert` su `LMSA Simulation Session`) blocca lo studente che ha esaurito la quota giornaliera.
- **Injection defense**: ogni `user_text` in `send_message` passa per `detect_injection` (`prompts/defense.py`); attacchi rilevati ricevono una risposta canned **in carattere** (`in_character_refusal(persona.name)`) e il turn user viene flaggato (`injection_attempt_detected = 1`) per audit. Il pattern matcher copre anche "personaggio" oltre a "cliente" per coprire scenari non-vendita.
- **Prompt versioning**: ogni sessione persiste `prompt_version = "{SCENARIO_GEN_VERSION}+{ROLE_PLAY_VERSION}"` (es. `gen.v1+rp.v1`). I judge versions vengono persistiti in `judge_versions_json` su ogni trace per audit. Bumpare il `version` di un `LMSA Judge Prompt` o `LMSA Prompt Template` traccia automaticamente la modifica nei trace successivi.
- **Pseudonymizzazione**: `SessionOrchestrator.pseudonymize_session_id(user)` ritorna SHA-256 dello user — usato quando si inviano payload a provider esterni per evitare di esporre email.
- **LLM call logging (debug)**: `eval/authoring_runner.py` wrappa il provider con `LoggingProvider` se `utils/llm/logger.ENABLED = True`. Tutti i call dell'eval finiscono in `{site}/private/files/llm_logs/{eval_id}.jsonl`. Disabilitato di default. Inoltre `pipeline._log_judge_failure` registra ogni judge fallito (parse_error o provider_error) sul `Error Log` Desk con `response.text` raw — chiave per debuggare modelli che non rispettano lo strict response_format.
- **Asimmetria student/role-player nell'eval**: il role-player turn passa per `RolePlayerTurnService` (stesso codepath della produzione), lo student turn è inline nel runner (non c'è analogo lato prod perché lì lo studente è umano). Il role-player è quindi cover-tested anche dall'eval; lo student turn no.
- **`Autocomplete` di frappe-ui**: il `v-model` riceve un object `{label, value}` quando l'utente seleziona dalla dropdown, ma una stringa pura quando popolato programmaticamente (response API / set programmatic). I form normalizzano via `unwrapAutocomplete` prima di submit per evitare di mandare object al backend (causerebbe `LinkValidationError` o `[object Object]` su `frappe.throw`).
- **Helper `__()` di translation**: in `frontend/src/translation.js` ritorna **string** senza placeholder, ma **object** `{format: fn}` con placeholder `{N}`. Per stringhe con placeholder: `__('Errore: {0}').format(arg)` — la sintassi Python-style `__('text {0}', [arg])` ritorna un object e finisce nei toast come "[object Object]".

## File rilevanti (cheat sheet)

| Layer | File |
|---|---|
| Frontend (studente) | `frontend/src/oslms/components/simulations/SimulationLauncherButton.vue`, `SimulationLauncher.vue`, `ChatSession.vue` |
| Frontend (docente) | `ScenarioEditor.vue`, `EvaluationSchemaEditor.vue`, `CriterionEditor.vue`, `TranscriptDrawer.vue` |
| Frontend (eval/QA) | `eval/SimulationTestDialog.vue`, `eval/EvaluationResultsDialog.vue`, `eval/EvaluationTraceCard.vue`, `eval/DimensionScoreBar.vue` |
| Backend API | `apps/os_lms/os_lms/os_lms/ai/simulations/api.py`, `simulations/eval/api.py` |
| Orchestrazione prod | `simulations/orchestrator.py` (SessionOrchestrator) |
| Pure services | `simulations/role_player.py` (ScenarioVariantGenerator, RolePlayerTurnService) |
| AI authoring | `simulations/authoring_ai.py` (generate_scenario_payload, generate_evaluation_schema_payload) |
| Prompts statici | `simulations/prompts/scenario_generator.py`, `role_play.py`, `debrief.py`, `defense.py` |
| Prompt loaders | `simulations/prompts/judge_loader.py`, `simulations/prompts/template_loader.py` |
| Debrief job | `simulations/tasks.py:generate_debrief` |
| Eval orchestration | `simulations/eval/authoring_runner.py`, `eval/jobs.py` |
| Eval transcript gen | `simulations/eval/runner.py` (run_synthetic_llm_student) |
| Eval judges | `simulations/eval/judges/persona.py`, `coverage.py`, `debrief.py`, `difficulty.py` |
| Eval student helpers | `simulations/eval/student/llm_student.py`, `profiles.py` |
| Eval pipeline | `simulations/eval/pipeline.py` (`_run_judge` + `_log_judge_failure`) |
| LLM call logger (debug) | `apps/os_lms/os_lms/os_lms/ai/utils/llm/logger.py` |
| Permessi | `simulations/eval/permissions.py` |
| Setup seed | `apps/os_lms/os_lms/setup.py` (`seed_judge_prompts`, `seed_prompt_templates`) |
| Patches DB | `apps/os_lms/os_lms/patches/v0_0_3/rename_simulation_scenario_roleplay_persona.py`, `v0_0_4/drop_golden_runs.py` |
