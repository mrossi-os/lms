# Evaluation module — eval/

Verifies the quality of AI simulation scenarios across four dimensions
(persona consistency, learning-objective coverage, debrief accuracy,
difficulty calibration) on two kinds of input:

- **Synthetic transcripts** — generated at authoring time via golden replay
  + LLM-student profiles
- **Real session transcripts** — existing `LMSA Simulation Session` rows
  evaluated on-demand by an instructor

Spec: `docs/superpowers/specs/2026-06-05-simulation-prompt-evaluation-design.md`
Plan: `docs/superpowers/plans/2026-06-05-simulation-prompt-evaluation.md`
Contract: `docs/superpowers/plans/2026-06-05-simulation-prompt-evaluation-CONTRACT.md`

## Module layout

```
eval/
├── types.py           # DimensionScore, ScenarioRef, GoldenExpectations
├── permissions.py     # user_is_course_instructor + access guards
├── pipeline.py        # evaluate_transcript() — shared across modes
├── runner.py          # synthetic-session generators (authoring)
├── jobs.py            # frappe.enqueue background handlers
├── api.py             # @frappe.whitelist() endpoints
├── student/
│   ├── golden.py      # deterministic golden-transcript replay
│   ├── profiles.py    # 4 LLM-student profile constants
│   └── llm_student.py # student prompt builder
├── judges/
│   ├── persona.py
│   ├── coverage.py
│   ├── debrief.py
│   └── difficulty.py
└── tests/
    ├── test_*.py            # 40+ unit tests
    └── integration/
        ├── test_run_production.py
        └── test_run_authoring_quick.py
```

## Running the test suite

```bash
docker exec --user frappe -w /home/frappe/bench-data/frappe-bench dev-elite-frappe-1 \
  bench --site lms.localhost run-tests --app os_lms \
  --module os_lms.os_lms.ai.simulations.eval.tests.test_pipeline
```

Substitute the module path for any of the test files.

## Manual smoke test against the real LLM provider

After every judge-prompt iteration, run a single quick check against the
real LLM provider to validate prompt+parser end-to-end. The integration
test suite uses a FakeProvider so it stays cheap and offline; a real-LLM
verification is currently a manual one-liner from the bench console:

```bash
docker exec --user frappe -w /home/frappe/bench-data/frappe-bench dev-elite-frappe-1 \
  bench --site lms.localhost execute \
  'os_lms.os_lms.ai.simulations.eval.api.run_quick_check' \
  --kwargs '{"scenario": "SC-XXX"}'
```

Replace `SC-XXX` with a real scenario id that has at least one active
LMSA Scenario Golden Run. The eval_id is returned; the background job runs
asynchronously. Inspect the result via the desk or
`bench execute os_lms.os_lms.ai.simulations.eval.api.get_evaluation_result`.

## Endpoints

| Endpoint | Args | Purpose |
|---|---|---|
| `run_quick_check` | `scenario` | Enqueue quick authoring eval (1 golden + 1 LLM-student[competent]) |
| `run_deep_evaluation` | `scenario` | Enqueue deep authoring eval (1 golden + 4 LLM-student profiles) |
| `run_production_evaluation` | `session_id` | Enqueue production eval of a real session |
| `get_evaluation_status` | `eval_id` | Poll-friendly summary (status + aggregates) |
| `get_evaluation_result` | `eval_id` | Full result including per-trace dimension scores |
| `list_evaluations_for_scenario` | `scenario` | History of evals for a scenario |
| `list_evaluations_for_session` | `session_id` | History of evals for a session |
| `list_goldens` | `scenario` | Goldens registered for a scenario |
| `save_golden` | `payload` | Create/update an LMSA Scenario Golden Run |
| `delete_golden` | `golden_name` | Remove a golden |

All endpoints require either ownership of the target scenario or
instructor status on its `lms_course`.

## Milestone status

- **M1 — Backend feature-complete**: production + authoring eval works
  end-to-end via API + queue jobs.
- **M2 — Authoring UI in ScenarioEditor**: Quick + Deep buttons,
  EvaluationResultsDialog, GoldenRunsModal.
- **M3 — Production UI in TranscriptDrawer**: "Valuta sessione" button +
  evaluation history list, on-demand from instructor view.
