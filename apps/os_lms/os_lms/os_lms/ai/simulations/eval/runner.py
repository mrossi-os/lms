"""Synthetic session generators for authoring mode.

Two strategies:
- run_golden_replay: deterministic, no LLM calls
- run_synthetic_llm_student: mirrors the orchestrator's runtime flow ---
  first generate a scenario variant via scenario_generator (PersonaVariant +
  situation), then alternate LLM-student + LLM-cliente turns using the same
  role_play system prompt the real student sees.

Mirroring the runtime chain matters: if we bypassed scenario_generator the
eval would not catch drift in that prompt. Cost is +1 LLM call per trace.
"""
from __future__ import annotations

import time

from os_lms.os_lms.ai.utils.llm.provider import ChatMessage, LLMProvider
from os_lms.os_lms.ai.simulations.prompts.role_play import (
	build_role_play_system_prompt,
)
from os_lms.os_lms.ai.simulations.prompts.scenario_generator import (
	build_scenario_generator_messages,
	parse_scenario_generator_output,
)
from os_lms.os_lms.ai.simulations.eval.student.golden import replay_golden
from os_lms.os_lms.ai.simulations.eval.student.llm_student import (
	build_student_messages,
)
from os_lms.os_lms.ai.simulations.eval.types import ScenarioRef


def run_golden_replay(*, turns_json: str, provider: LLMProvider) -> list[dict]:
	# Provider accepted for signature symmetry; deterministic — never called.
	return replay_golden(turns_json)


def _generate_variant(
	scenario: ScenarioRef,
	provider: LLMProvider,
	model: str | None,
):
	"""Run scenario_generator once at the start of a synthetic trace.

	Returns the parsed ScenarioVariant (with .situation and .persona).
	Raises ValueError on parse failure — the caller surfaces this as a
	trace failure.
	"""
	seed = f"eval-{int(time.time() * 1000)}"
	system, messages = build_scenario_generator_messages(
		scenario_name=scenario.scenario_name,
		difficulty=scenario.difficulty,
		customer_persona=scenario.customer_persona,
		situation_template=scenario.situation_template,
		learning_objectives=scenario.learning_objectives,
		seed_variations={},
		seed=seed,
	)
	response = provider.chat(
		[ChatMessage(role=m["role"], content=m["content"]) for m in messages],
		system=system,
		model=model,
		temperature=0.7,
		max_tokens=1024,
	)
	return parse_scenario_generator_output(response.text)


def run_synthetic_llm_student(
	*,
	scenario: ScenarioRef,
	profile_name: str,
	provider: LLMProvider,
	model: str | None = None,
) -> list[dict]:
	"""Generate a full synthetic session: 1 variant call + alternating
	student/cliente turns up to scenario.max_turns."""
	variant = _generate_variant(scenario, provider, model)

	transcript: list[dict] = []
	for turn_index in range(scenario.max_turns):
		if turn_index % 2 == 0:
			# Student turn
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
			# Cliente turn — same chain the real student sees
			system_prompt = build_role_play_system_prompt(
				persona=variant.persona,
				generated_situation=variant.situation,
				difficulty=scenario.difficulty,
			)
			history_msgs = [
				ChatMessage(role=t["role"], content=t.get("text", ""))
				for t in transcript
				if t["role"] in ("user", "assistant")
			]
			response = provider.chat(
				history_msgs,
				system=system_prompt,
				model=model,
				temperature=0.7,
				max_tokens=400,
			)
			transcript.append({
				"turn_index": turn_index,
				"role": "assistant",
				"text": response.text.strip(),
			})
	return transcript
