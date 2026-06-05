# Simulation Prompt Evaluation — Design

**Status:** Draft — awaiting user review
**Date:** 2026-06-05
**Module:** `apps/os_lms/os_lms/os_lms/ai/simulations/eval/`

## 1. Goal

Build a system that lets instructors verify the quality of their AI simulation scenarios across two axes:

- **Prompt correctness** — the LLM follows instructions (persona stays in character, debrief doesn't hallucinate, difficulty matches the scenario label).
- **Pedagogical effectiveness** — the simulation actually exercises the declared `learning_objectives`.

The system supports two modes:

- **Authoring** — while editing a scenario, run a synthetic simulation with an LLM-as-student and evaluate the result.
- **Production** — pick an existing real `LMSA Simulation Session` and evaluate the transcript retroactively.

Both modes share the same evaluation pipeline; they differ only in transcript source.

## 2. Architecture

### 2.1 Module layout

New module `apps/os_lms/os_lms/os_lms/ai/simulations/eval/`:

```
eval/
├── __init__.py
├── runner.py             # Authoring orchestration: golden replay + LLM-student runs
├── student/
│   ├── golden.py         # Deterministic golden transcript replay
│   └── llm_student.py    # LLM-as-student with configurable profiles
├── judges/
│   ├── persona.py        # Persona consistency
│   ├── coverage.py       # Learning-objective coverage
│   ├── debrief.py        # Debrief accuracy
│   └── difficulty.py     # Difficulty calibration
├── pipeline.py           # evaluate_transcript() — shared by all modes
├── api.py                # whitelisted endpoints (trigger + read)
└── jobs.py               # background jobs (frappe.enqueue handlers)
```

Existing runtime prompt modules (`prompts/scenario_generator.py`, `prompts/role_play.py`, `prompts/debrief.py`) are **not** touched — they are the prompts the real student uses. The judges live in a separate folder because they are *meta* prompts that analyse the output of the runtime prompts. Keeping them apart prevents accidental conflation.

### 2.2 Shared pipeline

```python
# eval/pipeline.py

def evaluate_transcript(
    *,
    transcript: list[dict],
    scenario: ScenarioRef,
    trace_kind: str,
    golden_expectations: GoldenExpectations | None = None,
    debrief_payload: dict | None = None,
) -> list[DimensionScore]:
    """Run all 4 judges over a transcript. Source-agnostic.

    Called by:
    - runner.run_authoring_test() for synthetic trace_kinds (golden_replay, llm_student)
    - jobs.evaluate_production_session() for trace_kind=production_session
    """
```

`DimensionScore` is a small dataclass `{dimension, score, summary, evidence_quotes, warnings, extras}` where `extras` carries judge-specific payload (e.g. `by_objective` for coverage, `expected_difficulty` for difficulty).

All judges return scores normalised `0.0-1.0`. Aggregation is the unweighted mean.

### 2.3 Unified background execution

Both authoring modes and production evaluation run **inside the background queue**. The API endpoint creates the parent `LMSA Quality Evaluation`, enqueues a job, returns the `eval_id` immediately.

This avoids HTTP timeout risk regardless of LLM provider latency, and gives one codepath to test/debug/monitor.

Frontend differentiates by polling pattern (see §6).

## 3. Data model

Three new doctypes. No changes to existing doctypes.

### 3.1 `LMSA Scenario Golden Run`

Hand-curated golden transcript, N per scenario.

| Field | Type | Notes |
|---|---|---|
| `scenario` | Link → `LMSA Simulation Scenario` | parent |
| `name_label` | Data | e.g. "Studente esemplare" |
| `turns` | Long Text (JSON) | ordered array of `{role: "user"\|"assistant", text: str}` |
| `expected_outcomes` | Long Text | free-form notes on what the student should achieve |
| `active` | Check | include in evaluation runs |

The `turns` JSON is intentionally flat — keeps the doctype slim and is rendered by a custom Vue editor (see §6.2). When a scenario has zero `active=1` goldens, the quick/deep modes refuse to run with a UX-actionable error message.

### 3.2 `LMSA Quality Evaluation`

One row per evaluation request. Parent grouping for the traces below.

| Field | Type | Notes |
|---|---|---|
| `scenario` | Link → `LMSA Simulation Scenario` | always present |
| `run_mode` | Select | `quick` \| `deep` \| `production` |
| `triggered_by` | Link → User | who fired it |
| `triggered_at` | Datetime | auto |
| `status` | Select | `queued` \| `running` \| `complete` \| `failed` |
| `aggregate_persona_score` | Float | 0-1, mean of completed traces |
| `aggregate_coverage_score` | Float | 0-1 |
| `aggregate_debrief_score` | Float | 0-1 |
| `aggregate_difficulty_score` | Float | 0-1 |
| `error_message` | Long Text | populated on `failed` |
| `traces` | Child Table → `LMSA Evaluation Trace` | see below |

Trace count by mode:
- `production` — 1 trace (the real session)
- `quick` — 2 traces (1 golden replay + 1 LLM-student with `competent` profile)
- `deep` — 5 traces (1 golden + 4 LLM-students: competent, novice, off_topic, adversarial)

Aggregates exclude `failed` traces; if all traces fail, `status=failed` and aggregates are null.

### 3.3 `LMSA Evaluation Trace` (child table)

| Field | Type | Notes |
|---|---|---|
| `trace_kind` | Select | `golden_replay` \| `llm_student` \| `production_session` |
| `student_profile` | Data | only for `llm_student` |
| `source_session` | Link → `LMSA Simulation Session` | only for `production_session` |
| `source_golden` | Link → `LMSA Scenario Golden Run` | only for `golden_replay` |
| `transcript_json` | Long Text | populated for synthetic kinds; null for `production_session` (transcript lives on the source session) |
| `dimension_scores_json` | Long Text | array `[{dimension, score, summary, evidence_quotes, warnings, extras}]` |
| `judge_versions_json` | Long Text | map `{dimension: judge_version_string}` for traceability |
| `trace_status` | Select | `complete` \| `failed` |
| `trace_error` | Long Text | only on `failed` |

Per-dimension scores live in a JSON Code field rather than a nested child table because (a) Frappe child-of-child is awkward, (b) we don't need SQL queries on individual dimension scores in v1 — aggregation runs in Python.

If a future need for SQL aggregation emerges we promote `dimension_scores_json` into a separate `LMSA Evaluation Dimension Score` doctype linked back to the trace. The migration is a one-time Python script over historical data.

### 3.4 LLM-student profiles

Constants in `eval/student/llm_student.py`, not a doctype:

- `competent` — uses the right techniques, well-prepared (Quick mode uses only this)
- `novice` — basic / awkward replies, common rookie mistakes
- `off_topic` — drifts to unrelated topics (probes persona consistency)
- `adversarial` — attempts prompt injection / hostile tone (probes defenses)

Promote to a doctype only if instructors want to define custom profiles. Out of scope for v1.

## 4. Flows

### 4.1 Authoring — Quick check

```
Editor → click "Quick check"
       ↓
POST eval.api.run_quick_check(scenario_name)
       ↓ (returns eval_id immediately)
Backend:
  1. Validate: scenario exists + has at least one active golden (else 400)
  2. Insert LMSA Quality Evaluation (status=queued, run_mode=quick)
  3. frappe.enqueue(jobs.run_authoring_evaluation, eval_id)
       ↓
Frontend: open modal with spinner, poll get_evaluation_status(eval_id) every 2s
       ↓
Background job:
  - trace_0 = golden_replay (deterministic, 0 LLM calls)
  - trace_1 = llm_student[competent]
        scenario_generator(seed) → 1 LLM call
        loop turns: student_prompt + cliente_prompt × N (~10-15 turns)
        debrief_prompt → 1 LLM call
  - For each trace: pipeline.evaluate_transcript() → 4 judge LLM calls
  - Aggregate per-dimension means
  - status=complete
  - frappe.publish_realtime("simulation:eval_complete", {eval_id, scenario, run_mode})
       ↓
Frontend:
  - On poll seeing status=complete → close modal, open EvaluationResultsDialog
  - On 90s client-side timeout → close modal, toast "Sta richiedendo più del previsto",
    keep listening on realtime channel for the eventual completion
```

Estimated load: ~25 chat-turn LLM calls + 8 judge calls = ~33 LLM calls. Median time 30-60s.

### 4.2 Authoring — Deep evaluation

```
Editor → click "Deep evaluation"
       ↓
POST run_deep_evaluation(scenario_name) → eval_id immediately
       ↓
Frontend: badge "Valutazione in corso" appears next to the scenario title,
both eval buttons disabled until this eval completes; editor remains usable
       ↓
Background job: 1 golden + 4 LLM-students × {scenario_gen + turns + debrief}
                5 transcripts × 4 judges
                ~120 LLM calls total
       ↓
On complete: realtime event → toast → auto-open EvaluationResultsDialog
```

If the docente leaves the editor before completion, a notification surfaces in the global toast handler.

### 4.3 Production — On-demand evaluation

```
TranscriptDrawer (terminal session) → click "Valuta sessione"
       ↓
POST run_production_evaluation(session_id) → eval_id immediately
       ↓
Frontend: drawer shows "Valutazione in corso" inline; poll get_evaluation_status
       ↓
Background job:
  - trace_0 = production_session
  - Fetch transcript from LMSA Simulation Turn rows linked to the session
  - Fetch the session's existing debrief payload (if any) → pass to debrief judge
  - pipeline.evaluate_transcript(trace_kind="production_session", debrief_payload=…)
  - 4 judge LLM calls
  - status=complete
       ↓
On complete: realtime event → drawer opens results dialog inline
```

Estimated load: 4 LLM calls only. Median time 10-20s.

**Idempotence:** re-evaluating the same session creates a **new** `LMSA Quality Evaluation`; the previous one is preserved. This makes prompt drift visible — re-running historical sessions after a judge prompt iteration shows whether the change moved scores.

## 5. Judges

All four judges follow the same Python module shape (mirrors `prompts/scenario_generator.py`). The skeleton below shows structure only; the actual prompt body and rubric of each judge is designed at implementation time and committed in the same PR.

```python
JUDGE_VERSION = "persona.v1"  # bumped on every prompt change

SYSTEM_PROMPT = "..."  # designed at implementation time per judge

OUTPUT_SCHEMA: dict = {
    "type": "object",
    "required": ["score", "summary", "evidence_quotes"],
    "properties": {
        "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "summary": {"type": "string"},
        "evidence_quotes": {"type": "array", "items": {...}},
        "warnings": {"type": "array", "items": {"type": "string"}},
        # judge-specific extras below
    },
}

def build_messages(*, transcript, scenario, ...) -> tuple[str, list[dict]]:
    """Pure function — no frappe / no HTTP."""

def parse_output(text: str) -> DimensionScore:
    """Raises ValueError on parse failure; caller retries with temp=0."""
```

### 5.1 `persona.py`

Checks: cliente stays in character (`name`, `role`, `company`, `mood`, `key_objection`, `hidden_motivation`); does not leak `hidden_motivation`; does not break character ("come AI", offering to help the student); resists prompt injection in-character (does not respond meta).

Indicative thresholds: `≥0.85` consistent · `0.6-0.85` minor slips · `<0.6` persona broken.

### 5.2 `coverage.py`

Per-objective breakdown in `extras.by_objective[]`:

```json
{
  "score": 0.62,
  "extras": {
    "by_objective": [
      {"objective": "Gestione obiezione prezzo", "score": 0.9,
       "covered": true, "evidence_turn": 4},
      {"objective": "Riconoscere segnali chiusura", "score": 0.0,
       "covered": false, "reason": "Mai emerso nel dialogo"}
    ]
  }
}
```

Distinguishes **not-emerged** (scenario gave no opportunity) from **emerged-but-not-exercised** (student missed it). Only the first penalises the scenario; the second penalises the student. Mixing these two would conflate prompt-authoring quality with student performance.

### 5.3 `debrief.py`

Extra input: `debrief_payload` — the runtime debrief output (`criterion_scores`, `strengths`, `improvements`, `overall_score`).

If `debrief_payload` is missing (synthetic run where the debrief stage failed, or production session that never reached the debrief job), the judge returns `score=null` with `warnings=["debrief_missing"]` and is excluded from the trace aggregate for the `accuratezza_debrief` dimension. The other three judges proceed normally.

Checks:
- **Hallucination**: each `evidence_quote` in the debrief is actually present in the transcript (substring match, with small tolerance for whitespace/case).
- **Score↔evidence consistency**: a high `criterion_score` is supported by positive-tone evidence, not by quotes that read as failures.
- **Overall consistency**: `overall_score` matches the weighted mean of `criterion_scores` against `evaluation_schema.passing_threshold`.
- **Improvement actionability**: each improvement references something specific to the transcript, not generic advice.

`extras` carries `hallucinated_quotes`, `score_inconsistencies`, `overall_consistency_delta`.

### 5.4 `difficulty.py`

Checks: `easy` scenario → cliente concedes to basic techniques in 2-3 turns; `hard` → resists advanced techniques, forces specific tooling. Cross-checks the runtime debrief `overall_score` against the scenario label (`easy` with `overall_score=20/100` flags a calibration miss).

`extras`:
```json
{
  "expected_difficulty": "medium",
  "perceived_difficulty": "medium-hard",
  "calibration_offset": 0.5  // -2..+2, positive = harder than label
}
```

`calibration_offset` enables future drift-over-time charts without a v2 schema change.

### 5.5 Model selection

Default: `simulation_debrief_provider` / `simulation_debrief_model` from `LMSA Settings`. Judges are non-realtime so we optimise for accuracy over latency. An `eval_provider` / `eval_model` override is a v2 add — implement only if a specific judge needs a different model.

### 5.6 Aggregation

```python
trace.aggregate = mean([persona, coverage, debrief, difficulty])
evaluation.aggregate_<dim> = mean(trace.<dim> for trace in traces
                                  if trace.trace_status == "complete")
```

Unweighted mean for v1. Weighted aggregation (e.g. "coverage counts double for us") is a config knob to add when demand emerges.

## 6. Frontend

Four edits to existing files plus one new shared dialog component. No new routes.

### 6.1 `ScenarioEditor.vue` header

```
[Quick check] [Deep evaluation] [Golden runs]    [Esporta] [Importa] [Prova...] [Salva]
```

- All three new buttons disabled until `props.scenarioName` is non-empty (scenario saved at least once)
- Quick: opens `EvaluationResultsDialog` in loading state, polls `get_evaluation_status` every 2s, 90s client-side timeout
- Deep: fires API, toast "Valutazione avviata", badge `Valutazione in corso` on the scenario title; both Quick + Deep disabled while a deep eval is pending for this scenario
- Realtime listener filters on `scenario === props.scenarioName`: opens results dialog when matching event arrives
- Golden runs: opens `GoldenRunsModal.vue`

### 6.2 `GoldenRunsModal.vue` (new)

Dialog listing `LMSA Scenario Golden Run` rows for the current scenario.

- Row: `name_label`, turn count, `active` badge, edit/delete actions
- "+ Nuovo golden run" opens an inline editor

The single-golden editor is a screenplay-like form:

- `name_label`, `expected_outcomes` (textarea), `active` checkbox
- Turn list: each turn has a role selector (`Studente` / `Cliente`), a textarea, and reorder up/down + delete controls
- "+ Aggiungi turn" buttons for each role at the bottom

Pattern is the same accordion + reorder we already use for `CriterionEditor` and `seed_variations`.

### 6.3 `EvaluationResultsDialog.vue` (new)

Shared component used by both authoring and production. Layout (sketch):

```
┌─ Valutazione — {run_mode} — {triggered_at} ─────┐
│  Scenario: {name}                                │
│  Aggregate scores:                               │
│    Persona consistency     ████████░░  0.78     │
│    Coverage obiettivi      █████░░░░░  0.55  ⚠ │
│    Accuratezza debrief     █████████░  0.91  ✓ │
│    Calibrazione difficoltà ██████░░░░  0.62     │
│                                                  │
│  Traces:                                         │
│    ▾ Golden replay ("Studente esemplare")  0.81 │
│      Persona: 0.92 — "...quote..."              │
│      Coverage: 0.78 — by_objective breakdown    │
│      [Vedi transcript completo]                 │
│    ▸ LLM-student (competent)               0.65 │
│    ▸ LLM-student (novice)                  0.58 │
│    ...                                           │
└──────────────────────────────────────────────────┘
```

Score colour thresholds: green `≥0.80`, yellow `0.60-0.79`, red `<0.60`. Hardcoded constants in v1; tunable per-team in v2 if needed.

"Vedi transcript completo" opens a side drawer with the synthetic transcript and the judge's evidence quotes anchored to the cited turn indices. For `production_session` traces the link navigates to the existing `TranscriptDrawer`.

### 6.4 `TranscriptDrawer.vue` additions

- "Valuta sessione" button next to "Salva nota". Visible only when `payload.session.status` is terminal (`Completed`, `Needs Review`, `Abandoned`, `Error`).
- Click → same flow as quick check (enqueue + poll + dialog)
- New section "Valutazioni precedenti" lists past `LMSA Quality Evaluation` for this session. Each row clickable to re-open the results dialog. Useful when a judge prompt was iterated and the docente wants to compare old vs new scores on the same session.

### 6.5 Realtime

New channel: `simulation:eval_complete`. Payload `{eval_id, scenario, source_session, run_mode, status}`.

Subscribed lazily:
- `ScenarioEditor` on mount, filters on `scenario === props.scenarioName`, unsubscribes on unmount.
- `TranscriptDrawer` on mount, filters on `source_session === props.sessionId`, unsubscribes on unmount.

Same lifecycle pattern as `useSimulationSession.js`.

### 6.6 `useEvaluation.js` (new composable)

Consolidates polling + timeout + realtime in one place so the three entry points reuse it:

```js
const {
    runQuickCheck,
    runDeepEvaluation,
    runProductionEvaluation,
    pollUntilComplete,        // resolves on complete, rejects on timeout
    subscribeToCompletion,    // filter fn, emits eval_id
} = useEvaluation()
```

### 6.7 Out of scope (v1)

- Quality dashboard cross-scenario with trends over time
- Drift visualisation of judge versions (re-running historical sessions on new prompts and plotting deltas)
- Custom student profiles editable from the SPA
- Configurable per-dimension weights
- Configurable colour thresholds in `Brand Customize`

These become valuable once we have weeks of historical evaluation data. Revisit after the first month of usage.

## 7. APIs

All under `os_lms.os_lms.ai.simulations.eval.api`. All `@frappe.whitelist()`, return type-annotated dicts.

| Endpoint | Args | Returns | Permissions |
|---|---|---|---|
| `run_quick_check` | `scenario: str` | `{eval_id: str}` | scenario.owner or instructor of `scenario.lms_course` |
| `run_deep_evaluation` | `scenario: str` | `{eval_id: str}` | scenario.owner or instructor of `scenario.lms_course` |
| `run_production_evaluation` | `session_id: str` | `{eval_id: str}` | instructor of `session.scenario.lms_course` |
| `get_evaluation_status` | `eval_id: str` | `{status, run_mode, aggregate_*, error_message?}` | `eval.triggered_by` or instructor of the scenario's course |
| `get_evaluation_result` | `eval_id: str` | full result with traces + dimension scores | Same as above |
| `list_evaluations_for_scenario` | `scenario: str` | `[{eval_id, triggered_at, run_mode, status, aggregate_*}]` | scenario.owner or instructor of `scenario.lms_course` |
| `list_evaluations_for_session` | `session_id: str` | `[{eval_id, triggered_at, status, aggregate_*}]` | instructor of `session.scenario.lms_course` |
| `list_goldens` | `scenario: str` | `[{name, name_label, turn_count, active}]` | scenario.owner or instructor of `scenario.lms_course` |
| `save_golden` | `payload: dict` | `{name: str}` | scenario.owner or instructor of `scenario.lms_course` |
| `delete_golden` | `golden_name: str` | `{ok: bool}` | scenario.owner or instructor of `scenario.lms_course` |

"Instructor" = the user appears in the `Course Instructor` child rows of the `LMS Course`, per the existing helper pattern already used in `simulations/api.py` (querying `Course Instructor` with `filters={"instructor": user}` and `pluck="parent"`). Reuse the same helper rather than re-implementing the check.

`run_quick_check` and `run_deep_evaluation` return 400 with a UX-actionable message if the scenario has zero active goldens.

## 8. Error handling

- **Missing golden on authoring eval**: API rejects with `MissingGoldenError` → toast "Crea almeno un golden run attivo per lanciare la valutazione" + deep-link to `GoldenRunsModal`.
- **LLM provider error during a trace**: that specific trace is marked `failed` with `trace_error`; the job continues for the remaining traces. Aggregates are computed over the `complete` traces only. The evaluation parent is `complete` if at least one trace succeeded, otherwise `failed`.
- **JSON parse failure on a judge output**: one in-process retry with `temperature=0` (same recovery pattern as the existing debrief job). Persistent failure → that dimension on that trace is `failed`, excluded from the trace and evaluation aggregates.
- **max_turns reached during LLM-student run**: the trace status remains `complete`, but the synthetic session is marked as abandoned (`session_status="Abandoned"` in `transcript_json` metadata). The coverage judge receives this signal and typically scores low.
- **Timeout on the background job** (Frappe queue default ~5 min, may need tuning for deep mode): job marked `failed`, surface in `error_message`. Frontend realtime listener receives a failure event and shows a toast.
- **Per-LLM-call timeout**: each individual provider call (chat turn, judge call) is wrapped with a hard timeout of 60s (configurable via `LMSA Settings.eval_llm_call_timeout_s`, default `60`). On exceeded timeout the call counts as a provider error and triggers the trace failure path above. Prevents a single hung call from stalling an entire deep evaluation job.
- **HTTP client-side timeout on quick check polling** (90s): close the modal, keep the realtime listener; the eventual completion event opens the results dialog with a toast.

## 9. Testing

Unit tests, no LLM calls:

- `eval/judges/test_persona.py`, `test_coverage.py`, `test_debrief.py`, `test_difficulty.py` — `build_messages()` produces expected message structure, `parse_output()` handles valid + invalid JSON.
- `eval/test_pipeline.py` — `evaluate_transcript()` dispatches the right judges and aggregates correctly.
- `eval/student/test_golden.py` — golden replay produces a transcript matching the stored turns.
- `eval/student/test_llm_student.py` — student profile prompt construction.
- `eval/test_jobs.py` — job creates traces, calls pipeline, persists results.
- `eval/test_api.py` — endpoints enforce permissions, validate input.

Integration tests with a mock LLM provider (`prompts/mock.py` style):

- `eval/integration/test_run_authoring_quick.py` — full flow with a deterministic mock provider, asserts on persisted doctype state.
- `eval/integration/test_run_production.py` — same for production.

A smoke test that runs a real eval against the local OpenAI key, gated behind an env var (`RUN_LLM_TESTS=1`), is added for manual verification on each judge-prompt iteration.

## 10. Open questions / explicitly deferred

- **Authorization granularity for production eval**: currently restricted to "instructor of the course". If schools want HR / admins to trigger evals on courses they don't instruct, we add a `Quality Reviewer` role. Deferred until a stakeholder asks.
- **Per-dimension weights**: configurable later if instructors want to upweight one signal.
- **Score normalisation across judge versions**: when we bump `JUDGE_VERSION`, scores become a new distribution. If `persona.v1` and `persona.v2` produce systematically different score ranges, aggregate-over-time charts will look noisy. Solution (v2): expose a "show only v_n results" filter in the dashboard.
- **Cost telemetry**: track LLM token usage per evaluation and surface it. Useful once schools cost-model the feature. Deferred — initial assumption is that authoring usage is sporadic enough not to need it.

## 11. Delivery sequencing (suggested, not binding)

The implementation plan will be authored separately via the `writing-plans` skill. Suggested order so each step is independently valuable:

1. Doctypes + migrations
2. Pipeline + judges (with mock provider for tests)
3. `runner.py` (authoring with synthetic student)
4. APIs + background jobs
5. `useEvaluation.js` composable
6. `EvaluationResultsDialog.vue`
7. ScenarioEditor integration (Quick + Deep + Golden runs)
8. TranscriptDrawer integration (production)
9. Realtime channel + listeners

A working production-only evaluation slice is reachable after step 4 + a minimal frontend integration in step 8, providing an early dogfooding milestone.
