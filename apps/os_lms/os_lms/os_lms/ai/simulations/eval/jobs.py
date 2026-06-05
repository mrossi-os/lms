"""Background job entry points for evaluation runs.

Called by frappe.enqueue from api.py. All jobs follow the same shape:
    1. Load the LMSA Quality Evaluation parent
    2. Mark status=running
    3. Drive the pipeline against each trace
    4. Persist results, compute aggregates
    5. Mark status=complete (or failed)
    6. publish_realtime
"""
from __future__ import annotations

import json
from statistics import mean

import frappe

from os_lms.os_lms.ai.simulations.eval.pipeline import evaluate_transcript
from os_lms.os_lms.ai.simulations.eval.types import (
	DimensionScore,
	DIMENSION_PERSONA, DIMENSION_COVERAGE,
	DIMENSION_DEBRIEF, DIMENSION_DIFFICULTY,
	ScenarioRef,
)


REALTIME_EVENT = "simulation:eval_complete"


def _get_provider():
	"""Resolve the configured 'debrief' provider — judges are non-realtime
	so we use the same purpose-based factory the runtime uses. Tests patch
	this function to inject a FakeProvider."""
	from os_lms.os_lms.ai.utils.llm import resolve_provider
	return resolve_provider("debrief")


def _get_eval_model() -> str | None:
	settings = frappe.get_single("LMSA Settings")
	return settings.get("simulation_debrief_model") or None


def _scenario_ref(scenario_name: str) -> ScenarioRef:
	doc = frappe.get_doc("LMSA Simulation Scenario", scenario_name)
	objectives = [
		row.objective_text
		for row in (doc.learning_objectives or [])
		if (row.objective_text or "").strip()
	]
	return ScenarioRef(
		name=doc.name,
		scenario_name=doc.scenario_name,
		learning_objectives=objectives,
		difficulty=doc.difficulty,
		customer_persona=doc.customer_persona or "",
		situation_template=doc.situation_template or "",
		max_turns=doc.max_turns or 20,
		evaluation_schema=doc.evaluation_schema or "",
	)


def _load_session_transcript(session_name: str) -> list[dict]:
	turns = frappe.get_all(
		"LMSA Simulation Turn",
		filters={"session": session_name},
		fields=["turn_index", "role", "text_content"],
		order_by="turn_index asc",
	)
	return [
		{"turn_index": t.turn_index, "role": t.role, "text": t.text_content or ""}
		for t in turns
	]


def _load_session_debrief(session_name: str) -> dict | None:
	"""Read the most recent debrief for a session.

	The Debrief doctype stores criterion_scores/strengths/improvements as
	child tables (LMSA Criterion Score, LMSA Debrief Strength,
	LMSA Debrief Improvement). We load the parent doc and serialise the
	child rows into plain dicts the debrief judge can consume.
	"""
	debrief_names = frappe.get_all(
		"LMSA Simulation Debrief",
		filters={"session": session_name},
		pluck="name",
		limit=1,
	)
	if not debrief_names:
		return None
	doc = frappe.get_doc("LMSA Simulation Debrief", debrief_names[0])
	return {
		"overall_score": doc.overall_score,
		"passed": bool(doc.passed),
		"criterion_scores": [
			{
				"criterion": row.get("criterion_name", ""),
				"score": row.get("score"),
				"evidence_quote": row.get("evidence_quote", ""),
			}
			for row in (doc.criterion_scores or [])
		],
		"strengths": [
			{"title": row.get("title", ""), "quote": row.get("quote", "")}
			for row in (doc.strengths or [])
		],
		"improvements": [
			{
				"title": row.get("title", ""),
				"quote": row.get("quote", ""),
				"suggestion": row.get("suggestion", ""),
			}
			for row in (doc.improvements or [])
		],
	}


def _persist_trace_scores(trace, scores: list[DimensionScore]) -> None:
	judge_versions = {
		DIMENSION_PERSONA: "persona.v1",
		DIMENSION_COVERAGE: "coverage.v1",
		DIMENSION_DEBRIEF: "debrief.v1",
		DIMENSION_DIFFICULTY: "difficulty.v1",
	}
	trace.dimension_scores_json = json.dumps(
		[s.to_dict() for s in scores], ensure_ascii=False
	)
	trace.judge_versions_json = json.dumps(judge_versions)
	trace.trace_status = "complete"


def _compute_aggregates(evaluation) -> None:
	by_dim: dict[str, list[float]] = {
		DIMENSION_PERSONA: [], DIMENSION_COVERAGE: [],
		DIMENSION_DEBRIEF: [], DIMENSION_DIFFICULTY: [],
	}
	for trace in evaluation.traces:
		if trace.trace_status != "complete":
			continue
		for entry in json.loads(trace.dimension_scores_json or "[]"):
			if entry.get("score") is None:
				continue
			by_dim[entry["dimension"]].append(float(entry["score"]))
	evaluation.aggregate_persona_score = (
		mean(by_dim[DIMENSION_PERSONA]) if by_dim[DIMENSION_PERSONA] else None
	)
	evaluation.aggregate_coverage_score = (
		mean(by_dim[DIMENSION_COVERAGE]) if by_dim[DIMENSION_COVERAGE] else None
	)
	evaluation.aggregate_debrief_score = (
		mean(by_dim[DIMENSION_DEBRIEF]) if by_dim[DIMENSION_DEBRIEF] else None
	)
	evaluation.aggregate_difficulty_score = (
		mean(by_dim[DIMENSION_DIFFICULTY]) if by_dim[DIMENSION_DIFFICULTY] else None
	)


def _publish(evaluation) -> None:
	frappe.publish_realtime(
		REALTIME_EVENT,
		message={
			"eval_id": evaluation.name,
			"scenario": evaluation.scenario,
			"run_mode": evaluation.run_mode,
			"status": evaluation.status,
			"source_session": (
				evaluation.traces[0].source_session
				if evaluation.run_mode == "production" and evaluation.traces
				else None
			),
		},
		user=evaluation.triggered_by,
	)


def run_production_evaluation(eval_id: str) -> None:
	"""Job entry point: evaluate a single real session and persist scores."""
	evaluation = frappe.get_doc("LMSA Quality Evaluation", eval_id)
	try:
		evaluation.status = "running"
		evaluation.save(ignore_permissions=True)
		frappe.db.commit()

		provider = _get_provider()
		model = _get_eval_model()
		scenario = _scenario_ref(evaluation.scenario)
		trace = evaluation.traces[0]
		transcript = _load_session_transcript(trace.source_session)
		debrief_payload = _load_session_debrief(trace.source_session)

		scores = evaluate_transcript(
			transcript=transcript,
			scenario=scenario,
			trace_kind="production_session",
			provider=provider,
			debrief_payload=debrief_payload,
			model=model,
		)
		_persist_trace_scores(trace, scores)
		_compute_aggregates(evaluation)
		evaluation.status = "complete"
	except Exception as e:  # noqa: BLE001
		evaluation.status = "failed"
		evaluation.error_message = str(e)
		frappe.log_error(message=str(e), title="run_production_evaluation")
	finally:
		evaluation.save(ignore_permissions=True)
		frappe.db.commit()
		_publish(evaluation)
