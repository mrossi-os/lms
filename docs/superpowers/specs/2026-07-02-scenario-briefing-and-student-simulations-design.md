# Scenario briefing (two-phase start) + student simulations tab

**Date:** 2026-07-02
**Status:** Approved design, pending implementation plan
**Area:** `apps/os_lms` (backend) + `frontend/src/oslms` (frontend)

## Problem

When a student starts an AI simulation today, the flow generates a scenario
variant and **immediately** drops the student into the conversation with the AI
role-player. The student is given no explanation of the situation or of what
they are supposed to accomplish, so they do not know how to begin.

There is also no place for a student to see the simulations they have run for a
course, review results, or resume/restart a session. Prepared-but-never-started
sessions (see the new `Ready` state below) would otherwise dangle with no way to
resume them.

## Goals

1. Split simulation start into **two phases**: (1) generate the variant and show
   the student a briefing describing what they must do, then (2) begin the
   actual AI session on an explicit action.
2. Once started, keep the briefing visible next to the conversation (chat on the
   left, briefing on the right; voice mirrors this).
3. Add a **student "Simulazioni" tab** on the course page listing the student's
   own sessions with status, plus the ability to start new simulations, restart
   completed ones, and continue pending ones.

## Non-goals

- Reworking the instructor-facing `CourseSimulations.vue` panel (untouched).
- Resuming live voice audio for an interrupted `In Progress` voice session
  (not technically feasible — audio is never persisted). Such sessions are
  review-only.

## Key decisions (from brainstorming)

- **Briefing content:** situation + who the student faces (name/role/context) +
  the student's goal. It **must not reveal** `hidden_motivation` or
  `key_objection` — those stay hidden to preserve the challenge.
- **`both` modality:** the briefing dialog shows two buttons, *Avvia chat* and
  *Avvia voce*. (Fixes the current bug where a `both` scenario silently falls
  through to chat.)
- **Variant generation timing:** generate the variant **once** in phase 1,
  persist it on the session, and reuse it in phase 2. No double LLM call.
- **Restart of a completed session:** clone the session reusing the **same
  variant** (persona/situation/brief) so the student retries the identical
  challenge to improve.
- **Student tab scope:** the tab both lists past/pending sessions **and** lets
  the student start new simulations (scenario picker + history in one place).

---

## Current architecture (baseline)

- **Variant schema** `SCENARIO_SCHEMA` in
  `apps/os_lms/os_lms/os_lms/ai/simulations/prompts/scenario_generator.py`:
  `{situation, persona:{name, role, context, mood, key_objection,
  hidden_motivation}}`. Dataclasses `PersonaVariant`, `ScenarioVariant`;
  parser `parse_scenario_generator_output`; message builder
  `build_scenario_generator_messages`.
- **Prompt template** (default) `ai/utils/default_prompt/scenario_variant_generator.py`
  (`VERSION = "gen.v1"`), DB-overridable via `LMSA Prompt Template`
  (purpose `scenario_variant_generator`).
- **Generation call** `ScenarioVariantGenerator.generate` in
  `ai/simulations/role_player.py`.
- **Orchestrator** `ai/simulations/orchestrator.py`:
  - `start_session(scenario, modality)` — resolve provider, generate variant,
    create `LMSA Simulation Session` (`In Progress`) with
    `generated_situation`/`generated_persona`, **persist first role-player turn**
    (`_first_roleplay_line`), commit.
  - `start_voice_session(...)` — same generation but no first turn; currently
    **regenerates its own variant**.
  - `end_session(...)`.
- **API** `ai/simulations/api.py`: `start_session`, `send_message`,
  `end_session`, `get_session` (returns `generated_persona`,
  `generated_situation`), `list_scenarios` (student-facing),
  `list_my_scenarios` (instructor-scoped), `instructor_report`, scenario CRUD.
  `ai/realtime/api.py`: `create_voice_session(scenario_id)`,
  `persist_transcript_turn`, `end_voice_session`.
  Access gate: `load_session(session_id)` allows moderator / owning student /
  course instructor.
