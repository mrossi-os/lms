# Code Contract — actual interfaces the eval module integrates with

This file is the source of truth for what the existing codebase actually
exposes. The plan's tasks must match this exactly. If you find a divergence
during implementation, update this file first, then the plan.

## LLM provider layer — `os_lms.os_lms.ai.utils.llm`

### Key exports

```python
from os_lms.os_lms.ai.utils.llm import (
    resolve_provider,           # purpose-based provider factory
    chat_with_fallback,         # convenience wrapper with provider fallback
)
from os_lms.os_lms.ai.utils.llm.provider import (
    LLMProvider,                # ABC
    ChatMessage,                # dataclass: role, content, name
    ChatResponse,               # dataclass: text, finish_reason, usage, model, provider, raw
    Usage,                      # dataclass: prompt_tokens, completion_tokens
    JsonSchema,                 # dataclass for structured output
)
```

### `LLMProvider.chat()` signature

```python
def chat(
    self,
    messages: list[ChatMessage],            # POSITIONAL
    *,
    system: str | None = None,              # keyword-only
    model: str | None = None,
    temperature: float = 0.7,
    top_p: float = 1.0,
    max_tokens: int = 1024,
    stop: list[str] | None = None,
    response_format: JsonSchema | None = None,
    stream: bool = False,
    timeout: float = 60.0,
) -> ChatResponse | Iterator[ChatChunk]:
    ...
```

**Reading the result**: `response.text` (string). `response.usage.prompt_tokens` /
`.completion_tokens`. `response.provider`, `response.model`.

### `resolve_provider()`

```python
def resolve_provider(
    purpose: Literal["chat", "debrief"] = "chat",
    *,
    override: str | None = None,
) -> LLMProvider: ...
```

Reads LMSA Settings (`simulation_chat_provider` / `simulation_debrief_provider`,
falling back to `simulation_provider_default` on "auto"). The optional
`override` (e.g. from a Scenario field) takes precedence.

For the eval module we use `resolve_provider("debrief")` because judges are
non-realtime (we want quality, not latency).

### `chat_with_fallback()`

```python
def chat_with_fallback(
    purpose: Literal["chat", "debrief"],
    messages: list[ChatMessage],
    *,
    override: str | None = None,
    **chat_kwargs,                          # forwarded to provider.chat
) -> ChatResponse: ...
```

Used by the orchestrator's `_ask_customer`. Useful for the eval module's
runner too: same fallback semantics, same single call site.

### Mock provider

Registered as `"mock"`. Enabled in tests via `enable_mock_provider()` from
the existing `_fixtures.py`. Behaviour: `chat()` returns
`ChatResponse(text="MOCK[<hash>]: <truncated last user msg>", ...)`.

## Role-play prompt — `os_lms.os_lms.ai.simulations.prompts.role_play`

### What it exports

```python
def build_role_play_system_prompt(
    *,
    persona: PersonaVariant,             # NOT a string; a dataclass
    generated_situation: str,
    difficulty: str,
    language: str = "it",
) -> str: ...
```

**Returns the system prompt only.** The messages list (history) is the
caller's responsibility — see how `orchestrator._ask_customer` does it.

### What does NOT exist (the plan v1 referenced these by mistake)

- `role_play.build_messages(...)` — does not exist
- `role_play.parse_output(...)` — not applicable; role-play is free text

## `PersonaVariant` — `os_lms.os_lms.ai.simulations.prompts.scenario_generator`

```python
@dataclass
class PersonaVariant:
    name: str
    role: str
    company: str
    mood: str
    key_objection: str
    hidden_motivation: str
```

The PersonaVariant is **generated** at session start by `scenario_generator`
from the scenario's `customer_persona` template. It is NOT the same as the
raw `customer_persona` string field on the scenario.

For the eval module's authoring synthetic runs we have two options:

**A. Mirror the runtime flow** — call `scenario_generator` first to get a
PersonaVariant, then run role_play turns with it. Faithful to runtime
behaviour but adds 1 LLM call per synthetic trace and a JSON parse step.

**B. Bypass scenario_generator** — construct a PersonaVariant directly from
the scenario doc's `customer_persona` text by parsing the first line/section
heuristically, or fall back to a constant persona. Cheaper but the LLM-student
exercises a different prompt than the runtime student does — limits the
fidelity of the eval.

**Decision for the plan: Option A.** We need to evaluate the same prompt
chain the real student sees, otherwise the eval doesn't catch drift in
`scenario_generator`. Cost: +1 LLM call per LLM-student trace, +parser
fragility (already known and handled by the runtime).

