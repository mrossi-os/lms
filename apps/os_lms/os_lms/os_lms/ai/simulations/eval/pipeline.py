"""Source-agnostic evaluation pipeline.

Given a transcript + a ScenarioRef + an LLMProvider, run all four judges
and return their DimensionScore objects. The provider follows the project's
real abstraction (utils.llm.provider.LLMProvider) — tests can substitute a
fake that matches the same shape; production code passes the result of
`resolve_provider("debrief")`.

The pipeline never raises on a judge failure: it returns a DimensionScore
with score=None and a warning so the caller can decide whether to surface
the trace as 'failed' or just exclude that dimension from aggregates.
"""
from __future__ import annotations

from os_lms.os_lms.ai.utils.llm.provider import ChatMessage, LLMProvider
from os_lms.os_lms.ai.simulations.eval.judges import (
	persona as persona_judge,
	coverage as coverage_judge,
	debrief as debrief_judge,
	difficulty as difficulty_judge,
)
from os_lms.os_lms.ai.simulations.eval.types import (
	DimensionScore,
	DIMENSION_PERSONA,
	DIMENSION_COVERAGE,
	DIMENSION_DEBRIEF,
	DIMENSION_DIFFICULTY,
	ScenarioRef,
)


def _to_chat_messages(messages: list[dict]) -> list[ChatMessage]:
	return [ChatMessage(role=m["role"], content=m["content"]) for m in messages]


def _run_judge(
	*,
	judge_module,
	dimension: str,
	provider: LLMProvider,
	build_kwargs: dict,
	model: str | None = None,
) -> DimensionScore:
	try:
		system, messages = judge_module.build_messages(**build_kwargs)
		response = provider.chat(
			_to_chat_messages(messages),
			system=system,
			model=model,
			temperature=0.0,  # judges want determinism
			max_tokens=1024,
		)
		return judge_module.parse_output(response.text)
	except ValueError as e:
		return DimensionScore(
			dimension=dimension,
			score=None,
			summary=str(e),
			warnings=["judge_parse_error"],
		)
	except Exception as e:  # noqa: BLE001 - provider error, network, etc.
		return DimensionScore(
			dimension=dimension,
			score=None,
			summary=str(e),
			warnings=["judge_provider_error"],
		)


def evaluate_transcript(
	*,
	transcript: list[dict],
	scenario: ScenarioRef,
	trace_kind: str,
	provider: LLMProvider,
	debrief_payload: dict | None = None,
	model: str | None = None,
) -> list[DimensionScore]:
	"""Run the 4 judges. Returns scores in fixed order:
	persona, coverage, debrief, difficulty.
	"""

	persona_score = _run_judge(
		judge_module=persona_judge,
		dimension=DIMENSION_PERSONA,
		provider=provider,
		build_kwargs={
			"transcript": transcript,
			"scenario": scenario,
			"trace_kind": trace_kind,
		},
		model=model,
	)

	coverage_score = _run_judge(
		judge_module=coverage_judge,
		dimension=DIMENSION_COVERAGE,
		provider=provider,
		build_kwargs={
			"transcript": transcript,
			"scenario": scenario,
			"trace_kind": trace_kind,
		},
		model=model,
	)

	if debrief_payload is None:
		debrief_score = debrief_judge.skipped_score(reason="debrief_missing")
	else:
		debrief_score = _run_judge(
			judge_module=debrief_judge,
			dimension=DIMENSION_DEBRIEF,
			provider=provider,
			build_kwargs={
				"transcript": transcript,
				"scenario": scenario,
				"trace_kind": trace_kind,
				"debrief_payload": debrief_payload,
			},
			model=model,
		)

	runtime_overall = None
	if isinstance(debrief_payload, dict):
		runtime_overall = debrief_payload.get("overall_score")
	difficulty_score = _run_judge(
		judge_module=difficulty_judge,
		dimension=DIMENSION_DIFFICULTY,
		provider=provider,
		build_kwargs={
			"transcript": transcript,
			"scenario": scenario,
			"trace_kind": trace_kind,
			"runtime_overall_score": runtime_overall,
		},
		model=model,
	)

	return [persona_score, coverage_score, debrief_score, difficulty_score]
