# os_lms → lms : mappa delle modifiche

Documento di riferimento per chiunque debba capire **cosa fa `os_lms` al modulo `lms`** (Frappe Learning upstream). Sorgenti citate sono percorsi assoluti relativi alla root del repo.

> Convenzione: in tabella, "Override" = sostituisce un'API LMS esistente; "Estende" = aggiunge campi/dati al payload di un'API LMS senza cambiare contratto principale; "Aggiunge" = nuova entità.

---

## 1. App registration

| Voce | Valore | File |
| --- | --- | --- |
| Nome app | `os_lms` | `apps/os_lms/os_lms/hooks.py` |
| Dipendenza richiesta | `lms` (`required_apps = ["lms"]`) | idem |
| Template HTML base | `templates/base.html` (override del template Frappe per iniettare brand CSS) | `apps/os_lms/os_lms/templates/base.html` |
| CSS Desk injectato | `/api/method/os_lms.os_lms.branding.brand_css` (servito dinamicamente da `Brand Customize` doctype) | `apps/os_lms/os_lms/os_lms/branding.py` |
| Hook pre-request | `os_lms.debug.active_debug` (attiva debugpy quando `DEBUG_MODE=1`) | `apps/os_lms/os_lms/debug.py` |

---

## 2. API REST overridate (`override_whitelisted_methods`)

Ogni voce sostituisce la funzione `lms.*` con la versione `os_lms.os_lms.override_*`. Il path REST esposto resta lo stesso (`/api/method/lms.lms.api.*`), quindi il **frontend upstream non sa di parlare con `os_lms`**.

| Metodo LMS originale | Override `os_lms` | Cosa cambia |
| --- | --- | --- |
| `lms.lms.api.get_sidebar_settings` | `override_api.get_sidebar_settings` | Aggiunge i campi sidebar dell'estensione `LMS Settings`: `programs`, `home`, `search`, `quizzes`, `assignments` |
| `lms.lms.api.get_lms_settings` | `override_api.get_lms_settings` | Aggiunge nel payload globale `ai_enabled` (RAG tutor) e `simulations_enabled` (feature simulazioni AI) letti da `LMSA Settings` |
| `lms.lms.api.get_announcements` | `override_api.get_announcements` | Permission gating per studenti: vedono solo gli annunci batch in cui sono destinatari (recipients/cc/bcc); paginazione esplicita `{data, total}`. Moderator/Batch Evaluator vedono tutto |
| `lms.lms.api.get_notifications` | `override_api.get_notifications` | Arricchisce le notifiche `LMS Live Class` con titolo/data/ora/durata della live class |
| `lms.lms.api.get_user_info` | `override_api.get_user_info` | Aggiunge il flag `welcome_video_seen` (Custom Field su `User`) |
| `lms.lms.api.save_role` | `override_api.save_role` | Aggiunge il supporto ai ruoli custom **`Gestore`** e **`Docente`** (gestiti via `Has Role`); per gli altri ruoli delega all'originale |
| `lms.command_palette.search_sqlite` | `override_api.search_sqlite` | Usa `CustomLearningSearch` (sotto) e raggruppa per `LMS Course / LMS Batch / Job Opportunity / LMS Program / LMS Quiz / LMS Assignment / Course Lesson` con permission gating per ruolo |
| `lms.lms.utils.get_course_details` | `override_utils.get_course_details` | Aggiunge `feature_sections` (JSON deserializzato da custom field) e `hero` (`{enabled, media_type, media_url}`) |
| `lms.lms.utils.get_courses` | `override_utils.get_courses` | Aggiunge `total_minutes` per ciascun corso (somma durate Course Lesson) |
| `lms.lms.utils.get_lesson` | `override_utils.get_lesson` | Aggiunge: `tags`, `lesson_access`/`quiz_access` (regole di accesso lezione per lezione), `simulations` (array di scenari Published agganciati a questa lezione, fallback a course-level) |
| `lms.lms.utils.get_lesson_creation_details` | `override_utils.get_lesson_creation_details` | Aggiunge nei campi della lezione: `index_status`, `indexed_at` (RAG), `tags` |
| `lms.lms.utils.get_batch_details` | `override_utils.get_batch_details` | Aggiunge `custom_feature_sections` (JSON deserializzato) e `tab_notifications` (contatori unread per tab del batch) |
| `lms.lms.utils.get_roles` | `override_utils.get_roles` | Aggiunge i due flag custom `manager` e `instructor` (presenza dei ruoli `Gestore` / `Docente`) |

