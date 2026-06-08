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


class CustomerTurnService:
	"""Placeholder — full implementation added in Task 3."""
	pass


# Type alias for a chat callable — used by CustomerTurnService in Task 3.
ChatFn = Callable[..., ChatResponse]
