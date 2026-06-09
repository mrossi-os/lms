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

import frappe

from os_lms.os_lms.ai.simulations.eval.judges import (
	coverage as coverage_judge,
)
from os_lms.os_lms.ai.simulations.eval.judges import (
	debrief as debrief_judge,
)
from os_lms.os_lms.ai.simulations.eval.judges import (
	difficulty as difficulty_judge,
)
from os_lms.os_lms.ai.simulations.eval.judges import (
	persona as persona_judge,
)
from os_lms.os_lms.ai.simulations.eval.types import (
	DIMENSION_COVERAGE,
	DIMENSION_DEBRIEF,
	DIMENSION_DIFFICULTY,
	DIMENSION_PERSONA,
	DimensionScore,
	ScenarioRef,
)
from os_lms.os_lms.ai.simulations.prompts.judge_loader import load_judge_prompt
from os_lms.os_lms.ai.utils.llm.provider import ChatMessage, JsonSchema, LLMProvider


def _run_judge(
	*,
	judge_module,
	dimension: str,
	provider: LLMProvider,
	build_kwargs: dict,
	model: str | None = None,
) -> DimensionScore:
	config = load_judge_prompt(f"judge_{dimension}")
	response = None
	try:
		user_text = judge_module.build_user_message(**build_kwargs)
		response = provider.chat(
			[ChatMessage(role="user", content=user_text)],
			system=config["system_prompt"],
			model=model,
			temperature=config["temperature"],
			max_tokens=config["max_tokens"],
			response_format=JsonSchema(
				name=f"{dimension}_judgement",
				schema=config["output_schema"],
			),
		)
		return judge_module.parse_output(response.text)
	except ValueError as e:
		_log_judge_failure(dimension, "parse_error", str(e), response, model, config)
		return DimensionScore(
			dimension=dimension,
			score=None,
			summary=str(e),
			warnings=["judge_parse_error"],
		)
	except Exception as e:  # noqa: BLE001 - provider error, network, etc.
		_log_judge_failure(dimension, "provider_error", str(e), response, model, config)
		return DimensionScore(
			dimension=dimension,
			score=None,
			summary=str(e),
			warnings=["judge_provider_error"],
		)


def _log_judge_failure(
	dimension: str,
	kind: str,
	error: str,
	response,
	model: str | None,
	config: dict,
) -> None:
	"""Record a judge failure in the Frappe Error Log so it surfaces in the Desk.

	Captures the provider's actual response text + finish reason + usage so the
	"Expecting value: line 1 column 1 (char 0)" symptom (which means
	response.text == "") can be distinguished from real malformed JSON.
	Best-effort: never raises (the caller already has a fallback DimensionScore).
	"""
	try:
		if response is not None:
			text = response.text or ""
			details = (
				f"dimension={dimension} kind={kind}\n"
				f"error={error}\n"
				f"model={model or '(default)'}\n"
				f"request: temperature={config['temperature']} max_tokens={config['max_tokens']} "
				f"version={config.get('version')}\n"
				f"response: provider={response.provider} model={response.model} "
				f"finish_reason={response.finish_reason} "
				f"prompt_tokens={response.usage.prompt_tokens} "
				f"completion_tokens={response.usage.completion_tokens}\n"
				f"response.text (len={len(text)}, first 1000 chars):\n{text[:1000]}"
			)
		else:
			details = (
				f"dimension={dimension} kind={kind}\n"
				f"error={error}\n"
				f"model={model or '(default)'} (no response reached the parser)"
			)
		frappe.log_error(message=details, title=f"LMSA judge {dimension} {kind}")
	except Exception:
		pass


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