Funzioni **nuove** (non override) esposte da `override_api.py`:

- `os_lms.os_lms.override_api.get_new_courses` — 6 corsi più recenti, ordinati per `published_on` desc
- `os_lms.os_lms.override_api.get_most_followed_courses` — 6 corsi con più iscrizioni

---

## 3. Doctype LMS override (`override_doctype_class`)

| Doctype | Override class | File | Comportamento |
| --- | --- | --- | --- |
| `Email Account` (Frappe) | `CustomEmailAccount` | `apps/os_lms/os_lms/overrides/email_account.py` | Bypassa il check ESMTP SIZE quando il server lo dichiara a 0 (fix per server SMTP che restituiscono size=0 erroneamente, bloccando email con allegati) |
| `Data Import` (Frappe) | `CustomDataImport` | `apps/os_lms/os_lms/overrides/data_import.py` | Pre-elabora il CSV prima dell'import: espande colonne speciali per `LMS Course` (`course_column_expanders`) e `LMS Batch Enrollment` (`enrollment_column_expanders`) — abilita formati CSV custom per il workflow del cliente |
| `LMS Live Class` (LMS) | `CustomLMSLiveClass` | `apps/os_lms/os_lms/overrides/lms_live_class.py` | Override completo di `build_event_description` (italiano), gestione duale Zoom/Google Meet, reminder schedulati via doctype custom `LMS Live Class Reminder` |

---

## 4. Doctype LMS estesi via Custom Field (`fixtures/custom_field.json`)

I custom field vengono caricati come fixtures Frappe (e replicati programmaticamente in `setup.create_custom_fields`).

### `LMS Course` (6 campi aggiunti)

| Field | Tipo | Insert after | Scopo |
| --- | --- | --- | --- |
| `enforce_lesson_order` | Check | `disable_self_learning` | Forza ordine sequenziale delle lezioni |
| `enforce_quiz_on_completion` | Check | `enforce_lesson_order` | Richiede quiz superato per completare la lezione |
| `simulations_enabled` | Check | `enforce_quiz_on_completion` | Attiva la feature simulazioni AI per il corso (espone scenari pubblicati a studenti iscritti) |
| `hero_enabled` | Check | `enforce_quiz_on_completion` | Abilita hero media nella course page |
| `hero_media_type` | Select | `hero_enabled` | Video / Image |
| `hero_media_url` | Data | `hero_media_type` | URL/path del media hero |

Inoltre il file `feature_sections` (Long Text) viene aggiunto via `setup.create_custom_fields` (non da fixture) per le sezioni feature personalizzate della pagina corso.

### `Course Lesson` (4 campi)

| Field | Tipo | Scopo |
| --- | --- | --- |
| `duration` | Data | Durata stimata (usata da `get_courses.total_minutes`) |
| `index_status` | Select | Stato pipeline RAG (`pending` / `processing` / `indexed` / `failed`) |
| `indexed_at` | Datetime | Timestamp ultimo successo ingest |
| `tags` | Small Text | Tag liberi per ricerca/filtro |

### `LMS Settings` (10 campi)

Sidebar items (toggle visibilità): `programs`, `home`, `search`, `quizzes`, `assignments`.

Welcome video onboarding: `welcome_video_section`, `welcome_video_enabled`, `welcome_video_title`, `welcome_video_subtitle`, `welcome_video_file`.

### `LMS Batch` (1 campo)

| Field | Tipo | Scopo |
| --- | --- | --- |
| `custom_feature_sections` | Long Text | JSON delle feature sections custom della batch page |

### `LMS Live Class` (3 campi)