- **Session doctype** `LMSA Simulation Session`: `student`, `scenario`,
  `course` (`fetch_from: scenario.lms_course`), `modality` (chat/voice),
  `status` (In Progress / Completed / Abandoned / Error / Needs Review),
  `started_at`, `ended_at`, `turn_count`, `seed`, `prompt_version`,
  `generated_situation`, `generated_persona`. `LMSA Simulation Debrief` holds
  `overall_score`/`passed`, linked by `session`.
- **Frontend:** `SimulationLauncher.vue` (scenario cards + *Avvia*),
  `SimulationLauncherButton.vue` (floating), `SimulationPlay.vue` +
  `useSimulationSession.js` + `ChatSession.vue` (chat runtime),
  `VoiceSession.vue` + `useRealtimeSession.js` (voice runtime).
  Routes in `frontend/src/router.js`: `SimulationPlay`
  (`/simulations/:sessionId`), `SimulationDebrief`
  (`/simulations/:sessionId/debrief`).
  Course tabs are built in `frontend/src/pages/Courses/CourseDetail.vue`;
  students currently get no tabs (`showTabs = isAdmin || isValutatore`) and see
  the full-page `CourseOverview`.

---

## Part A — Two-phase start with student briefing

### A1. New AI-generated field `student_brief`

`ai/simulations/prompts/scenario_generator.py`
- Add `student_brief` to `SCENARIO_SCHEMA` as a **top-level required** string
  property, with a description constraining it to: 2nd person, describe the
  situation, the counterpart (name/role/context) and the student's goal;
  **never** mention `hidden_motivation` or `key_objection`.
- Add `student_brief: str` to the `ScenarioVariant` dataclass.
- Extend `parse_scenario_generator_output` to read/validate `student_brief`.

`ai/utils/default_prompt/scenario_variant_generator.py`
- Extend `SYSTEM_TEMPLATE`/`USER_TEMPLATE` instructing generation of
  `student_brief` with the no-spoiler rule above.
- Bump `VERSION = "gen.v2"`; raise `MAX_TOKENS` to accommodate the extra text.

### A2. Session doctype

