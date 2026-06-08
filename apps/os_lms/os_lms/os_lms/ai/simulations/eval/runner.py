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

from os_lms.os_lms.ai.utils.llm.provider import ChatMessage, LLMProvider
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