| Field | Tipo | Scopo |
| --- | --- | --- |
| `reminders_section` | Section Break | Header sezione reminder |
| `reminders` | Table → `LMS Live Class Reminder` | Schedulazione reminder via doctype child custom |
| `started_at` | Datetime | Timestamp avvio effettivo della live |

### `User` (2 campi)

| Field | Tipo | Scopo |
| --- | --- | --- |
| `welcome_video_seen` | Check | Tracciamento utenti che hanno visto il welcome video |
| `first_login` | Check | Flag transitorio settato a 1 all'`after_insert` e azzerato a `on_session_creation` |

### `LMS Program` (1 campo)

| Field | Tipo | Scopo |
| --- | --- | --- |
| `description` | Text Editor | Descrizione rich-text del programma |

---

## 5. Eventi doctype LMS agganciati (`doc_events`)

| Doctype | Evento | Handler `os_lms` | Effetto |
| --- | --- | --- | --- |
| `Badge` (Frappe) | `after_insert` | `os_lms.badge_utils.clear_cache_on_badge_create` | Fix workaround a un bug di cache su creazione badge |
| `Course Lesson` | `before_save` | `os_lms.events.lesson.reset_index_status_on_content_change` | Riporta `index_status` a `pending` quando il body della lezione cambia (rigenera embedding RAG al prossimo cron) |
| `User` | `after_insert` | `os_lms.auth.mark_first_login` | Imposta `first_login=1` per gli utenti appena creati |
| `LMS Live Class` | `before_save` | `os_lms.os_lms.live_class_reminders.reset_sent_at` | Reset stato reminder quando la live class viene modificata |
| `Brand Customize` (custom) | `on_update` | `os_lms.os_lms.branding.clear_brand_cache` | Invalida cache CSS al cambio brand |
| `LMSA Simulation Session` (custom) | `before_insert` | `os_lms.os_lms.ai.simulations.orchestrator.validate_quota` | Enforce quota giornaliera simulazioni per studente |

Hook **`on_session_creation`** → `os_lms.auth.on_session_creation`: al primo login dopo l'`after_insert`, se `welcome_video_enabled` in `LMS Settings`, crea una notifica di benvenuto.

---

## 6. Search (`sqlite_search`)

`CustomLearningSearch` (estende `lms.sqlite.LearningSearch`) aggiunge questi doctype all'indice di ricerca command-palette LMS, ognuno con i suoi fields:

- `LMS Course` — title + description, category, tags
- `LMS Program` — title
- `LMS Quiz` — title
- `LMS Assignment` — title + question
- `Course Lesson` — title + body + tags

LMS upstream indicizza solo `Job Opportunity` e `LMS Batch`; `os_lms` estende la ricerca a tutta la struttura formativa.

---

## 7. Email template overridati (`standard_email_override`)

| Template originale | Override |
| --- | --- |
| `login_via_key` | `os_lms/templates/emails/login_via_key.html` (testo italiano + branding) |

---

## 8. Frontend — componenti aggiunti a pagine LMS upstream

Il frontend Vue 3 SPA è quello di `lms` (`frontend/src/`); `os_lms` **non lo forka** ma inietta componenti nelle pagine esistenti via `import` diretto da `@/oslms/`.

### `Lesson.vue` (pagina lezione studente)
- **Inietta**: `ChatBot.vue` (tutor RAG) — visibile se `ai_enabled` e lezione senza quiz attivo
- **Inietta**: `SimulationLauncher.vue` + bottone "Avvia simulazione" — visibile se `simulations_enabled` e la lezione espone scenari pubblicati

### `Courses/CourseDetail.vue` (pagina corso lato admin)
- **Aggiunge tab "Simulations"** (4ª tab) — visibile a admin/instructor quando `simulations_enabled` global. Renderizza `CourseSimulations.vue` con KPI per stato e tabella scenari del corso

### `Home/Home.vue` e `Home/StudentHome.vue`
- Sezioni feature personalizzate, course tag badges (`@/oslms/components/CourseTagBadges.vue`)