`LMSA Simulation Session`
- Add field `student_brief` (Long Text, read-only).
- Add `Ready` to the `status` Select options (variant generated, awaiting the
  student's explicit start). Lifecycle: `Ready → In Progress` on begin.

### A3. Orchestrator refactor

`ai/simulations/orchestrator.py` — split `start_session` into:
- `prepare_session(scenario, modality) -> {session, brief, modality}`: resolve
  provider, generate variant once, create session in status `Ready` with
  `generated_situation` / `generated_persona` / `student_brief` / `seed` /
  `prompt_version`. **No first turn.**
- `begin_chat_session(session_id) -> {first_turn}`: load the `Ready` session,
  persist the first role-player turn from the **stored** persona
  (`_first_roleplay_line`), set `In Progress`, commit.
- `start_voice_session(session_id)`: load the prepared session and reuse its
  stored persona to build realtime instructions (no regeneration); set
  `In Progress`.

Keep `_generate_variant`, `_first_roleplay_line`, `end_session` intact.

### A4. API

`ai/simulations/api.py`
- `prepare_session(scenario_id: str, modality: str = "chat") -> dict`
  → `{session_id, brief, modality}`. Gates: scenario Published; requested
  modality compatible with `scenario.modality` (including `both`); student
  enrolled (same rule as `list_scenarios`).
- `begin_session(session_id: str) -> dict` → `{first_turn}`. Owner-only.
- `get_session` return payload gains `student_brief`.
- Remove `start_session`; update the single caller (`SimulationLauncher.vue`).

`ai/realtime/api.py`
- `create_voice_session(session_id: str) -> dict` (was `scenario_id`): reads the
  prepared session, reuses its persona; unchanged return descriptor.

### A5. Frontend runtime layout

- `SimulationPlay.vue` / `ChatSession.vue`: two-column layout — chat on the
  left, `student_brief` panel on the right (from `get_session`).
- `VoiceSession.vue` / `useRealtimeSession.js`: `start(sessionId)` →
  `create_voice_session({session_id})`; brief panel on the right, voice controls
  on the left.

---

## Part B — Student "Simulazioni" tab

### B1. Backend

`ai/simulations/api.py`
- `list_my_sessions(course: str | None = None) -> list[dict]`: sessions where
  `student == frappe.session.user` (optionally filtered by `course`), left-joined
  with `LMSA Simulation Debrief` for `overall_score` / `passed` /
  `debrief_status`. Row fields: `name`, `scenario`, `scenario_name`, `modality`,
  `status`, `started_at`, `ended_at`, `turn_count`, `overall_score`, `passed`,
  `debrief_status`. Sorted by `started_at DESC`.
- `clone_session(session_id: str) -> dict` → `{session_id, brief, modality}`:
  owner-checked via `load_session`; create a **new `Ready` session** copying the
  source session's `scenario`, `modality`, `generated_situation`,
  `generated_persona`, `student_brief`, `seed`, `prompt_version` (same variant).
  No turns.

### B2. `CourseDetail.vue`

- Enable the tabbed layout for **enrolled students** (`course.data.membership`,
  non-admin) when `simulationsEnabledGlobal`: tabs = `[Overview, Simulazioni]`.
  Admin tab set unchanged; instructor `CourseSimulations.vue` untouched.
- Register a new student component `CourseStudentSimulations.vue` for the
  `simulations` tab in the student branch.

### B3. `CourseStudentSimulations.vue` (new)

- **Available scenarios** (`list_scenarios(course)`): cards with **Avvia** →
  `prepare_session` → briefing dialog → begin.
- **My sessions** (`list_my_sessions(course)`): table with status badge, score,
  and per-status actions:
  - `Completed` / `Abandoned` / `Error` / `Needs Review` → **Rivedi**
    (`SimulationDebrief`) and **Riavvia** (`clone_session` → briefing → begin).
  - `Ready` → **Continua** (`get_session` brief → briefing → begin). Drains
    dangling prepared sessions.
  - `In Progress` + chat → **Riprendi** (`SimulationPlay`, hydrates turns).
  - `In Progress` + voice → **Rivedi trascrizione** only (no live resume).

### B4. Shared briefing UI

- New `SimulationBriefing.vue`: renders `student_brief` + a start action.
  For `both` modality shows **Avvia chat** and **Avvia voce**; otherwise a
  single button matching the modality.
- Reused by `SimulationLauncher.vue` (new start), and by the tab's *Avvia*,
  *Riavvia*, and *Continua* paths. Start handlers: chat → `begin_session` then
  route `SimulationPlay`; voice → open `VoiceSession` with the session id.

---

## Testing

- `scenario_generator` parsing: `student_brief` present/valid; missing field
  handled by the existing corrective retry.
- `prepare_session`: creates a `Ready` session with brief and **no** turns.
- `begin_session`: adds the first role-player turn, transitions to
  `In Progress`.
- `clone_session`: new `Ready` session copies the source variant fields; owner
  enforced.
- `list_my_sessions`: returns only the caller's sessions; course filter works;
  debrief score join correct.

## Risks / notes

- `prompt_version` bump (`gen.v2`) means older sessions carry `gen.v1`; purely
  informational, no migration needed.
- Adding the `Ready` status affects any code that assumes a session is
  `In Progress` immediately after creation — audit `instructor_report` and
  session-state guards so `Ready` sessions are represented sensibly.
- Enabling tabs for students changes their course view from a full-page
  overview to an Overview tab + Simulazioni tab. Overview remains the default
  (first) tab.
