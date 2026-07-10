# Scenario Briefing (Two-Phase Start) + Student Simulations Tab — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split simulation start into two phases — generate the variant and show the student a briefing, then begin the AI session — and add a student "Simulazioni" course tab to list, restart, and continue their sessions.

**Architecture:** Backend adds an AI-generated `student_brief` to the scenario variant, a new `Ready` session state, and splits the orchestrator's `start_session` into `prepare_session` (generate + persist `Ready`) and `begin_chat_session` (persist first turn → `In Progress`). Voice reuses the prepared session instead of regenerating. Frontend adds a shared briefing UI + `useSimulationBegin` composable, a two-phase `SimulationLauncher`, brief side-panels in the chat/voice runtimes, and a `CourseStudentSimulations` tab backed by new `list_my_sessions` / `clone_session` endpoints.

**Tech Stack:** Frappe Framework (Python 3.10, `frappe.tests.UnitTestCase`), Vue 3 SPA (`frappe-ui`, Pinia, Vite), MariaDB, Redis.

## Global Constraints

- Backend business logic delegates through `SessionOrchestrator`; whitelisted API methods stay thin (validate → gate → delegate → return plain dict). Copy this pattern.
- `require_type_annotated_api_methods = True`: every `@frappe.whitelist()` method MUST have type-annotated params and return type.
- Indentation per existing file: `orchestrator.py`, `prompts/scenario_generator.py`, `realtime/api.py`, doctype `.py` use **tabs**; `simulations/api.py` and all `tests/*.py` use **4 spaces**. Match the file you edit.
- All code comments in English (project rule). User-facing SPA strings stay Italian (existing convention) wrapped in `__()`.
- Session status strings must stay in sync between the doctype JSON `status` Select options and the `STATUS_*` constants in `lmsa_simulation_session.py`.
- Run backend tests with: `bench --site lms.localhost run-tests --app os_lms --module <dotted.module>` (Docker: prefix with `docker compose exec frappe`). Frontend has no JS unit runner — verify with `cd frontend && yarn build`.
- Keep `SessionOrchestrator.start_session` and the whitelisted `api.start_session` working (used by internal tests, the eval runner, and the instructor "Test Run" in `ScenarioEditor.vue`). Refactor `start_session` to compose the new primitives; do not delete it.

---

## File Structure

**Backend (create):** none.
**Backend (modify):**
- `apps/os_lms/os_lms/os_lms/ai/simulations/prompts/scenario_generator.py` — schema/dataclass/parser + version bump.
- `apps/os_lms/os_lms/os_lms/ai/utils/default_prompt/scenario_variant_generator.py` — prompt text + version/tokens.
- `apps/os_lms/os_lms/os_lms/doctype/lmsa_simulation_session/lmsa_simulation_session.json` — `student_brief` field + `Ready` status option.
- `apps/os_lms/os_lms/os_lms/doctype/lmsa_simulation_session/lmsa_simulation_session.py` — `STATUS_READY` constant.
- `apps/os_lms/os_lms/os_lms/ai/simulations/orchestrator.py` — `prepare_session`, `begin_chat_session`, refactor `start_session`, refactor `start_voice_session`, `clone_session`.
- `apps/os_lms/os_lms/os_lms/ai/simulations/api.py` — `prepare_session`, `begin_session`, `list_my_sessions`, `clone_session`, `get_session` payload.
- `apps/os_lms/os_lms/os_lms/ai/realtime/api.py` — `create_voice_session(session_id)`.
- `apps/os_lms/os_lms/os_lms/ai/simulations/tests/_fixtures.py` — `CANNED_VARIANT` gains `student_brief`.
- Test files: `tests/test_prompts.py`, `tests/test_orchestrator.py`, `tests/test_api.py`, `realtime/tests/test_realtime_api.py`.

**Frontend (create):**
- `frontend/src/oslms/components/simulations/SimulationBriefing.vue`
- `frontend/src/oslms/composables/useSimulationBegin.js`
- `frontend/src/oslms/pages/Courses/CourseStudentSimulations.vue`

**Frontend (modify):**
- `frontend/src/oslms/components/simulations/SimulationLauncher.vue`
- `frontend/src/oslms/components/simulations/VoiceSession.vue`
- `frontend/src/oslms/composables/useRealtimeSession.js`
- `frontend/src/oslms/pages/Simulation/SimulationPlay.vue`
- `frontend/src/oslms/components/simulations/ChatSession.vue`
- `frontend/src/pages/Courses/CourseDetail.vue`

---

## Task 1: Add `student_brief` to the scenario variant (schema, dataclass, parser, prompt)

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/ai/simulations/prompts/scenario_generator.py`
- Modify: `apps/os_lms/os_lms/os_lms/ai/utils/default_prompt/scenario_variant_generator.py`
- Modify: `apps/os_lms/os_lms/os_lms/ai/simulations/tests/_fixtures.py`
- Test: `apps/os_lms/os_lms/os_lms/ai/simulations/tests/test_prompts.py`

**Interfaces:**
- Produces: `ScenarioVariant(situation: str, persona: PersonaVariant, student_brief: str)`; `SCENARIO_GEN_VERSION == "gen.v2"`; `parse_scenario_generator_output(text)` requires a non-empty `student_brief` top-level string. `SCENARIO_SCHEMA` requires top-level `student_brief`.

- [ ] **Step 1: Write the failing tests** (4-space indent) — append to `TestScenarioGenerator` in `tests/test_prompts.py`:

```python
    def test_parser_reads_student_brief(self):
        payload = (
            '{"situation":"S","student_brief":"Il tuo compito è ...",'
            '"persona":{"name":"A","role":"R","context":"C","mood":"M",'
            '"key_objection":"K","hidden_motivation":"H"}}'
        )
        variant = parse_scenario_generator_output(payload)
        self.assertEqual(variant.student_brief, "Il tuo compito è ...")

    def test_parser_rejects_missing_student_brief(self):
        with self.assertRaises(ValueError):
            parse_scenario_generator_output(
                '{"situation":"S","persona":{"name":"A","role":"R","context":"C",'
                '"mood":"M","key_objection":"K","hidden_motivation":"H"}}'
            )

    def test_schema_requires_student_brief(self):
        self.assertIn("student_brief", SCENARIO_SCHEMA["required"])
        self.assertIn("student_brief", SCENARIO_SCHEMA["properties"])

    def test_version_is_v2(self):
        self.assertEqual(SCENARIO_GEN_VERSION, "gen.v2")
```

Also add `SCENARIO_SCHEMA` and `SCENARIO_GEN_VERSION` to the existing import block at the top of the file (line ~14) if not already imported:

```python
from os_lms.os_lms.ai.simulations.prompts.scenario_generator import (
    SCENARIO_GEN_VERSION,
    SCENARIO_SCHEMA,
    build_scenario_generator_messages,
    parse_scenario_generator_output,
    render_situation_template,
)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.simulations.tests.test_prompts`
Expected: FAIL — `test_parser_reads_student_brief` (AttributeError/KeyError), `test_parser_rejects_missing_student_brief` (no error raised), `test_schema_requires_student_brief`, `test_version_is_v2` (`gen.v1 != gen.v2`).

- [ ] **Step 3: Update the dataclass, schema, parser, version** (tabs) in `scenario_generator.py`:

Change the version constant (line ~24):

```python
SCENARIO_GEN_VERSION = "gen.v2"
```

Add the field to `ScenarioVariant` (after the `persona` line, ~line 45):

```python
@dataclass
class ScenarioVariant:
	situation: str
	persona: PersonaVariant
	student_brief: str