### `LessonForm.vue` / `CourseDashboard.vue` / `Batches/BatchForm.vue` / `QuizForm.vue` / `ProfileRoles.vue`
- Vari composable e widget custom da `@/oslms/composables/` e `@/oslms/components/`

### Plugin Vite `osOverrideTheme` (in `frontend/vite.config.js`)
Permette di **rimpiazzare componenti da `node_modules/`** (es. `frappe-ui`) senza forkare il pacchetto. File presenti in `frontend/src/overrides/`:

| Componente sovrascritto | File override |
| --- | --- |
| `frappe-ui/frappe/Link/Link.vue` | `frontend/src/overrides/frappe-ui/frappe/Link/Link.vue` |
| `frappe-ui/src/components/ListView/ListSelectBanner.vue` | `frontend/src/overrides/frappe-ui/src/components/ListView/ListSelectBanner.vue` |

### Pagine totalmente nuove (non override LMS)
- `pages/Simulations/SimulationPlay.vue` — chat sessione simulazione (rotta `/simulations/:sessionId`)
- `pages/Simulations/SimulationDebrief.vue` — debrief post-sessione (rotta `/simulations/:sessionId/debrief`)
- `pages/Simulations/InstructorReports.vue` — pannello docente (rotta `/simulations/admin`)
- `pages/Courses/CourseSimulations.vue` — tab inline su `CourseDetail`
- Componenti `@/oslms/components/simulations/*` (ChatSession, SimulationLauncher, ScenarioEditor, EvaluationSchemaEditor, TranscriptDrawer)
- Composables `@/oslms/composables/*` (`useSimulationSession`, `useSimulationDebrief`, `useLessonIngestion`)

---

## 9. Scheduler events

| Frequenza | Handler | Effetto |
| --- | --- | --- |
| `daily` | `os_lms.os_lms.ai.scheduler.reindex_lesson_content` | Re-indicizza le lezioni con `index_status` `pending`/`null`/`""` nella pipeline RAG |
| `cron */15 * * * *` | `os_lms.os_lms.live_class_reminders.send_live_class_reminders` | Invia reminder schedulati per le live class (tabella custom `reminders` su `LMS Live Class`) |

---

## 10. After-migrate hooks (`after_migrate`)

Eseguiti dopo `bench migrate`:

1. `os_lms.setup.ensure_italian_language` — Garantisce che la `Language` italiana sia presente e abilitata
2. `os_lms.setup.remove_deprecated_custom_fields` — Pulizia di custom field deprecati (es. `LMS Course-learning_items`)
3. `os_lms.setup.create_custom_fields` — Crea i custom field non gestiti da fixtures (es. `LMS Course.feature_sections`, `User.codice_fiscale`)
4. `os_lms.setup.create_redis_index` — Crea l'indice vector store su Redis (RAG)
5. `os_lms.setup.rebuild_search_index` — Ricostruisce l'indice SQLite di ricerca con i nuovi doctype indicizzabili

---

## 11. Ruoli aggiunti

Due ruoli LMS extra usati nelle override:

- **`Gestore`** — Manager del cliente; gestito separatamente in `save_role`/`get_roles`
- **`Docente`** — Instructor del cliente; idem

Sono inseriti nel doctype `Has Role` su `User` e vengono ritornati dalle override come flag booleani `manager`/`instructor` (oltre ai ruoli LMS standard `LMS Student`, `LMS Instructor`, `Course Creator`, `Moderator`).

---

## 12. Doctype custom **aggiunti** (non override, ma estendono il dominio LMS)

Riferimento rapido — tutti hanno prefisso `LMS …`, `LMS OS …` o `LMSA`.

### Branding & personalizzazione
- `Brand Customize` — Single, contiene logo + variabili CSS theme

### AI / RAG tutor
- `LMSA Settings` — Single con config AI (provider LLM/STT/TTS, chiavi API, parametri RAG)
- `LMSA Query Log` — Audit query studente al tutor
- `LMSA Transcript Cache` — Cache trascrizioni video (YouTube, Vimeo)