## How the orchestrator builds role-play LLM calls

This is the pattern to mirror in `eval/runner.py`:

```python
# _ask_customer in orchestrator.py
persona = _persona_from_session(session)    # PersonaVariant from JSON on session
system_prompt = build_role_play_system_prompt(
    persona=persona,
    generated_situation=session.generated_situation,
    difficulty=_scenario_difficulty(session.scenario),
)
history = _load_chat_history(session.name)  # list[ChatMessage]
response = chat_with_fallback(
    "chat",
    history,
    override=_scenario_provider_override(session.scenario),
    system=system_prompt,
    temperature=0.7,
    max_tokens=400,
)
# response is ChatResponse; use response.text
```

`_load_chat_history` filters out non-user/assistant rows. The eval module
doesn't have a session to read from, so it builds the ChatMessage list
from its in-memory transcript.

## Frappe doctype shapes used by the eval module

### LMSA Simulation Turn — fields used

- `session` (Link, parent)
- `turn_index` (Int, order)
- `role` (Select: `user` / `assistant` / others filtered out)
- `text_content` (Long Text — **NOT** `text`)
- `model_used`, `provider_used`, `latency_ms`, `tokens_input`,
  `tokens_output`, `injection_attempt_detected`

### LMSA Simulation Session — terminal status values

`Completed`, `Abandoned`, `Error`, `Needs Review`

### LMSA Simulation Debrief — fields used by `_load_session_debrief`

- `session` (Link, FK to session)
- `scenario`, `course`, `student`
- `overall_score` (Int / Float)
- `passed` (Check)
- `criterion_scores` (Code / JSON)
- `strengths`, `improvements` (Code / JSON)
- `behavioral_analysis` (Code / JSON, optional)
- `prompt_version`, `debrief_provider_used`, `debrief_model_used`
- `instructor_review`, `instructor_reviewed_by`, `instructor_reviewed_at`

**Field-name note**: existing fields are `criterion_scores`, NOT
`criterion_scores_json`. The plan v1 had the `_json` suffix assumption
which is wrong for this doctype. Reading: parse with `json.loads()` —
they're Code-type fields containing JSON strings.

## Existing fixtures — `os_lms.os_lms.ai.simulations.tests._fixtures`

What exists:

```python
def make_evaluation_schema(name: str = "Test Schema"): ...
def make_published_scenario(
    *,
    name: str = "Test Scenario",
    course: str | None = None,
    evaluation_schema: str | None = None,
): ...
def enable_mock_provider(): ...
def reset_settings(): ...
def cleanup_sessions_and_turns(): ...
```

What does NOT exist (must be added by the plan):

- `make_scenario_with_instructor()` — needs Course Instructor child
- `make_completed_session()` — needs a Session in `Completed` status with
  >= 2 turns
- `make_scenario()` / `make_session()` — older names referenced by mistake;
  use `make_published_scenario()` instead

## Permission helper to mirror

Existing pattern in `simulations/api.py`:

```python
courses_for_user = frappe.get_all(
    "Course Instructor",
    filters={"instructor": user},
    pluck="parent",
)
# Then check if course in courses_for_user
```

The eval module's `permissions.py` reuses this exact pattern.

## Summary of plan-vs-reality deltas

| Plan v1 reference | Reality | Plan tasks impacted |
|---|---|---|
| `simulations/providers.get_provider(name)` | `utils/llm.resolve_provider(purpose, override=...)` | 13 |
| `provider.chat(system, messages, model) -> str` | `provider.chat(messages, *, system, model, ...) -> ChatResponse` | 12, 13, 14 |
| `role_play.build_messages(...)` | `role_play.build_role_play_system_prompt(persona, ...)` only; messages built by caller | 14 |
| Raw `customer_persona` directly usable | Must run `scenario_generator` first to get `PersonaVariant` for role-play | 14 |
| `text` field on Turn | `text_content` | 13 |
| `criterion_scores_json`, `strengths_json` on Debrief | `criterion_scores`, `strengths` (Code fields, JSON content) | 13 |
| `make_scenario()`, `make_session()` | `make_published_scenario(*, ...)` exists; instructor + completed helpers need creating | 5, 13 |
| `enable_mock_provider()` exists and should be used | Use it in tests instead of patching `_get_provider` | 13, 16, 17 |

These deltas are addressed by the plan revisions following this document.
