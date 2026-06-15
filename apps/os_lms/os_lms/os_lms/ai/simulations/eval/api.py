"""Whitelisted endpoints for the evaluation system.

All endpoints return JSON-serialisable dicts. Permissions are enforced via
eval.permissions helpers; missing prerequisites surface as frappe.throw
with UX-actionable messages.
"""

from __future__ import annotations

import json

import frappe

from os_lms.os_lms.ai.simulations.eval.permissions import (
	require_scenario_access,
	require_session_access,
)
from os_lms.os_lms.ai.simulations.eval.student.profiles import (
	LLM_STUDENT_PROFILES,
)

VALID_PROFILES = {p["name"] for p in LLM_STUDENT_PROFILES}
MAX_VARIANTS = 3

from os_lms.os_lms.ai.simulations.eval.authoring_runner import (  # noqa: E402
	AuthoringEvaluationRunner,
)


@frappe.whitelist()
def run_simulation_test(
	scenario: str,
	student_profile: str,
	num_variants: int = 1,
) -> dict:
	"""Run an authoring simulation test.

	The user picks a student profile and a number of conversation variants
	(1-3). The job spawns N LLM-student conversations against the scenario
	prompts, then runs the 4 judges on each transcript.
	"""
	require_scenario_access(scenario)
	if student_profile not in VALID_PROFILES:
		frappe.throw(
			f"Profilo studente non valido: {student_profile}. Ammessi: {', '.join(sorted(VALID_PROFILES))}."
		)
	try:
		n = int(num_variants)
	except (TypeError, ValueError):
		frappe.throw("num_variants deve essere un intero.")
	if n < 1 or n > MAX_VARIANTS:
		frappe.throw(f"num_variants deve essere tra 1 e {MAX_VARIANTS}.")

	doc = frappe.get_doc(
		{
			"doctype": "LMSA Quality Evaluation",
			"scenario": scenario,
			"run_mode": "simulation_test",
			"student_profile": student_profile,
			"num_variants": n,
			"status": "queued",
			"triggered_by": frappe.session.user,
			"triggered_at": frappe.utils.now_datetime(),
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	AuthoringEvaluationRunner(doc.name).run()

	"""frappe.enqueue(
		"os_lms.os_lms.ai.simulations.eval.jobs.run_authoring_evaluation",
		queue="long" if n > 1 else "default",
		timeout=600 + 600 * (n - 1),
		eval_id=doc.name,
	)"""
	return {"eval_id": doc.name}


@frappe.whitelist()
def run_production_evaluation(session_id: str) -> dict:
	require_session_access(session_id)
	scenario = frappe.db.get_value("LMSA Simulation Session", session_id, "scenario")
	if not scenario:
		frappe.throw(f"Session {session_id} has no scenario.")
	doc = frappe.get_doc(
		{
			"doctype": "LMSA Quality Evaluation",
			"scenario": scenario,
			"run_mode": "production",
			"status": "queued",
			"triggered_by": frappe.session.user,
			"triggered_at": frappe.utils.now_datetime(),
			"traces": [
				{
					"trace_kind": "production_session",
					"source_session": session_id,
				}
			],
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	frappe.enqueue(
		"os_lms.os_lms.ai.simulations.eval.jobs.run_production_evaluation",
		queue="default",
		timeout=600,
		eval_id=doc.name,
	)
	return {"eval_id": doc.name}


@frappe.whitelist()
def get_evaluation_status(eval_id: str) -> dict:
	evaluation = frappe.get_doc("LMSA Quality Evaluation", eval_id)
	require_scenario_access(evaluation.scenario)
	return {
		"eval_id": evaluation.name,
		"scenario": evaluation.scenario,
		"run_mode": evaluation.run_mode,
		"student_profile": evaluation.get("student_profile"),
		"num_variants": evaluation.get("num_variants"),
		"status": evaluation.status,
		"aggregate_persona_score": evaluation.aggregate_persona_score,
		"aggregate_coverage_score": evaluation.aggregate_coverage_score,
		"aggregate_debrief_score": evaluation.aggregate_debrief_score,
		"aggregate_difficulty_score": evaluation.aggregate_difficulty_score,
		"error_message": evaluation.error_message,
	}


@frappe.whitelist()
def get_evaluation_result(eval_id: str) -> dict:
	evaluation = frappe.get_doc("LMSA Quality Evaluation", eval_id)
	require_scenario_access(evaluation.scenario)
	traces_out = []
	for trace in evaluation.traces:
		traces_out.append(
			{
				"trace_kind": trace.trace_kind,
				"student_profile": trace.student_profile,
				"source_session": trace.source_session,
				"trace_status": trace.trace_status,
				"trace_error": trace.trace_error,
				"transcript": json.loads(trace.transcript_json or "[]"),
				"dimension_scores": json.loads(trace.dimension_scores_json or "[]"),
				"judge_versions": json.loads(trace.judge_versions_json or "{}"),
			}
		)
	return {
		"eval_id": evaluation.name,
		"scenario": evaluation.scenario,
		"run_mode": evaluation.run_mode,
		"student_profile": evaluation.get("student_profile"),
		"num_variants": evaluation.get("num_variants"),
		"status": evaluation.status,
		"triggered_by": evaluation.triggered_by,
		"triggered_at": evaluation.triggered_at,
		"aggregate_persona_score": evaluation.aggregate_persona_score,
		"aggregate_coverage_score": evaluation.aggregate_coverage_score,
		"aggregate_debrief_score": evaluation.aggregate_debrief_score,
		"aggregate_difficulty_score": evaluation.aggregate_difficulty_score,
		"error_message": evaluation.error_message,
		"traces": traces_out,
	}


@frappe.whitelist()
def list_evaluations_for_scenario(scenario: str) -> list[dict]:
	require_scenario_access(scenario)
	return frappe.get_all(
		"LMSA Quality Evaluation",
		filters={"scenario": scenario},
		fields=[
			"name as eval_id",
			"triggered_at",
			"run_mode",
			"status",
			"aggregate_persona_score",
			"aggregate_coverage_score",
			"aggregate_debrief_score",
			"aggregate_difficulty_score",
		],
		order_by="triggered_at desc",
		limit=50,
	)


@frappe.whitelist()
def list_evaluations_for_session(session_id: str) -> list[dict]:
	require_session_access(session_id)
	eval_names = frappe.get_all(
		"LMSA Evaluation Trace",
		filters={"source_session": session_id},
		pluck="parent",
	)
	if not eval_names:
		return []
	return frappe.get_all(
		"LMSA Quality Evaluation",
		filters={"name": ["in", eval_names]},
		fields=[
			"name as eval_id",
			"triggered_at",
			"status",
			"aggregate_persona_score",
			"aggregate_coverage_score",
			"aggregate_debrief_score",
			"aggregate_difficulty_score",
		],
		order_by="triggered_at desc",
		limit=50,
	)


@frappe.whitelist()
def list_student_profiles() -> list[dict]:
	"""Return the available LLM-student profiles for the test dialog."""
	return [{"name": p["name"], "label": p["label"]} for p in LLM_STUDENT_PROFILES]