### AI Simulations (Sprint 1-4 della feature)
- `LMSA Simulation Scenario` (+ child `LMSA Simulation Learning Objective`, `LMSA Simulation Seed Variation`)
- `LMSA Evaluation Schema` (+ child `LMSA Schema Criterion`)
- `LMSA Simulation Session` (submittable) (+ child via Link `LMSA Simulation Turn`)
- `LMSA Simulation Debrief` (+ child `LMSA Criterion Score`, `LMSA Debrief Strength`, `LMSA Debrief Improvement`, `LMSA Debrief Recommendation`)

### Domini accessori
- `LMS Live Class Reminder` — child di `LMS Live Class` per la schedulazione reminder
- `LMS Course Learning Item` — child per le feature sections del corso
- `LMS OS Tag`, `LMS OS Course Tag` — tag riusabili tra corsi
- `Vimeo Settings` — credenziali API Vimeo per il transcriber

---

## 13. Domini esterni integrati (non override LMS ma collegati)

| Servizio | Dove integrato | Note |
| --- | --- | --- |
| OpenAI / Gemini / DeepSeek / Anthropic | `apps/os_lms/os_lms/os_lms/ai/utils/llm/providers/` | Layer provider-agnostico; selezione runtime da `LMSA Settings` |
| Vimeo API | `apps/os_lms/os_lms/os_lms/ai/utils/transcriber/vimeo.py` | Estrazione text tracks per il RAG |
| YouTube Transcript API | `apps/os_lms/os_lms/os_lms/ai/utils/transcriber/youtube.py` | Trascrizioni caption per il RAG |
| RediSearch / redisvl | `apps/os_lms/os_lms/os_lms/ai/utils/rag/redis_rag_storage.py` | Vector store per gli embedding RAG |
| Zoom / Google Meet | `apps/os_lms/os_lms/overrides/lms_live_class.py` | Gestione duale provider per le live class |

---

## 14. Cosa NON viene toccato in `lms` upstream

Per orientamento — il modulo `lms` resta intatto per:

- DocType core LMS (`LMS Course`, `Course Lesson`, `LMS Batch`, `LMS Quiz`, `LMS Assignment`, `LMS Certificate`, `LMS Payment`, ecc.) — solo custom field aggiunti, mai modificati i field originali
- Tabelle DB upstream — i custom field stanno in colonne dedicate
- File JS/CSS del bundle `lms` — `os_lms` aggiunge solo asset propri e override Vite del solo `frappe-ui`
- Endpoint REST non listati in §2 — il routing Frappe risolve direttamente alla funzione originale `lms.*`
- File `requirements.txt` di `lms` — `os_lms` ha il suo `pyproject.toml` con dipendenze separate (`redisvl`, `numpy`, `youtube_transcript_api`, ecc. + optional extras per provider AI)

---

## 15. Diagramma riepilogativo

```
┌──────────────────────────────────────────────────────────────┐
│                      Frappe LMS (upstream)                   │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │  API    │  │ DocTypes │  │ Frontend │  │  Templates   │   │
│  │  REST   │  │  + perms │  │   Vue    │  │   email      │   │
│  └────┬────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘   │
└───────┼────────────┼─────────────┼───────────────┼───────────┘
        │ override   │ extend      │ import-inject │ override
        ▼            ▼             ▼               ▼
┌──────────────────────────────────────────────────────────────┐
│                            os_lms                            │
│  override_api / override_utils      doc_events + scheduler   │
│  override_doctype_class             permission hooks         │
│  fixtures custom_field              osOverrideTheme Vite     │
│                                                              │
│  + nuovi DocType: Brand Customize, LMSA Settings/Scenario/   │
│    Session/Turn/Debrief/Evaluation Schema/…, LMS OS Tag, …   │
│  + nuove pagine: /simulations/* , tab in CourseDetail, …     │
│  + provider AI agnostico (LLM, STT, TTS)                     │
└──────────────────────────────────────────────────────────────┘
```

---

*Ultimo aggiornamento: 2026-05-19 — vedi `git log apps/os_lms` per il cronologico delle modifiche puntuali.*