```

Add `student_brief` to the top-level `SCENARIO_SCHEMA` — change `"required"` to include it and add the property (edit the `SCENARIO_SCHEMA` dict, ~lines 48-52):

```python
	"required": ["situation", "student_brief", "persona"],
	"properties": {
		"situation": {
			"type": "string",
			"description": "Setup concreto della scena, 2-5 frasi.",
		},
		"student_brief": {
			"type": "string",
			"description": (
				"Briefing rivolto allo studente, in seconda persona. Spiega la "
				"situazione, chi ha di fronte (nome, ruolo, contesto) e l'obiettivo "
				"da raggiungere. NON rivelare MAI key_objection né hidden_motivation."
			),
		},
```

In `parse_scenario_generator_output`, after the `situation` validation block (~line 179), add the `student_brief` check and pass it to the constructor:

```python
	situation = data.get("situation")
	if not isinstance(situation, str) or not situation.strip():
		raise ValueError("situation is missing or empty")
	student_brief = data.get("student_brief")
	if not isinstance(student_brief, str) or not student_brief.strip():
		raise ValueError("student_brief is missing or empty")

	return ScenarioVariant(
		situation=situation.strip(),
		student_brief=student_brief.strip(),
		persona=PersonaVariant(
			name=persona_data["name"].strip(),
			role=persona_data["role"].strip(),
			context=persona_data["context"].strip(),
			mood=persona_data["mood"].strip(),
			key_objection=persona_data["key_objection"].strip(),
			hidden_motivation=persona_data["hidden_motivation"].strip(),
		),
	)
```

- [ ] **Step 4: Update the default prompt template** (tabs) in `ai/utils/default_prompt/scenario_variant_generator.py`:

Bump version and tokens:

```python
VERSION = "gen.v2"
TEMPERATURE = 0.7
MAX_TOKENS = 900
```

Extend the `SYSTEM_TEMPLATE` — replace the sentence starting `"Genera: nome del personaggio, ..."` block so it also asks for `student_brief`. The new "Genera" paragraph (keep the surrounding text intact):

```python
	"Genera: nome del personaggio, ruolo, contesto/affiliazione (azienda, "
	"scuola, ospedale, ente, studio professionale, ecc. — coerente con il "
	"tipo di persona base), mood iniziale, obiezione o resistenza "
	"principale, motivazione nascosta. Genera inoltre uno student_brief: un "
	"testo rivolto allo studente in seconda persona che spiega la situazione, "
	"chi ha di fronte (nome, ruolo, contesto) e l'obiettivo da raggiungere. "
	"Nello student_brief NON rivelare MAI l'obiezione principale né la "
	"motivazione nascosta: devono restare una sfida da scoprire. La situation "
	"in output deve essere il setup ricevuto eventualmente arricchito con "
	"dettagli plausibili (ma coerenti con i valori già fissati).\n\n"
```

- [ ] **Step 5: Update the test fixture** (4-space indent) in `tests/_fixtures.py` — add `student_brief` to `CANNED_VARIANT` (~line 8):

```python
CANNED_VARIANT = ScenarioVariant(
    situation="Anna ha appena visto un'offerta competitor del -20%.",
    student_brief="Il tuo compito è convincere Anna a confermare l'ordine.",
    persona=PersonaVariant(
        name="Anna",
        role="Head Buyer",
        context="Acme",
        mood="diffidente",
        key_objection="prezzo troppo alto",
        hidden_motivation="budget tagliato dal CFO",
    ),
)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.simulations.tests.test_prompts`
Expected: PASS (all `TestScenarioGenerator` tests including the 4 new ones).

- [ ] **Step 7: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/simulations/prompts/scenario_generator.py \
        apps/os_lms/os_lms/os_lms/ai/utils/default_prompt/scenario_variant_generator.py \
        apps/os_lms/os_lms/os_lms/ai/simulations/tests/_fixtures.py \
        apps/os_lms/os_lms/os_lms/ai/simulations/tests/test_prompts.py
git commit -m "feat(simulations): add AI-generated student_brief to scenario variant"
```

---

## Task 2: Session doctype — `student_brief` field + `Ready` status

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/doctype/lmsa_simulation_session/lmsa_simulation_session.json`
- Modify: `apps/os_lms/os_lms/os_lms/doctype/lmsa_simulation_session/lmsa_simulation_session.py`

**Interfaces:**
- Produces: `STATUS_READY = "Ready"` importable from `lmsa_simulation_session`; session field `student_brief` (Long Text); `status` Select accepts `Ready`.

- [ ] **Step 1: Add the `Ready` status constant** (tabs) in `lmsa_simulation_session.py` — after `STATUS_IN_PROGRESS` (~line 12):

```python
STATUS_READY = "Ready"
STATUS_IN_PROGRESS = "In Progress"
```

`Ready` is intentionally **not** added to `TERMINAL_STATUSES` (a prepared session is still runnable).

- [ ] **Step 2: Add `Ready` to the status Select options** in `lmsa_simulation_session.json` — find the `status` field (`"fieldname": "status"`, ~line 77) and change its `options`:

```json
   "options": "Ready\nIn Progress\nCompleted\nAbandoned\nError\nNeeds Review",
```

- [ ] **Step 3: Add the `student_brief` field** in `lmsa_simulation_session.json` — inside the "Generated Variant" section, add a new field object immediately after the `generated_situation` field object (~line 141, before `generated_persona`):

```json
  {
   "fieldname": "student_brief",
   "fieldtype": "Long Text",
   "label": "Student Brief",
   "read_only": 1
  },
```

Then add `"student_brief"` to the doctype's top-level `"field_order"` array, right after `"generated_situation"`.

- [ ] **Step 4: Migrate the site so the schema change lands**

Run: `bench --site lms.localhost migrate`
Expected: completes without error; `LMSA Simulation Session` reloaded.

- [ ] **Step 5: Verify the field exists**

Run: `bench --site lms.localhost console` then:
```python
import frappe; print(frappe.get_meta("LMSA Simulation Session").get_field("student_brief").fieldtype)
```
Expected: `Long Text`.

- [ ] **Step 6: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/doctype/lmsa_simulation_session/
git commit -m "feat(simulations): add student_brief field and Ready status to session"
```

---

## Task 3: Orchestrator — split into `prepare_session` + `begin_chat_session`, refactor voice, add `clone_session`

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/ai/simulations/orchestrator.py`
- Test: `apps/os_lms/os_lms/os_lms/ai/simulations/tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `STATUS_READY` (Task 2); `ScenarioVariant.student_brief` (Task 1); existing `_generate_variant`, `_persist_turn`, `_first_roleplay_line`, `_persona_from_session`, `_persona_to_dict`, `_model_from_provider`, `_new_seed`, `_scenario_difficulty`.
- Produces:
  - `prepare_session(*, scenario_id: str | Document, modality: str = "chat", seed: str | None = None) -> frappe._dict` → keys `session`, `brief`, `modality`.
  - `begin_chat_session(*, session_id: str) -> frappe._dict` → keys `session`, `first_turn` (`{name, text}`).
  - `start_session(*, scenario_id, modality="chat", seed=None) -> frappe._dict` — unchanged signature/return (`session`, `first_turn`), now composed from the two above.
  - `start_voice_session(*, session_id: str) -> frappe._dict` → keys `session`, `persona`, `situation`, `difficulty`; sets status `In Progress`.
  - `clone_session(*, session_id: str) -> frappe._dict` → keys `session`, `brief`, `modality`.

- [ ] **Step 1: Write failing tests** (4-space indent) — add to `TestOrchestratorLifecycle` in `tests/test_orchestrator.py` (note `_generate_variant` is stubbed to `F.CANNED_VARIANT` by `setUp`, and `STATUS_READY` needs importing):

Add to imports at top:
```python
from os_lms.os_lms.doctype.lmsa_simulation_session.lmsa_simulation_session import STATUS_READY
```

Add tests:
```python
    def test_prepare_session_creates_ready_without_turns(self):
        result = SessionOrchestrator().prepare_session(scenario_id=self.scenario.name)
        session = frappe.get_doc("LMSA Simulation Session", result.session)
        self.assertEqual(session.status, STATUS_READY)
        self.assertEqual(session.student_brief, F.CANNED_VARIANT.student_brief)
        self.assertEqual(result.brief, F.CANNED_VARIANT.student_brief)
        self.assertEqual(
            frappe.db.count("LMSA Simulation Turn", {"session": session.name}), 0
        )

    def test_begin_chat_session_adds_first_turn(self):
        prepared = SessionOrchestrator().prepare_session(scenario_id=self.scenario.name)
        result = SessionOrchestrator().begin_chat_session(session_id=prepared.session)
        session = frappe.get_doc("LMSA Simulation Session", prepared.session)
        self.assertEqual(session.status, "In Progress")
        self.assertEqual(session.turn_count, 1)
        self.assertTrue(result.first_turn.text)

    def test_clone_session_copies_variant_into_ready(self):
        prepared = SessionOrchestrator().prepare_session(scenario_id=self.scenario.name)
        SessionOrchestrator().begin_chat_session(session_id=prepared.session)
        clone = SessionOrchestrator().clone_session(session_id=prepared.session)
        src = frappe.get_doc("LMSA Simulation Session", prepared.session)
        dst = frappe.get_doc("LMSA Simulation Session", clone.session)
        self.assertNotEqual(src.name, dst.name)
        self.assertEqual(dst.status, STATUS_READY)
        self.assertEqual(dst.generated_persona, src.generated_persona)
        self.assertEqual(dst.student_brief, src.student_brief)
        self.assertEqual(
            frappe.db.count("LMSA Simulation Turn", {"session": dst.name}), 0
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.simulations.tests.test_orchestrator`
Expected: FAIL — `AttributeError: 'SessionOrchestrator' object has no attribute 'prepare_session'` (and `begin_chat_session`, `clone_session`).

- [ ] **Step 3: Add `STATUS_READY` to orchestrator imports** (tabs) — extend the existing import block (~line 36):

```python
from os_lms.os_lms.doctype.lmsa_simulation_session.lmsa_simulation_session import (
	STATUS_ABANDONED,
	STATUS_COMPLETED,
	STATUS_ERROR,
	STATUS_IN_PROGRESS,
	STATUS_READY,
	TERMINAL_STATUSES,
)
```

- [ ] **Step 4: Replace `start_session` with the two-phase implementation** (tabs) — in `orchestrator.py`, replace the whole current `start_session` method (~lines 96-158) with:

```python
	def prepare_session(
		self,
		*,
		scenario_id: str | Document,
		modality: str = "chat",
		seed: str | None = None,
	) -> frappe._dict:
		"""Generate the variant and create a Ready session (no turns yet).

		Returns keys: session (name), brief (student_brief), modality.
		"""
		if not self.settings.simulations_enabled:
			frappe.throw(_("AI Simulations are not enabled in LMSA Settings."))

		if isinstance(scenario_id, str):
			scenario = frappe.get_doc("LMSA Simulation Scenario", scenario_id)
			if scenario.status != "Published":
				frappe.throw(
					_("Scenario {0} is not Published (status: {1}).").format(
						scenario.name, scenario.status
					),
					frappe.PermissionError,
				)
		else:
			scenario = scenario_id

		seed = seed or _new_seed()
		provider = self._resolve_provider("chat", scenario)
		variant = self._generate_variant(scenario, seed, provider)

		session = frappe.new_doc("LMSA Simulation Session")
		# Set student BEFORE insert(): the permission gate runs before
		# before_insert(), so has_permission needs `doc.student` already set.
		session.student = frappe.session.user
		session.scenario = scenario.name
		session.modality = modality
		session.status = STATUS_READY
		session.seed = seed
		session.prompt_version = f"{SCENARIO_GEN_VERSION}+{ROLE_PLAY_VERSION}"
		session.generated_situation = variant.situation
		session.student_brief = variant.student_brief
		session.generated_persona = json.dumps(
			_persona_to_dict(variant.persona), ensure_ascii=False
		)
		session.chat_provider_used = provider.name
		session.chat_model_used = _model_from_provider(provider)
		session.insert()
		frappe.db.commit()

		self.logger.info(
			"simulation prepare: session=%s scenario=%s seed=%s provider=%s",
			session.name,
			scenario.name,
			seed,
			provider.name,
		)
		return frappe._dict(
			session=session.name,
			brief=variant.student_brief,
			modality=modality,
		)

	def begin_chat_session(self, *, session_id: str) -> frappe._dict:
		"""Persist the first role-player turn for a prepared chat session.

		Returns keys: session (name), first_turn ({name, text}).
		"""
		session = frappe.get_doc("LMSA Simulation Session", session_id)
		if session.status == STATUS_IN_PROGRESS and (session.turn_count or 0) > 0:
			# Idempotent: already begun. Return the existing first turn.
			first = frappe.get_all(
				"LMSA Simulation Turn",
				filters={"session": session.name, "role": "assistant"},
				fields=["name", "text_content"],
				order_by="turn_index asc",
				limit=1,
			)
			if first:
				return frappe._dict(
					session=session.name,
					first_turn=frappe._dict(name=first[0].name, text=first[0].text_content),
				)

		variant = ScenarioVariant(
			situation=session.generated_situation or "",
			student_brief=session.student_brief or "",
			persona=_persona_from_session(session),
		)
		first_turn = self._persist_turn(
			session=session,
			role="assistant",
			text=_first_roleplay_line(variant),
			provider_used=session.chat_provider_used,
			model_used=session.chat_model_used,
		)
		session.status = STATUS_IN_PROGRESS
		session.turn_count = 1
		session.save()
		frappe.db.commit()

		self.logger.info("simulation begin: session=%s", session.name)
		return frappe._dict(
			session=session.name,
			first_turn=frappe._dict(name=first_turn.name, text=first_turn.text_content),
		)

	def start_session(
		self,
		*,
		scenario_id: str,
		modality: str = "chat",
		seed: str | None = None,
	) -> frappe._dict:
		"""Prepare + begin in one call (chat). Preserved for internal callers
		(eval runner, instructor Test Run, tests)."""
		prepared = self.prepare_session(
			scenario_id=scenario_id, modality=modality, seed=seed
		)
		begun = self.begin_chat_session(session_id=prepared.session)
		return frappe._dict(session=prepared.session, first_turn=begun.first_turn)
```

- [ ] **Step 5: Refactor `start_voice_session` to reuse a prepared session** (tabs) — replace the current `start_voice_session` method (~lines 279-326) with:

```python
	def start_voice_session(self, *, session_id: str) -> frappe._dict:
		"""Activate a prepared voice Session for live realtime streaming.

		Reuses the persona/situation generated at prepare time (no
		regeneration). Marks the session In Progress. Returns the data the
		realtime control-plane needs to build the model instructions.
		"""
		if not self.settings.simulations_enabled:
			frappe.throw(_("AI Simulations are not enabled in LMSA Settings."))

		session = frappe.get_doc("LMSA Simulation Session", session_id)
		if session.status in TERMINAL_STATUSES:
			raise SessionTerminatedError(
				f"Session {session_id} is in terminal state {session.status!r}"
			)
		if session.status != STATUS_IN_PROGRESS:
			session.status = STATUS_IN_PROGRESS
			session.save()
			frappe.db.commit()

		return frappe._dict(
			session=session.name,
			persona=_persona_from_session(session),
			situation=session.generated_situation,
			difficulty=_scenario_difficulty(session.scenario),
		)
```

- [ ] **Step 6: Add `clone_session`** (tabs) — add this method next to the other public lifecycle methods (e.g. after `end_session`):

```python
	def clone_session(self, *, session_id: str) -> frappe._dict:
		"""Create a new Ready session copying the source variant (same
		persona/situation/brief). Used to retry an identical challenge.

		Returns keys: session (name), brief, modality.
		"""
		src = frappe.get_doc("LMSA Simulation Session", session_id)
		clone = frappe.new_doc("LMSA Simulation Session")
		clone.student = frappe.session.user
		clone.scenario = src.scenario
		clone.modality = src.modality
		clone.status = STATUS_READY
		clone.seed = src.seed
		clone.prompt_version = src.prompt_version
		clone.generated_situation = src.generated_situation
		clone.generated_persona = src.generated_persona
		clone.student_brief = src.student_brief
		clone.chat_provider_used = src.chat_provider_used
		clone.chat_model_used = src.chat_model_used
		clone.insert()
		frappe.db.commit()
		self.logger.info("simulation clone: src=%s new=%s", src.name, clone.name)
		return frappe._dict(
			session=clone.name,
			brief=clone.student_brief,
			modality=clone.modality,
		)
```

- [ ] **Step 7: Run the orchestrator tests**

Run: `bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.simulations.tests.test_orchestrator`
Expected: PASS — the 3 new tests plus the existing `test_start_session_*` tests (which now exercise the composed path).

- [ ] **Step 8: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/simulations/orchestrator.py \
        apps/os_lms/os_lms/os_lms/ai/simulations/tests/test_orchestrator.py
git commit -m "feat(simulations): split start into prepare/begin, reuse prepared voice session, add clone_session"
```

---

## Task 4: Simulations API — `prepare_session`, `begin_session`, `list_my_sessions`, `clone_session`, `get_session` brief

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/ai/simulations/api.py`
- Test: `apps/os_lms/os_lms/os_lms/ai/simulations/tests/test_api.py`

**Interfaces:**
- Consumes: orchestrator `prepare_session`, `begin_chat_session`, `clone_session` (Task 3); `load_session`, `_resolve_published_scenario` (existing).
- Produces (whitelisted):
  - `prepare_session(scenario_id: str, modality: str = "chat") -> dict` → `{session_id, brief, modality}`.
  - `begin_session(session_id: str) -> dict` → `{session, first_turn}`.
  - `clone_session(session_id: str) -> dict` → `{session_id, brief, modality}`.
  - `list_my_sessions(course: str | None = None) -> list[dict]` → rows `{name, scenario, scenario_name, modality, status, started_at, ended_at, turn_count, overall_score, passed, debrief_status}`.
  - `get_session(session_id)` payload `session` dict gains `student_brief`.

- [ ] **Step 1: Write failing tests** (4-space indent) — add to `tests/test_api.py`. Extend the import block (~line 19) and add tests to the existing test class (uses the same `self.scenario` fixture as `start_session` tests):

```python
from os_lms.os_lms.ai.simulations.api import (
    begin_session,
    clone_session,
    end_session,
    get_session,
    list_my_sessions,
    prepare_session,
    start_session,
)
```

```python
    def test_prepare_then_begin(self):
        prepared = prepare_session(scenario_id=self.scenario.name)
        self.assertIn("session_id", prepared)
        self.assertTrue(prepared["brief"])
        detail = get_session(session_id=prepared["session_id"])
        self.assertEqual(detail["session"]["status"], "Ready")
        self.assertEqual(len(detail["turns"]), 0)
        self.assertEqual(
            detail["session"]["student_brief"], prepared["brief"]
        )

        begun = begin_session(session_id=prepared["session_id"])
        self.assertTrue(begun["first_turn"]["text"])
        detail2 = get_session(session_id=prepared["session_id"])
        self.assertEqual(detail2["session"]["status"], "In Progress")
        self.assertEqual(len(detail2["turns"]), 1)

    def test_list_my_sessions_returns_only_owner(self):
        prepared = prepare_session(scenario_id=self.scenario.name)
        rows = list_my_sessions(course=self.scenario.lms_course)
        names = [r["name"] for r in rows]
        self.assertIn(prepared["session_id"], names)
        row = next(r for r in rows if r["name"] == prepared["session_id"])
        self.assertEqual(row["scenario"], self.scenario.name)
        self.assertEqual(row["status"], "Ready")

    def test_clone_session_endpoint(self):
        start = start_session(scenario_id=self.scenario.name)
        end_session(session_id=start["session"], reason="completed")
        clone = clone_session(session_id=start["session"])
        self.assertNotEqual(clone["session_id"], start["session"])
        detail = get_session(session_id=clone["session_id"])
        self.assertEqual(detail["session"]["status"], "Ready")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.simulations.tests.test_api`
Expected: FAIL — `ImportError: cannot import name 'prepare_session'`.

- [ ] **Step 3: Add the new endpoints** (4-space indent) in `simulations/api.py`, immediately after the existing `start_session` endpoint (~line 105):

```python
@frappe.whitelist()
def prepare_session(scenario_id: str, modality: str = "chat") -> dict:
    """Phase 1: generate the variant and create a Ready session with a brief."""
    if modality not in ("chat", "voice"):
        frappe.throw(_("Unsupported modality: {0}").format(modality))

    scenario = _resolve_published_scenario(scenario_id)
    if modality == "chat" and scenario.modality not in ("chat", "both"):
        frappe.throw(_("Scenario {0} is not chat-enabled.").format(scenario.name))
    if modality == "voice" and scenario.modality not in ("voice", "both"):
        frappe.throw(_("Scenario {0} is not voice-enabled.").format(scenario.name))

    try:
        result = _service().prepare_session(scenario_id=scenario.name, modality=modality)
    except QuotaExceededError as e:
        frappe.throw(str(e), frappe.ValidationError)
    return {"session_id": result.session, "brief": result.brief, "modality": result.modality}


@frappe.whitelist()
def begin_session(session_id: str) -> dict:
    """Phase 2 (chat): persist the first role-player turn for a prepared session."""
    session = load_session(session_id)
    if session.student != frappe.session.user:
        frappe.throw(_("Only the session owner can begin the session"), frappe.PermissionError)
    return dict(_service().begin_chat_session(session_id=session.name))


@frappe.whitelist()
def clone_session(session_id: str) -> dict:
    """Restart a session: create a new Ready session reusing the same variant."""
    session = load_session(session_id)
    if session.student != frappe.session.user:
        frappe.throw(_("Only the session owner can restart it"), frappe.PermissionError)
    result = _service().clone_session(session_id=session.name)
    return {"session_id": result.session, "brief": result.brief, "modality": result.modality}
```

- [ ] **Step 4: Add `list_my_sessions`** (4-space indent) — add near the other list endpoints (e.g. after `list_scenarios`, ~line 337):

```python
@frappe.whitelist()
def list_my_sessions(course: str | None = None) -> list[dict]:
    """List the current user's own simulation sessions (optionally by course),
    enriched with the debrief score/status when available."""
    filters: dict = {"student": frappe.session.user}
    if course:
        filters["course"] = course

    sessions = frappe.get_all(
        "LMSA Simulation Session",
        filters=filters,
        fields=[
            "name",
            "scenario",
            "modality",
            "status",
            "started_at",
            "ended_at",
            "turn_count",
        ],
        order_by="started_at desc",
    )
    if not sessions:
        return []

    scenario_names = {s["scenario"] for s in sessions if s["scenario"]}
    titles = {
        r["name"]: r["scenario_name"]
        for r in frappe.get_all(
            "LMSA Simulation Scenario",
            filters={"name": ["in", list(scenario_names)]},
            fields=["name", "scenario_name"],
        )
    }
    debriefs = {
        d["session"]: d
        for d in frappe.get_all(
            "LMSA Simulation Debrief",
            filters={"session": ["in", [s["name"] for s in sessions]]},
            fields=["session", "overall_score", "passed", "status"],
        )
    }

    for s in sessions:
        s["scenario_name"] = titles.get(s["scenario"], s["scenario"])
        s["started_at"] = str(s["started_at"]) if s["started_at"] else None
        s["ended_at"] = str(s["ended_at"]) if s["ended_at"] else None
        d = debriefs.get(s["name"])
        s["overall_score"] = d["overall_score"] if d else None
        s["passed"] = bool(d["passed"]) if d else None
        s["debrief_status"] = d["status"] if d else None
    return sessions
```

- [ ] **Step 5: Add `student_brief` to `get_session` payload and treat `Ready` as not-started in `get_debrief`** (4-space indent):

In `get_session`, add to the `"session"` dict (after `"generated_situation"`, ~line 190):

```python
            "generated_situation": session.generated_situation,
            "student_brief": session.student_brief,
```

In `get_debrief`, widen the not-started guard (~line 216):

```python
    if session.status in ("In Progress", "Ready"):
        return {"status": "not_started", "session": session.name, "course": session.course}
```

- [ ] **Step 6: Run the api tests**

Run: `bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.simulations.tests.test_api`
Expected: PASS (new tests + existing ones).

- [ ] **Step 7: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/simulations/api.py \
        apps/os_lms/os_lms/os_lms/ai/simulations/tests/test_api.py
git commit -m "feat(simulations): add prepare/begin/clone/list_my_sessions endpoints and student_brief in get_session"
```

---

## Task 5: Realtime API — `create_voice_session(session_id)`

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/ai/realtime/api.py`
- Test: `apps/os_lms/os_lms/os_lms/ai/realtime/tests/test_realtime_api.py`

**Interfaces:**
- Consumes: orchestrator `start_voice_session(session_id=...)` (Task 3); `load_session` (existing).
- Produces: `create_voice_session(session_id: str) -> dict` — same return descriptor as before (`session_id, transport, connect_url, client_secret, voice, model, expires_at, max_seconds, extra`), now driven by a prepared session.

- [ ] **Step 1: Inspect the existing realtime test to mirror its setup**

Run: `sed -n '1,80p' apps/os_lms/os_lms/os_lms/ai/realtime/tests/test_realtime_api.py`
Expected: shows how it currently calls `create_voice_session(scenario_id=...)` and enables realtime — you will update those calls to prepare a session first.

- [ ] **Step 2: Update the failing test** (4-space indent) — change existing calls from `create_voice_session(scenario_id=<scenario>)` to a two-step prepare, e.g.:

```python
    def test_create_voice_session_from_prepared(self):
        prepared = prepare_session(scenario_id=self.scenario.name, modality="voice")
        res = create_voice_session(session_id=prepared["session_id"])
        self.assertEqual(res["session_id"], prepared["session_id"])
        self.assertTrue(res["transport"])
```

Add `from os_lms.os_lms.ai.simulations.api import prepare_session` to the test imports. Ensure the fixture scenario has `modality` `voice` or `both` (mirror the existing realtime fixture; if it is chat-only, set `modality="both"` when creating it).

- [ ] **Step 3: Run test to verify it fails**

Run: `bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.realtime.tests.test_realtime_api`
Expected: FAIL — `create_voice_session()` still requires `scenario_id`.

- [ ] **Step 4: Rewrite `create_voice_session`** (tabs) in `realtime/api.py` — replace the signature and the scenario-resolution/`start_voice_session` block (~lines 48-63) with a session-driven version; the instruction-building and token-minting below it stay unchanged:

```python
@frappe.whitelist()
def create_voice_session(session_id: str) -> dict:
	"""Activate a prepared voice Session, mint an ephemeral provider token, and
	return the descriptor the client needs to open the direct realtime stream."""
	settings = load_settings()
	if not settings.realtime_enabled:
		frappe.throw(_("Realtime voice is not enabled."), frappe.PermissionError)

	session = load_session(session_id)
	if session.student != frappe.session.user:
		frappe.throw(_("Only the session owner can start voice."), frappe.PermissionError)

	scenario = frappe.get_doc("LMSA Simulation Scenario", session.scenario)
	if scenario.modality not in ("voice", "both"):
		frappe.throw(_("Scenario {0} is not voice-enabled.").format(scenario.name))

	try:
		started = _service().start_voice_session(session_id=session.name)
	except SessionTerminatedError:
		frappe.throw(_("This session is no longer accepting turns."), frappe.ValidationError)
	except QuotaExceededError as e:
		frappe.throw(str(e), frappe.ValidationError)
```

Everything from `# Build the realtime instructions ...` down to the `return {...}` stays exactly as-is (it already reads `started.persona`, `started.situation`, `started.difficulty`, `started.session`, and `scenario.*`).

Confirm `SessionTerminatedError` is imported at the top of the file (it is imported from `orchestrator` already alongside `QuotaExceededError`).

- [ ] **Step 5: Run the realtime tests**

Run: `bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.realtime.tests.test_realtime_api`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/realtime/api.py \
        apps/os_lms/os_lms/os_lms/ai/realtime/tests/test_realtime_api.py
git commit -m "feat(realtime): drive create_voice_session from a prepared session"
```

---

## Task 6: Shared briefing UI + begin composable (frontend)

**Files:**
- Create: `frontend/src/oslms/components/simulations/SimulationBriefing.vue`
- Create: `frontend/src/oslms/composables/useSimulationBegin.js`

**Interfaces:**
- Produces:
  - `SimulationBriefing.vue` — props `{ brief: String, modality: String, starting: Boolean }`; emits `begin` with payload `'chat' | 'voice'`. For `modality === 'both'` renders two buttons (Avvia chat / Avvia voce); otherwise a single button matching the modality.
  - `useSimulationBegin()` — returns `{ beginning: Ref<boolean>, voiceSessionId: Ref<string|null>, begin: ({sessionId, mode}) => Promise<void>, clearVoice: () => void }`. `begin` with `mode==='chat'` calls `begin_session` then routes to `SimulationPlay`; `mode==='voice'` sets `voiceSessionId` (parent renders `<VoiceSession>`).

- [ ] **Step 1: Create the begin composable**

```javascript
// frontend/src/oslms/composables/useSimulationBegin.js
/**
 * Shared "phase 2" start logic for a prepared simulation session.
 * chat  -> begin_session then navigate to the play page.
 * voice -> expose the session id so the caller can mount <VoiceSession>.
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { createResource, toast } from 'frappe-ui'

export function useSimulationBegin() {
	const router = useRouter()
	const beginning = ref(false)
	const voiceSessionId = ref(null)

	const beginRes = createResource({
		url: 'os_lms.os_lms.ai.simulations.api.begin_session',
		method: 'POST',
	})

	async function begin({ sessionId, mode }) {
		if (!sessionId) return
		if (mode === 'voice') {
			voiceSessionId.value = sessionId
			return
		}
		beginning.value = true
		try {
			await beginRes.submit({ session_id: sessionId })
			router.push({ name: 'SimulationPlay', params: { sessionId } })
		} catch (e) {
			toast.error(e.messages?.[0] || e.message || String(e))
		} finally {
			beginning.value = false
		}
	}

	function clearVoice() {
		voiceSessionId.value = null
	}

	return { beginning, voiceSessionId, begin, clearVoice }
}
```

- [ ] **Step 2: Create the briefing component**

```vue
<!-- frontend/src/oslms/components/simulations/SimulationBriefing.vue -->
<template>
	<div class="space-y-4">
		<div
			class="whitespace-pre-wrap text-sm text-ink-gray-8 border border-outline-gray-2 rounded-md p-4 bg-surface-gray-1"
		>
			{{ brief || __('Nessun briefing disponibile.') }}
		</div>
		<div class="flex gap-2 justify-end">
			<template v-if="modality === 'both'">
				<Button
					variant="outline"
					:loading="starting"
					@click="emit('begin', 'voice')"
				>
					{{ __('Avvia voce') }}
				</Button>
				<Button
					variant="solid"
					:loading="starting"
					@click="emit('begin', 'chat')"
				>
					{{ __('Avvia chat') }}
				</Button>
			</template>
			<Button
				v-else
				variant="solid"
				:loading="starting"
				@click="emit('begin', modality)"
			>
				{{ modality === 'voice' ? __('Avvia voce') : __('Avvia chat') }}
			</Button>
		</div>
	</div>
</template>

<script setup>
import { Button } from 'frappe-ui'

defineProps({
	brief: { type: String, default: '' },
	modality: { type: String, default: 'chat' },
	starting: { type: Boolean, default: false },
})
const emit = defineEmits(['begin'])
</script>
```

- [ ] **Step 3: Verify the frontend still builds**

Run: `cd frontend && yarn build`
Expected: build succeeds (new files compile; not yet imported anywhere).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/oslms/components/simulations/SimulationBriefing.vue \
        frontend/src/oslms/composables/useSimulationBegin.js
git commit -m "feat(simulations-ui): add shared SimulationBriefing component and useSimulationBegin composable"
```

---

## Task 7: Two-phase `SimulationLauncher` + voice `VoiceSession`/`useRealtimeSession` by session id

**Files:**
- Modify: `frontend/src/oslms/components/simulations/SimulationLauncher.vue`
- Modify: `frontend/src/oslms/composables/useRealtimeSession.js`
- Modify: `frontend/src/oslms/components/simulations/VoiceSession.vue`

**Interfaces:**
- Consumes: `SimulationBriefing.vue`, `useSimulationBegin()` (Task 6); `prepare_session`, `create_voice_session(session_id)` (Tasks 4-5).
- Produces: `VoiceSession.vue` prop renamed `scenarioId` → `sessionId`; `useRealtimeSession().start(sessionId)` posts `{ session_id }`.

- [ ] **Step 1: Update `useRealtimeSession.js` to start from a session id** — change `start(scenarioId)` to `start(sessionId)` and the submit payload:

Replace the `start` signature line:
```javascript
	async function start(sessionId) {
```
Replace the create-session submit call inside `start`:
```javascript
			const res = await createSessionRes.submit({
				session_id: sessionId,
			})
```
(The rest of `start` — `sessionId.value = res.session_id`, transport wiring, timer — is unchanged. Note: `create_voice_session` returns the same `session_id`, so `sessionId.value` stays correct.)

- [ ] **Step 2: Update `VoiceSession.vue` to accept `sessionId`** — change the prop and the `onStart` call:

Replace the props line:
```javascript
const props = defineProps({ sessionId: { type: String, required: true } })
```
Replace `onStart`:
```javascript
async function onStart() {
	await start(props.sessionId)
}
```

- [ ] **Step 3: Rewrite `SimulationLauncher.vue` for the two-phase flow** — replace the whole file with:

```vue
<template>
	<!-- Voice runtime overlay (phase 2, voice): mounted once a session is
	     prepared and the student chose "Avvia voce". -->
	<Dialog
		v-if="voiceSessionId"
		v-model="voiceDialogOpen"
		:options="{ title: __('Simulazione vocale'), size: 'lg' }"
	>
		<template #body-content>
			<VoiceSession :session-id="voiceSessionId" @ended="onVoiceEnded" />
		</template>
	</Dialog>

	<Dialog
		v-model="visible"
		:options="{
			title: step === 'briefing' ? __('Preparati alla simulazione') : __('Avvia una simulazione'),
			size: 'lg',
		}"
	>
		<template #body-content>
			<!-- Phase 1: scenario selection -->
			<template v-if="step === 'select'">
				<div v-if="!scenarios?.length" class="text-sm text-ink-gray-5 py-4">
					{{ __('Nessuno scenario disponibile per questa lezione.') }}
				</div>
				<div v-else class="space-y-3">
					<button
						v-for="sc in scenarios"
						:key="sc.name"
						type="button"
						:disabled="preparing"
						class="w-full text-left border border-outline-gray-2 rounded-md p-3 hover:bg-surface-gray-1 disabled:opacity-50"
						:class="{ 'ring-2 ring-outline-gray-3': sc.name === selected }"
						@click="selected = sc.name"
					>
						<div class="font-medium text-ink-gray-9">
							{{ sc.scenario_name }}
						</div>
						<div class="text-xs text-ink-gray-5 mt-1 flex gap-3">
							<Badge :label="sc.difficulty" :theme="difficultyTheme(sc.difficulty)" />
							<span class="capitalize">{{ sc.modality }}</span>
						</div>
					</button>
				</div>
			</template>

			<!-- Phase 2: briefing -->
			<SimulationBriefing
				v-else
				:brief="brief"
				:modality="briefModality"
				:starting="beginning"
				@begin="onBegin"
			/>

			<div v-if="error" class="text-sm text-ink-red-3 mt-3">{{ error }}</div>
		</template>
		<template #actions>
			<div class="flex gap-2 justify-end">
				<Button v-if="step === 'briefing'" @click="backToSelect">
					{{ __('Indietro') }}
				</Button>
				<Button v-else @click="visible = false">{{ __('Annulla') }}</Button>
				<Button
					v-if="step === 'select'"
					variant="solid"
					:loading="preparing"
					:disabled="!selected"
					@click="onPrepare"
				>
					{{ __('Avvia') }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Badge, Button, Dialog, createResource, toast } from 'frappe-ui'
import VoiceSession from './VoiceSession.vue'
import SimulationBriefing from './SimulationBriefing.vue'
import { useSimulationBegin } from '../../composables/useSimulationBegin'

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	scenarios: { type: Array, default: () => [] },
	modality: { type: String, default: 'chat' },
})
const emit = defineEmits(['update:modelValue', 'started'])

const selected = ref(null)
const preparing = ref(false)
const error = ref(null)
const step = ref('select') // select | briefing
const brief = ref('')
const preparedSessionId = ref(null)
const briefModality = ref('chat')

const { beginning, voiceSessionId, begin, clearVoice } = useSimulationBegin()

const voiceDialogOpen = computed({
	get: () => Boolean(voiceSessionId.value),
	set: (v) => {
		if (!v) clearVoice()
	},
})

const selectedScenario = computed(() =>
	props.scenarios?.find((sc) => sc.name === selected.value),
)

const visible = computed({
	get: () => props.modelValue,
	set: (v) => emit('update:modelValue', v),
})

watch(visible, (v) => {
	if (v) {
		selected.value = props.scenarios?.[0]?.name || null
		error.value = null
		step.value = 'select'
	}
})

const prepareRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.prepare_session',
	method: 'POST',
})

// A scenario declaring modality "both" is prepared as "voice" so the backend
// gate passes; the briefing then offers both chat and voice buttons.
function requestedModality(scMod) {
	if (scMod === 'both') return 'voice'
	return scMod || props.modality
}

async function onPrepare() {
	if (!selected.value) return
	preparing.value = true
	error.value = null
	try {
		const result = await prepareRes.submit({
			scenario_id: selected.value,
			modality: requestedModality(selectedScenario.value?.modality),
		})
		if (!result?.session_id) throw new Error(__('Preparazione fallita.'))
		preparedSessionId.value = result.session_id
		brief.value = result.brief
		briefModality.value = selectedScenario.value?.modality || 'chat'
		step.value = 'briefing'
		emit('started', result)
	} catch (e) {
		error.value = e.messages?.[0] || e.message || String(e)
		toast.error(error.value)
	} finally {
		preparing.value = false
	}
}

async function onBegin(mode) {
	if (mode === 'voice') visible.value = false
	await begin({ sessionId: preparedSessionId.value, mode })
}

function backToSelect() {
	step.value = 'select'
}

function onVoiceEnded() {
	clearVoice()
}

function difficultyTheme(diff) {
	return { easy: 'green', medium: 'blue', hard: 'orange' }[diff] || 'gray'
}
</script>
```

- [ ] **Step 4: Verify the frontend builds**

Run: `cd frontend && yarn build`
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/oslms/components/simulations/SimulationLauncher.vue \
        frontend/src/oslms/components/simulations/VoiceSession.vue \
        frontend/src/oslms/composables/useRealtimeSession.js
git commit -m "feat(simulations-ui): two-phase launcher with briefing; drive voice by session id"
```

---

## Task 8: Brief side-panel in the chat runtime

**Files:**
- Modify: `frontend/src/oslms/pages/Simulation/SimulationPlay.vue`
- Modify: `frontend/src/oslms/components/simulations/ChatSession.vue`

**Interfaces:**
- Consumes: `get_session` now returns `student_brief` (Task 4).
- Produces: `SimulationPlay.vue` renders a two-column layout — `ChatSession` on the left, brief panel on the right; passes `studentBrief` down or renders the panel itself.

- [ ] **Step 1: Add a brief side-panel in `SimulationPlay.vue`** — replace the root wrapper and the `<ChatSession .../>` block so the chat sits left and the brief sits right. Change the outer container and add the panel:

Replace the opening wrapper `<div class="flex flex-col h-screen max-w-3xl mx-auto">` with:
```html
	<div class="flex flex-col h-screen max-w-6xl mx-auto">
```

Wrap the `<ChatSession .../>` in a two-column flex row and add the brief aside (inside the existing `<template v-else>`), replacing the current `<ChatSession .../>` element:
```html
			<div class="flex flex-1 min-h-0 gap-4 px-4 pb-4">
				<ChatSession
					class="flex-1 min-w-0"
					:scenarioName="scenarioName"
					:persona="persona"
					:turns="turns"
					:status="session.status"
					:sending="sending"
					:ending="ending"
					@send="onSend"
					@end="onEnd"
				/>
				<aside
					v-if="studentBrief"
					class="hidden md:block w-80 shrink-0 overflow-y-auto border border-outline-gray-2 rounded-md p-4 bg-surface-gray-1"
				>
					<div class="text-sm font-semibold text-ink-gray-9 mb-2">
						{{ __('Il tuo compito') }}
					</div>
					<div class="whitespace-pre-wrap text-sm text-ink-gray-7">
						{{ studentBrief }}
					</div>
				</aside>
			</div>
```

Add the computed in `<script setup>` (after `persona`):
```javascript
const studentBrief = computed(() => session.value?.student_brief || '')
```

- [ ] **Step 2: (No change needed in `ChatSession.vue` for the brief)** — the panel lives in `SimulationPlay.vue`. Verify `ChatSession.vue` still receives `class="flex-1 min-w-0"` correctly (it already renders `<div class="flex flex-col h-full">` as its root, which fills the column). No edit required unless the build flags an unused prop; skip.

- [ ] **Step 3: Verify the frontend builds**

Run: `cd frontend && yarn build`
Expected: build succeeds.

- [ ] **Step 4: Manual verification (Docker running)**

Prepare + begin a chat session via the launcher, then confirm on `/simulations/:sessionId` the chat is on the left and the "Il tuo compito" panel on the right (desktop width). Note it in the commit if screenshots are captured.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/oslms/pages/Simulation/SimulationPlay.vue
git commit -m "feat(simulations-ui): show student brief beside the chat runtime"
```

---

## Task 9: Brief panel in the voice runtime

**Files:**
- Modify: `frontend/src/oslms/components/simulations/VoiceSession.vue`

**Interfaces:**
- Consumes: `get_session` `student_brief` (Task 4); `sessionId` prop (Task 7).

- [ ] **Step 1: Fetch and show the brief in `VoiceSession.vue`** — add a resource to load the prepared session's brief and render it beside the transcript.

Add to `<script setup>` (after the existing composable destructure):
```javascript
import { createResource } from 'frappe-ui'

const studentBrief = ref('')
const sessionRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.get_session',
	method: 'GET',
	makeParams: () => ({ session_id: props.sessionId }),
	onSuccess: (data) => {
		studentBrief.value = data?.session?.student_brief || ''
	},
})
sessionRes.reload()
```
Ensure `ref` is in the existing `import { ... } from 'vue'` line.

Wrap the existing content in a two-column layout: change the root `<div class="flex flex-col gap-4 p-4">` to a row that keeps the voice controls left and adds the brief right:
```html
	<div class="flex gap-4 p-4">
		<div class="flex flex-col gap-4 flex-1 min-w-0">
			<!-- existing state row, transcript scroller, and buttons stay here -->
		</div>
		<aside
			v-if="studentBrief"
			class="hidden md:block w-72 shrink-0 overflow-y-auto border border-outline-gray-2 rounded-md p-3 bg-surface-gray-1"
			style="max-height: 60vh"
		>
			<div class="text-sm font-semibold text-ink-gray-9 mb-2">
				{{ __('Il tuo compito') }}
			</div>
			<div class="whitespace-pre-wrap text-sm text-ink-gray-7">
				{{ studentBrief }}
			</div>
		</aside>
	</div>
```
Move the three existing children (the state `<div class="flex items-center justify-between">`, the transcript `<div ref="scroller" ...>`, and the buttons `<div class="flex gap-2">`) inside the new left column `<div class="flex flex-col gap-4 flex-1 min-w-0">`.

- [ ] **Step 2: Verify the frontend builds**

Run: `cd frontend && yarn build`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/oslms/components/simulations/VoiceSession.vue
git commit -m "feat(simulations-ui): show student brief beside the voice runtime"
```

---

## Task 10: Student "Simulazioni" course tab

**Files:**
- Create: `frontend/src/oslms/pages/Courses/CourseStudentSimulations.vue`
- Modify: `frontend/src/pages/Courses/CourseDetail.vue`

**Interfaces:**
- Consumes: `list_scenarios`, `list_my_sessions`, `clone_session`, `get_session` (Task 4); `SimulationLauncher.vue` (Task 7), `SimulationBriefing.vue` + `useSimulationBegin` (Task 6), `VoiceSession.vue` (Task 7).
- Produces: a `course`-prop component rendered as the student `simulations` tab.

- [ ] **Step 1: Create `CourseStudentSimulations.vue`**

```vue
<!-- frontend/src/oslms/pages/Courses/CourseStudentSimulations.vue -->
<template>
	<div class="p-5 space-y-8 overflow-y-auto">
		<!-- New simulation -->
		<section>
			<div class="flex items-center justify-between mb-3">
				<h2 class="text-lg font-semibold text-ink-gray-9">
					{{ __('Avvia una nuova simulazione') }}
				</h2>
				<Button
					variant="solid"
					:disabled="!scenariosRes.data?.length"
					@click="launcherOpen = true"
				>
					<template #prefix><span class="lucide-bot size-4" /></template>
					{{ __('Nuova simulazione') }}
				</Button>
			</div>
			<div v-if="!scenariosRes.data?.length" class="text-sm text-ink-gray-5">
				{{ __('Nessuno scenario disponibile per questo corso.') }}
			</div>
		</section>

		<!-- History -->
		<section>
			<h2 class="text-lg font-semibold text-ink-gray-9 mb-3">
				{{ __('Le tue simulazioni') }}
			</h2>
			<div v-if="!sessionsRes.data?.length" class="text-sm text-ink-gray-5">
				{{ __('Non hai ancora svolto simulazioni per questo corso.') }}
			</div>
			<table v-else class="w-full text-sm">
				<thead class="text-left text-ink-gray-5">
					<tr>
						<th class="py-2">{{ __('Scenario') }}</th>
						<th>{{ __('Modalità') }}</th>
						<th>{{ __('Stato') }}</th>
						<th>{{ __('Punteggio') }}</th>
						<th>{{ __('Data') }}</th>
						<th></th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="s in sessionsRes.data"
						:key="s.name"
						class="border-t border-outline-gray-1"
					>
						<td class="py-2">{{ s.scenario_name }}</td>
						<td class="capitalize">{{ s.modality }}</td>
						<td><Badge :label="s.status" :theme="statusTheme(s.status)" /></td>
						<td>
							{{ s.overall_score != null ? s.overall_score : '—' }}
						</td>
						<td>{{ formatDate(s.started_at) }}</td>
						<td class="text-right">
							<div class="flex gap-2 justify-end">
								<Button
									v-if="isTerminal(s.status)"
									variant="subtle"
									size="sm"
									@click="goDebrief(s.name)"
								>
									{{ __('Rivedi') }}
								</Button>
								<Button
									v-if="isTerminal(s.status)"
									variant="outline"
									size="sm"
									:loading="busyId === s.name"
									@click="onRestart(s.name)"
								>
									{{ __('Riavvia') }}
								</Button>
								<Button
									v-else-if="s.status === 'Ready'"
									variant="solid"
									size="sm"
									:loading="busyId === s.name"
									@click="onContinueReady(s)"
								>
									{{ __('Continua') }}
								</Button>
								<Button
									v-else-if="s.status === 'In Progress' && s.modality === 'chat'"
									variant="solid"
									size="sm"
									@click="goPlay(s.name)"
								>
									{{ __('Riprendi') }}
								</Button>
								<Button
									v-else-if="s.status === 'In Progress' && s.modality === 'voice'"
									variant="subtle"
									size="sm"
									@click="goPlay(s.name)"
								>
									{{ __('Rivedi trascrizione') }}
								</Button>
							</div>
						</td>
					</tr>
				</tbody>
			</table>
		</section>

		<!-- Launcher for new sessions (own briefing flow inside) -->
		<SimulationLauncher
			v-model="launcherOpen"
			:scenarios="scenariosRes.data || []"
			@started="onLauncherStarted"
		/>

		<!-- Briefing dialog for restart / continue-ready -->
		<Dialog
			v-model="briefingOpen"
			:options="{ title: __('Preparati alla simulazione'), size: 'lg' }"
		>
			<template #body-content>
				<SimulationBriefing
					:brief="briefing.brief"
					:modality="briefing.modality"
					:starting="beginning"
					@begin="onBriefBegin"
				/>
			</template>
		</Dialog>

		<!-- Voice runtime overlay -->
		<Dialog
			v-if="voiceSessionId"
			v-model="voiceDialogOpen"
			:options="{ title: __('Simulazione vocale'), size: 'lg' }"
		>
			<template #body-content>
				<VoiceSession :session-id="voiceSessionId" @ended="onVoiceEnded" />
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Badge, Button, Dialog, createResource, toast } from 'frappe-ui'
import SimulationLauncher from '@/oslms/components/simulations/SimulationLauncher.vue'
import SimulationBriefing from '@/oslms/components/simulations/SimulationBriefing.vue'
import VoiceSession from '@/oslms/components/simulations/VoiceSession.vue'
import { useSimulationBegin } from '@/oslms/composables/useSimulationBegin'

const props = defineProps({
	// CourseDetail passes the `course` Resource object.
	course: { type: Object, required: true },
})

const router = useRouter()
const courseName = computed(() => props.course?.data?.name)

const launcherOpen = ref(false)
const briefingOpen = ref(false)
const briefing = reactive({ sessionId: null, brief: '', modality: 'chat' })
const busyId = ref(null)

const { beginning, voiceSessionId, begin, clearVoice } = useSimulationBegin()
const voiceDialogOpen = computed({
	get: () => Boolean(voiceSessionId.value),
	set: (v) => {
		if (!v) clearVoice()
	},
})

const scenariosRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.list_scenarios',
	method: 'GET',
	makeParams: () => ({ course: courseName.value }),
	auto: true,
})

const sessionsRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.list_my_sessions',
	method: 'GET',
	makeParams: () => ({ course: courseName.value }),
	auto: true,
})

const cloneRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.clone_session',
	method: 'POST',
})
const getSessionRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.get_session',
	method: 'GET',
})

const TERMINAL = ['Completed', 'Abandoned', 'Error', 'Needs Review']
function isTerminal(status) {
	return TERMINAL.includes(status)
}
function statusTheme(status) {
	return {
		Ready: 'gray',
		'In Progress': 'blue',
		Completed: 'green',
		Abandoned: 'orange',
		Error: 'red',
		'Needs Review': 'orange',
	}[status] || 'gray'
}
function formatDate(dt) {
	return dt ? new Date(dt).toLocaleString() : '—'
}

function goPlay(sessionId) {
	router.push({ name: 'SimulationPlay', params: { sessionId } })
}
function goDebrief(sessionId) {
	router.push({ name: 'SimulationDebrief', params: { sessionId } })
}

async function onRestart(sessionId) {
	busyId.value = sessionId
	try {
		const res = await cloneRes.submit({ session_id: sessionId })
		openBriefing(res.session_id, res.brief, res.modality)
	} catch (e) {
		toast.error(e.messages?.[0] || e.message || String(e))
	} finally {
		busyId.value = null
	}
}

async function onContinueReady(session) {
	busyId.value = session.name
	try {
		const res = await getSessionRes.submit({ session_id: session.name })
		openBriefing(
			session.name,
			res?.session?.student_brief || '',
			session.modality,
		)
	} catch (e) {
		toast.error(e.messages?.[0] || e.message || String(e))
	} finally {
		busyId.value = null
	}
}

function openBriefing(sessionId, brief, modality) {
	briefing.sessionId = sessionId
	briefing.brief = brief
	briefing.modality = modality
	briefingOpen.value = true
}

async function onBriefBegin(mode) {
	briefingOpen.value = false
	await begin({ sessionId: briefing.sessionId, mode })
}

function onLauncherStarted() {
	sessionsRes.reload()
}
function onVoiceEnded() {
	clearVoice()
	sessionsRes.reload()
}
</script>
```

- [ ] **Step 2: Register the student tab in `CourseDetail.vue`** — import the component and enable a student tab set.

Add the import (after the existing `CourseSimulations` import, ~line 193):
```javascript
import CourseStudentSimulations from '@/oslms/pages/Courses/CourseStudentSimulations.vue'
```

Add a student flag computed (after `isValutatore`, ~line 417):
```javascript
// An enrolled student sees a lightweight tabbed view (Overview + Simulazioni)
// when simulations are enabled globally.
const isEnrolledStudent = computed<boolean>(
	() =>
		!isAdmin.value &&
		!isValutatore.value &&
		Boolean(course.data?.membership) &&
		simulationsEnabledGlobal.value,
)
```

Widen `showTabs` (~line 419):
```javascript
const showTabs = computed<boolean>(
	() => isAdmin.value || isValutatore.value || isEnrolledStudent.value,
)
```

In the `tabs` computed, after the `if (isAdmin.value) { ... }` block and before `return t`, add the student branch:
```javascript
	if (!isAdmin.value && isEnrolledStudent.value) {
		t.push({
			id: 'simulations',
			label: __('Simulations'),
			component: markRaw(CourseStudentSimulations),
			icon: markRaw(Bot),
		})
	}
	return t
```

(The generic `<component :is="tab.component" :course="course" />` branch in the template already passes the `course` Resource to `CourseStudentSimulations`.)

- [ ] **Step 3: Verify the frontend builds**

Run: `cd frontend && yarn build`
Expected: build succeeds.

- [ ] **Step 4: Manual verification (Docker running)**

As an enrolled student on a course with a Published scenario and simulations enabled, open the course: confirm an "Simulations" tab appears with a scenario picker (Nuova simulazione) and the sessions list. Prepare a session and leave it at the briefing (close) → it appears as `Ready` with a **Continua** action. Complete a session → it shows **Rivedi** + **Riavvia**.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/oslms/pages/Courses/CourseStudentSimulations.vue \
        frontend/src/pages/Courses/CourseDetail.vue
git commit -m "feat(simulations-ui): student Simulazioni course tab with history, restart and continue"
```

---

## Task 11: Full regression pass

**Files:** none (verification only).

- [ ] **Step 1: Run the whole simulations + realtime backend suite**

Run:
```bash
bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.simulations.tests.test_prompts
bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.simulations.tests.test_orchestrator
bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.simulations.tests.test_api
bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.simulations.tests.test_instructor_api
bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.simulations.tests.test_debrief_job
bench --site lms.localhost run-tests --app os_lms --module os_lms.os_lms.ai.realtime.tests.test_realtime_api
```
Expected: all PASS. If `test_debrief_job` / `test_instructor_api` fail because they rely on `start_session`, confirm the composed `start_session` returns `{session, first_turn}` identically (it does) and fix any fixture that asserted a specific initial `status` before begin.

- [ ] **Step 2: Frontend production build**

Run: `cd frontend && yarn build`
Expected: succeeds.

- [ ] **Step 3: Commit any fixups**

```bash
git add -A
git commit -m "test(simulations): fixups from two-phase refactor regression pass"
```

---

## Self-Review Notes (coverage map)

- Spec A1 (`student_brief` field) → Task 1. A2 (session field + `Ready`) → Task 2. A3 (orchestrator split + voice reuse) → Task 3. A4 (API prepare/begin + get_session) → Task 4; realtime → Task 5. A5 (chat/voice brief layout) → Tasks 8, 9.
- Spec B1 (`list_my_sessions`, `clone_session`) → Tasks 4, 3. B2 (`CourseDetail` student tab) → Task 10. B3 (`CourseStudentSimulations`) → Task 10. B4 (shared briefing UI) → Tasks 6, 7.
- Testing section → Tasks 1, 3, 4, 5, 11.
- Deviation from spec: `start_session` (orchestrator + whitelisted API) is **kept** (composed), not removed, because internal tests, the eval runner, and `ScenarioEditor.vue` (instructor Test Run) depend on it. The student launcher migrates to `prepare_session`/`begin_session`.
- `get_debrief` widened to treat `Ready` as `not_started` (Task 4, Step 5) — prevents a prepared session from reporting a phantom pending debrief.
