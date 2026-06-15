# Extract Pure Customer Services — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estrarre la generazione della `ScenarioVariant` e la generazione della battuta del cliente AI in due servizi puri (`ScenarioVariantGenerator`, `CustomerTurnService`), iniettati sia in `SessionOrchestrator` (umano↔AI) sia in `eval/runner.py` (AI↔AI), per eliminare la duplicazione e chiudere il buco dello structured output nell'eval.

**Architecture:** Composition over inheritance. Due classi pure (no frappe, no HTTP) nel nuovo modulo `simulations/customer.py`. `ScenarioVariantGenerator` riceve un `LLMProvider` ed espone `.generate(scenario, *, seed) -> ScenarioVariant` con structured output + retry. `CustomerTurnService` riceve un `chat_fn` callable (così la produzione può iniettare `chat_with_fallback` purpose-aware mentre l'eval inietta `provider.chat` raw) ed espone `.ask(...) -> ChatResponse`. `SessionOrchestrator._generate_variant` e `_ask_customer` diventano thin wrapper che delegano — niente classi astratte, niente template method.

**Tech Stack:** Python 3.10+ dataclasses, `unittest`/`frappe.tests.UnitTestCase`, esistenti tipi `ChatMessage`/`ChatResponse`/`JsonSchema`/`LLMProvider`, prompt builder già puri in `simulations/prompts/`.

---

## File Structure

```
apps/os_lms/os_lms/os_lms/ai/simulations/
├── customer.py                          # NEW: pure services (no frappe)
├── orchestrator.py                      # MODIFY: delegate _generate_variant + _ask_customer
├── eval/
│   ├── types.py                         # MODIFY: ScenarioRef.seed_variations
│   ├── runner.py                        # MODIFY: use ScenarioVariantGenerator + CustomerTurnService
│   └── jobs.py                          # MODIFY: _scenario_ref includes seed_variations
└── tests/
    └── test_customer.py                 # NEW: unit tests for both services
```

**Comandi**: i test girano nel container `frappe` via docker compose. Prefisso da usare per ogni `bench` qui sotto:

```
docker compose --project-directory docker exec frappe \
  bench --site lms.localhost run-tests --app os_lms --module <dotted.path>
```

Per brevità lo abbrevio in `BENCH_TEST <module>` nei comandi. Il chiamante deve espanderlo.

---

### Task 1: Estendere `ScenarioRef` con `seed_variations`

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/ai/simulations/eval/types.py:50-62`
- Test: `apps/os_lms/os_lms/os_lms/ai/simulations/eval/tests/test_types.py`

- [ ] **Step 1: Aggiungere i due test in coda a `test_types.py`**

```python
def test_scenario_ref_defaults_seed_variations_to_empty_dict():
	ref = ScenarioRef(
		name="X", scenario_name="X",
		learning_objectives=[], difficulty="easy",
		customer_persona="", situation_template="",
		max_turns=10,
	)
	assert ref.seed_variations == {}


def test_scenario_ref_accepts_seed_variations():
	ref = ScenarioRef(
		name="X", scenario_name="X",
		learning_objectives=[], difficulty="easy",
		customer_persona="", situation_template="",
		max_turns=10,
		seed_variations={"mood": ["happy", "sad"]},
	)
	assert ref.seed_variations == {"mood": ["happy", "sad"]}
```

(Se `test_types.py` non contiene già l'import, aggiungere: `from os_lms.os_lms.ai.simulations.eval.types import ScenarioRef`.)

- [ ] **Step 2: Eseguire i test → falliscono**

```
BENCH_TEST os_lms.os_lms.ai.simulations.eval.tests.test_types
```

Atteso: 2 failure con `TypeError: __init__() got an unexpected keyword argument 'seed_variations'` (sul secondo test) e `AttributeError: 'ScenarioRef' object has no attribute 'seed_variations'` (sul primo).

- [ ] **Step 3: Aggiungere il campo a `ScenarioRef`**

Modificare `apps/os_lms/os_lms/os_lms/ai/simulations/eval/types.py:50-62`:

```python
@dataclass
class ScenarioRef:
	"""Subset of LMSA Simulation Scenario fields the eval pipeline needs."""

	name: str
	scenario_name: str
	learning_objectives: list[str]
	difficulty: str
	customer_persona: str
	situation_template: str
	max_turns: int
	evaluation_schema: str = ""
	seed_variations: dict[str, list[str]] = field(default_factory=dict)
```

(`field` è già importato dal modulo: vedi `from dataclasses import dataclass, field` riga 7.)

- [ ] **Step 4: Eseguire i test → passano**

```
BENCH_TEST os_lms.os_lms.ai.simulations.eval.tests.test_types
```

Atteso: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/simulations/eval/types.py \
        apps/os_lms/os_lms/os_lms/ai/simulations/eval/tests/test_types.py
git commit -m "feat(eval): add ScenarioRef.seed_variations field"
```

---

### Task 2: Creare `customer.py` — `ScenarioVariantGenerator`

**Files:**
- Create: `apps/os_lms/os_lms/os_lms/ai/simulations/customer.py`
- Create: `apps/os_lms/os_lms/os_lms/ai/simulations/tests/test_customer.py`

- [ ] **Step 1: Scrivere i test in `test_customer.py`**

Creare `apps/os_lms/os_lms/os_lms/ai/simulations/tests/test_customer.py`:

```python
"""Unit tests for the pure customer services (ScenarioVariantGenerator,
CustomerTurnService). Pure tests — no frappe, no DB."""
from __future__ import annotations

import json

from frappe.tests import UnitTestCase

from os_lms.os_lms.ai.utils.llm.provider import ChatMessage, ChatResponse, Usage
from os_lms.os_lms.ai.simulations.customer import (
	ScenarioVariantGenerator,
	CustomerTurnService,
)
from os_lms.os_lms.ai.simulations.eval.types import ScenarioRef


class _RecordingProvider:
	"""LLMProvider stub recording every chat() call and returning queued texts."""

	name = "recording"

	def __init__(self, responses: list[str]):
		self.responses = list(responses)
		self.calls: list[dict] = []

	def chat(self, messages, *, system=None, model=None, **kwargs):
		self.calls.append({
			"messages": list(messages),
			"system": system,
			"model": model,
			"kwargs": dict(kwargs),
		})
		return ChatResponse(
			text=self.responses.pop(0),
			finish_reason="stop", usage=Usage(),
			model=model or "rec-1", provider="recording",
		)


def _valid_variant_json() -> str:
	return json.dumps({
		"situation": "Cliente del settore manifatturiero.",
		"persona": {
			"name": "Mario", "role": "CTO", "company": "AcmeCo",
			"mood": "scettico", "key_objection": "prezzo",
			"hidden_motivation": "vuole sconto",
		},
	})


def _scenario_ref() -> ScenarioRef:
	return ScenarioRef(
		name="SC-1", scenario_name="X",
		learning_objectives=["o1", "o2"],
		difficulty="medium",
		customer_persona="base persona",
		situation_template="template",
		max_turns=4,
		seed_variations={"mood": ["calm", "tense"]},
	)


class TestScenarioVariantGenerator(UnitTestCase):
	def test_generate_returns_parsed_variant_on_valid_first_response(self):
		provider = _RecordingProvider(responses=[_valid_variant_json()])
		gen = ScenarioVariantGenerator(provider=provider, model="m1")
		variant = gen.generate(_scenario_ref(), seed="seed-1")
		self.assertEqual(variant.persona.name, "Mario")
		self.assertEqual(len(provider.calls), 1)

	def test_generate_passes_structured_output_response_format(self):
		provider = _RecordingProvider(responses=[_valid_variant_json()])
		gen = ScenarioVariantGenerator(provider=provider, model=None)
		gen.generate(_scenario_ref(), seed="seed-2")
		kw = provider.calls[0]["kwargs"]
		self.assertIn("response_format", kw)
		self.assertEqual(kw["response_format"].name, "scenario_variant")

	def test_generate_retries_once_on_invalid_first_response(self):
		provider = _RecordingProvider(responses=[
			"not json at all",
			_valid_variant_json(),
		])
		gen = ScenarioVariantGenerator(provider=provider, model=None)
		variant = gen.generate(_scenario_ref(), seed="seed-3")
		self.assertEqual(variant.persona.name, "Mario")
		self.assertEqual(len(provider.calls), 2)
		# Retry must use temperature=0
		self.assertEqual(provider.calls[1]["kwargs"].get("temperature"), 0)

	def test_generate_propagates_value_error_if_retry_also_fails(self):
		provider = _RecordingProvider(responses=["nope", "still not json"])
		gen = ScenarioVariantGenerator(provider=provider, model=None)
		with self.assertRaises(ValueError):
			gen.generate(_scenario_ref(), seed="seed-4")
```

(Se la directory `tests/` non ha già `__init__.py`, già esiste — vedi `simulations/tests/__init__.py` confermato.)

- [ ] **Step 2: Eseguire i test → falliscono (modulo `customer` non esiste)**

```
BENCH_TEST os_lms.os_lms.ai.simulations.tests.test_customer
```

Atteso: `ImportError: cannot import name 'ScenarioVariantGenerator' from 'os_lms.os_lms.ai.simulations.customer'` (o modulo not found).

- [ ] **Step 3: Creare `customer.py` con la classe**

Creare `apps/os_lms/os_lms/os_lms/ai/simulations/customer.py`:

```python
"""Pure customer-side services for simulation flows.

Both `SessionOrchestrator` (human↔AI) and `eval/runner.py` (AI↔AI) depend on
the same scenario-variant generation and customer-turn generation logic. To
avoid drift, that logic lives here as injectable services with NO frappe /
HTTP imports.

Composition over inheritance: each service is built per-call by the caller,
who supplies the provider (and, for customer turns, a `chat_fn` callable so
production can plug in `chat_with_fallback` while eval plugs in a raw
provider).
"""
from __future__ import annotations

from collections.abc import Callable

from os_lms.os_lms.ai.utils.llm.provider import (
	ChatMessage, ChatResponse, JsonSchema, LLMProvider,
)
from os_lms.os_lms.ai.simulations.eval.types import ScenarioRef
from os_lms.os_lms.ai.simulations.prompts import (
	PersonaVariant,
	SCENARIO_SCHEMA,
	ScenarioVariant,
	build_role_play_system_prompt,
	build_scenario_generator_messages,
	parse_scenario_generator_output,
)


class ScenarioVariantGenerator:
	"""Generate a concrete ScenarioVariant from a scenario template.

	Owns the structured-output JsonSchema + one-shot retry-with-correction
	used in production. Both SessionOrchestrator and the eval runner go
	through this class so changes apply uniformly.
	"""

	def __init__(self, provider: LLMProvider, model: str | None = None):
		self._provider = provider
		self._model = model

	def generate(self, scenario: ScenarioRef, *, seed: str) -> ScenarioVariant:
		system, messages = build_scenario_generator_messages(
			scenario_name=scenario.scenario_name,
			difficulty=scenario.difficulty,
			customer_persona=scenario.customer_persona,
			situation_template=scenario.situation_template,
			learning_objectives=scenario.learning_objectives,
			seed_variations=scenario.seed_variations,
			seed=seed,
		)
		response_format = JsonSchema(
			name="scenario_variant", schema=SCENARIO_SCHEMA,
		)
		chat_messages = [
			ChatMessage(role=m["role"], content=m["content"]) for m in messages
		]
		response = self._provider.chat(
			messages=chat_messages,
			system=system,
			model=self._model,
			temperature=0.7,
			max_tokens=600,
			response_format=response_format,
		)
		try:
			return parse_scenario_generator_output(response.text)
		except ValueError:
			retry = self._provider.chat(
				messages=chat_messages + [
					ChatMessage(role="assistant", content=response.text),
					ChatMessage(
						role="user",
						content=(
							"L'output non era JSON valido. Riprova rispondendo "
							"ESCLUSIVAMENTE con un oggetto JSON valido conforme "
							"allo schema, senza testo aggiuntivo."
						),
					),
				],
				system=system,
				model=self._model,
				temperature=0,
				max_tokens=600,
				response_format=response_format,
			)
			return parse_scenario_generator_output(retry.text)


# Placeholder for CustomerTurnService — added in Task 3.
ChatFn = Callable[..., ChatResponse]
```

- [ ] **Step 4: Eseguire i test → 4 PASS**

```
BENCH_TEST os_lms.os_lms.ai.simulations.tests.test_customer
```

Atteso: 4 PASS, 0 FAIL.

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/simulations/customer.py \
        apps/os_lms/os_lms/os_lms/ai/simulations/tests/test_customer.py
git commit -m "feat(simulations): extract ScenarioVariantGenerator"
```

---

### Task 3: Aggiungere `CustomerTurnService` a `customer.py`

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/ai/simulations/customer.py`
- Modify: `apps/os_lms/os_lms/os_lms/ai/simulations/tests/test_customer.py`

- [ ] **Step 1: Aggiungere il test `CustomerTurnService` in coda a `test_customer.py`**

Append a `test_customer.py`:

```python
from os_lms.os_lms.ai.simulations.prompts import PersonaVariant


def _persona() -> PersonaVariant:
	return PersonaVariant(
		name="Anna", role="CFO", company="Foo Srl",
		mood="diffidente", key_objection="costo",
		hidden_motivation="convincere il CEO",
	)


class TestCustomerTurnService(UnitTestCase):
	def test_ask_invokes_chat_fn_with_role_play_system_prompt(self):
		captured: dict = {}

		def chat_fn(*, messages, system, **kwargs):
			captured["messages"] = list(messages)
			captured["system"] = system
			captured["kwargs"] = dict(kwargs)
			return ChatResponse(
				text="Risposta del cliente",
				finish_reason="stop", usage=Usage(),
				model="t-1", provider="test",
			)

		service = CustomerTurnService(chat_fn=chat_fn)
		response = service.ask(
			persona=_persona(),
			situation="Trattativa in corso.",
			difficulty="hard",
			history=[ChatMessage(role="user", content="Buongiorno")],
		)
		self.assertEqual(response.text, "Risposta del cliente")
		self.assertIn("Anna", captured["system"])
		self.assertEqual(len(captured["messages"]), 1)
		self.assertEqual(captured["kwargs"].get("temperature"), 0.7)
		self.assertEqual(captured["kwargs"].get("max_tokens"), 400)
```

- [ ] **Step 2: Eseguire i test → fail (CustomerTurnService non esiste)**

```
BENCH_TEST os_lms.os_lms.ai.simulations.tests.test_customer
```

Atteso: `ImportError: cannot import name 'CustomerTurnService'`.

- [ ] **Step 3: Aggiungere la classe a `customer.py`**

Sostituire la riga `# Placeholder for CustomerTurnService — added in Task 3.` e il successivo `ChatFn = ...` con:

```python
ChatFn = Callable[..., ChatResponse]


class CustomerTurnService:
	"""Ask the AI customer for its next turn given the conversation history.

	The caller injects `chat_fn` so the same service works in production
	(where `chat_fn = chat_with_fallback("chat", ..., override=...)`) and in
	eval (where `chat_fn = lambda **kw: provider.chat(**kw)`). The service
	itself stays unaware of fallback and purpose routing.
	"""

	def __init__(self, chat_fn: ChatFn):
		self._chat = chat_fn

	def ask(
		self,
		*,
		persona: PersonaVariant,
		situation: str,
		difficulty: str,
		history: list[ChatMessage],
	) -> ChatResponse:
		system = build_role_play_system_prompt(
			persona=persona,
			generated_situation=situation,
			difficulty=difficulty,
		)
		return self._chat(
			messages=history,
			system=system,
			temperature=0.7,
			max_tokens=400,
		)
```

- [ ] **Step 4: Eseguire i test → 5 PASS**

```
BENCH_TEST os_lms.os_lms.ai.simulations.tests.test_customer
```

Atteso: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/simulations/customer.py \
        apps/os_lms/os_lms/os_lms/ai/simulations/tests/test_customer.py
git commit -m "feat(simulations): extract CustomerTurnService"
```

---

### Task 4: Refactor `SessionOrchestrator` per delegare

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/ai/simulations/orchestrator.py:284-345` (`_generate_variant`)
- Modify: `apps/os_lms/os_lms/os_lms/ai/simulations/orchestrator.py:347-363` (`_ask_customer`)

Manteniamo i metodi privati come thin wrapper: i test esistenti che fanno `patch.object(SessionOrchestrator, "_generate_variant", ...)` continuano a funzionare senza modifiche.

- [ ] **Step 1: Verificare la baseline dei test orchestrator (deve PASSARE prima della refactor)**

```
BENCH_TEST os_lms.os_lms.ai.simulations.tests.test_orchestrator
```

Atteso: tutti PASS (baseline pre-refactor).

- [ ] **Step 2: Modificare `_generate_variant` per delegare**

Aprire `apps/os_lms/os_lms/os_lms/ai/simulations/orchestrator.py` e sostituire l'intero metodo `_generate_variant` (righe 284-345) con:

```python
	def _generate_variant(self, scenario, seed: str, provider: LLMProvider) -> ScenarioVariant:
		from os_lms.os_lms.ai.simulations.customer import ScenarioVariantGenerator

		scenario_ref = self._scenario_ref_from_doc(scenario)
		generator = ScenarioVariantGenerator(
			provider=provider,
			model=_model_from_provider(provider) or None,
		)
		return generator.generate(scenario_ref, seed=seed)

	def _scenario_ref_from_doc(self, scenario) -> "ScenarioRef":
		from os_lms.os_lms.ai.simulations.eval.types import ScenarioRef

		objectives = [
			(row.objective_text or "").strip()
			for row in (scenario.learning_objectives or [])
		]
		objectives = [o for o in objectives if o]
		variations = {
			(row.variable_name or "").strip(): [
				v.strip() for v in (row.possible_values or "").splitlines() if v.strip()
			]
			for row in (scenario.seed_variations or [])
			if (row.variable_name or "").strip()
		}
		return ScenarioRef(
			name=scenario.name,
			scenario_name=scenario.scenario_name,
			learning_objectives=objectives,
			difficulty=scenario.difficulty,
			customer_persona=scenario.customer_persona or "",
			situation_template=scenario.situation_template or "",
			max_turns=scenario.max_turns or 20,
			evaluation_schema=scenario.evaluation_schema or "",
			seed_variations=variations,
		)
```

NOTA: stiamo togliendo da `_generate_variant` l'uso diretto di `SCENARIO_SCHEMA`, `JsonSchema`, `build_scenario_generator_messages`, `parse_scenario_generator_output`. Controllare gli import in cima al file e rimuovere quelli ora non più referenziati nell'orchestrator (potrebbero ancora servire per altre cose — lasciarli se in dubbio, ruff li segnalerà).

- [ ] **Step 3: Modificare `_ask_customer` per delegare**

Sostituire l'intero metodo `_ask_customer` (righe 347-363) con:

```python
	def _ask_customer(self, session, persona: PersonaVariant) -> ChatResponse:
		"""Send the full history + role-play system prompt to the LLM."""
		from os_lms.os_lms.ai.simulations.customer import CustomerTurnService

		history = _load_chat_history(session.name)
		override = _scenario_provider_override(session.scenario)

		def _chat_fn(*, messages, system, **kwargs):
			return chat_with_fallback(
				"chat", messages, override=override,
				system=system, **kwargs,
			)

		service = CustomerTurnService(chat_fn=_chat_fn)
		return service.ask(
			persona=persona,
			situation=session.generated_situation,
			difficulty=_scenario_difficulty(session.scenario),
			history=history,
		)
```

- [ ] **Step 4: Rieseguire i test orchestrator → tutti PASS**

```
BENCH_TEST os_lms.os_lms.ai.simulations.tests.test_orchestrator
```

Atteso: identico a Step 1. Se qualche test fallisce, NON andare avanti — rivedere la delegation (probabile causa: import mancante, signature scorretta, o `_scenario_ref_from_doc` non compatibile con quello che `_stub_generate_variant` aspetta).

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/simulations/orchestrator.py
git commit -m "refactor(simulations): orchestrator delegates to customer services"
```

---

### Task 5: Refactor `eval/runner.py` per usare i servizi

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/ai/simulations/eval/runner.py`

- [ ] **Step 1: Verificare baseline test runner**

```
BENCH_TEST os_lms.os_lms.ai.simulations.eval.tests.test_runner
```

Atteso: PASS.

- [ ] **Step 2: Riscrivere `runner.py`**

Sostituire l'INTERO contenuto di `apps/os_lms/os_lms/os_lms/ai/simulations/eval/runner.py` con:

```python
"""Synthetic session generators for authoring mode.

Two strategies:
- run_golden_replay: deterministic, no LLM calls
- run_synthetic_llm_student: mirrors the orchestrator's runtime flow by
  delegating scenario-variant generation and customer-turn generation to
  the same pure services (`ScenarioVariantGenerator`, `CustomerTurnService`)
  the orchestrator uses. The eval-specific bit is the LLM-student that
  generates the user-side turns.

Sharing the services kills drift: a change to structured output, retry
policy, or the role-play prompt automatically applies to both prod and eval.
"""
from __future__ import annotations

import time

from os_lms.os_lms.ai.utils.llm.provider import ChatMessage, ChatResponse, LLMProvider
from os_lms.os_lms.ai.simulations.customer import (
	CustomerTurnService,
	ScenarioVariantGenerator,
)
from os_lms.os_lms.ai.simulations.eval.student.golden import replay_golden
from os_lms.os_lms.ai.simulations.eval.student.llm_student import (
	build_student_messages,
)
from os_lms.os_lms.ai.simulations.eval.types import ScenarioRef


def run_golden_replay(*, turns_json: str, provider: LLMProvider) -> list[dict]:
	# Provider accepted for signature symmetry; deterministic — never called.
	return replay_golden(turns_json)


def run_synthetic_llm_student(
	*,
	scenario: ScenarioRef,
	profile_name: str,
	provider: LLMProvider,
	model: str | None = None,
) -> list[dict]:
	"""Generate a full synthetic session: 1 variant call + alternating
	student/cliente turns up to scenario.max_turns."""
	variant_gen = ScenarioVariantGenerator(provider=provider, model=model)
	variant = variant_gen.generate(
		scenario, seed=f"eval-{int(time.time() * 1000)}",
	)

	def _chat_fn(*, messages, system, **kwargs):
		return provider.chat(messages=messages, system=system, model=model, **kwargs)

	customer = CustomerTurnService(chat_fn=_chat_fn)

	transcript: list[dict] = []
	for turn_index in range(scenario.max_turns):
		if turn_index % 2 == 0:
			# Student turn — eval-specific (the orchestrator's caller is a human)
			system, messages = build_student_messages(
				scenario=scenario,
				history=transcript,
				profile_name=profile_name,
			)
			response = provider.chat(
				[ChatMessage(role=m["role"], content=m["content"]) for m in messages],
				system=system,
				model=model,
				temperature=0.8,
				max_tokens=400,
			)
			transcript.append({
				"turn_index": turn_index,
				"role": "user",
				"text": response.text.strip(),
			})
		else:
			# Customer turn — same code path as production
			history_msgs = [
				ChatMessage(role=t["role"], content=t.get("text", ""))
				for t in transcript
				if t["role"] in ("user", "assistant")
			]
			response = customer.ask(
				persona=variant.persona,
				situation=variant.situation,
				difficulty=scenario.difficulty,
				history=history_msgs,
			)
			transcript.append({
				"turn_index": turn_index,
				"role": "assistant",
				"text": response.text.strip(),
			})
	return transcript
```

- [ ] **Step 3: Rieseguire test runner**

```
BENCH_TEST os_lms.os_lms.ai.simulations.eval.tests.test_runner
```

Atteso: tutti PASS. Se fallisce `test_alternates_student_and_cliente_until_max_turns`, controllare che il FakeProvider del test accetti `response_format` via `**kwargs` (lo fa già: `runner.py` test FakeProvider `def chat(self, messages, *, system=None, model=None, **kwargs)`).

- [ ] **Step 4: Eseguire anche il test e2e di authoring**

```
BENCH_TEST os_lms.os_lms.ai.simulations.eval.tests.integration.test_run_authoring_quick
```

Atteso: PASS. Il FakeProvider di `test_run_authoring_quick.py:19` accetta `**kwargs` — ok.

- [ ] **Step 5: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/simulations/eval/runner.py
git commit -m "refactor(eval): runner uses shared customer services"
```

---

### Task 6: `_scenario_ref` popola `seed_variations`

**Files:**
- Modify: `apps/os_lms/os_lms/os_lms/ai/simulations/eval/jobs.py:43-59`

Così l'eval beneficia delle stesse variabili di randomizzazione configurate sullo scenario reale.

- [ ] **Step 1: Aggiornare `_scenario_ref` in `jobs.py`**

Sostituire `_scenario_ref` (righe 43-59) con:

```python
def _scenario_ref(scenario_name: str) -> ScenarioRef:
	doc = frappe.get_doc("LMSA Simulation Scenario", scenario_name)
	objectives = [
		row.objective_text
		for row in (doc.learning_objectives or [])
		if (row.objective_text or "").strip()
	]
	variations = {
		(row.variable_name or "").strip(): [
			v.strip() for v in (row.possible_values or "").splitlines() if v.strip()
		]
		for row in (doc.seed_variations or [])
		if (row.variable_name or "").strip()
	}
	return ScenarioRef(
		name=doc.name,
		scenario_name=doc.scenario_name,
		learning_objectives=objectives,
		difficulty=doc.difficulty,
		customer_persona=doc.customer_persona or "",
		situation_template=doc.situation_template or "",
		max_turns=doc.max_turns or 20,
		evaluation_schema=doc.evaluation_schema or "",
		seed_variations=variations,
	)
```

- [ ] **Step 2: Rieseguire i test jobs**

```
BENCH_TEST os_lms.os_lms.ai.simulations.eval.tests.test_jobs
```

Atteso: PASS (i test esistenti non controllano seed_variations, quindi devono restare verdi).

- [ ] **Step 3: Commit**

```bash
git add apps/os_lms/os_lms/os_lms/ai/simulations/eval/jobs.py
git commit -m "feat(eval): include seed_variations when building ScenarioRef"
```

---

### Task 7: Full regression suite

**Files:** nessuna modifica — solo verifica.

- [ ] **Step 1: Eseguire l'intera suite simulations + eval**

```
docker compose --project-directory docker exec frappe \
  bench --site lms.localhost run-tests --app os_lms \
  --module os_lms.os_lms.ai.simulations
```

(Se il bench non supporta `--module` su un package, eseguire i singoli moduli che hanno cambiato superficie: `test_customer`, `test_orchestrator`, `test_runner`, `test_types`, `test_jobs`, `integration.test_run_authoring_quick`, `tests.test_api`.)

Atteso: tutto verde.

- [ ] **Step 2: Ripristinare l'`enqueue` se è stato modificato per debug**

NOTA per chi esegue: il file `apps/os_lms/os_lms/os_lms/ai/simulations/eval/api.py:61-67` potrebbe essere stato modificato in una sessione precedente per chiamare `run_authoring_evaluation` sincrono (per attacco debugpy). Verificare con `git diff` e ripristinare la versione `frappe.enqueue(...)` originale se necessario. NON includere quella modifica in alcun commit di questa branch.

```bash
git diff apps/os_lms/os_lms/os_lms/ai/simulations/eval/api.py
```

Se il diff mostra la chiamata sincrona di debug, ripristinare e committare separatamente o stash-are.

- [ ] **Step 3: Nessun commit (verifica)**

---

## Self-Review

**1. Spec coverage:**
- Estrazione ScenarioVariantGenerator → Task 2 ✓
- Estrazione CustomerTurnService → Task 3 ✓
- Iniezione in SessionOrchestrator → Task 4 ✓
- Iniezione in runner → Task 5 ✓
- Closure del buco "structured output mancante nell'eval" → Task 5 ✓ (runner ora usa ScenarioVariantGenerator che applica `response_format`)
- Closure del buco "retry mancante nell'eval" → Task 5 ✓
- Niente classe astratta / template method → Task 4 (delegation thin wrapper) ✓
- Test esistenti restano verdi → Step 4 di Task 4, Step 3-4 di Task 5, Task 7 ✓

**2. Placeholder scan:**
- Tutti i blocchi codice sono completi (no TODO, no "implement later").
- Comandi `BENCH_TEST` definiti in cima come prefisso da espandere.
- Atteso output specificato per ogni test step.

**3. Type consistency:**
- `ScenarioVariantGenerator.__init__(provider, model=None)` — usato uguale in Task 2/3/4/5.
- `ScenarioVariantGenerator.generate(scenario, *, seed)` — keyword-only `seed`, usato uguale in Task 2/4/5.
- `CustomerTurnService.__init__(chat_fn)` — usato uguale in Task 3/4/5.
- `CustomerTurnService.ask(*, persona, situation, difficulty, history)` — tutto keyword, usato uguale in Task 3/4/5.
- `ScenarioRef.seed_variations: dict[str, list[str]]` — Task 1 definisce, Task 2/4/6 consumano.
- `ChatFn = Callable[..., ChatResponse]` — Task 2 placeholder, Task 3 definisce.

Coperto.
