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


def _has_active_golden(scenario_name: str) -> bool:
	return bool(frappe.get_all(
		"LMSA Scenario Golden Run",
		filters={"scenario": scenario_name, "active": 1},
		limit=1,
	))


def _create_evaluation(scenario_name: str, run_mode: str) -> str:
	doc = frappe.get_doc({
		"doctype": "LMSA Quality Evaluation",
		"scenario": scenario_name,
		"run_mode": run_mode,
		"status": "queued",
		"triggered_by": frappe.session.user,
		"triggered_at": frappe.utils.now_datetime(),
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


@frappe.whitelist()
def run_quick_check(scenario: str) -> dict:
	require_scenario_access(scenario)
	if not _has_active_golden(scenario):
		frappe.throw(
			"Crea almeno un golden run attivo per lanciare la valutazione."
		)
	eval_id = _create_evaluation(scenario, "quick")
	frappe.enqueue(
		"os_lms.os_lms.ai.simulations.eval.jobs.run_authoring_evaluation",
		queue="default",
		timeout=600,
		eval_id=eval_id,
	)
	return {"eval_id": eval_id}


@frappe.whitelist()
def run_deep_evaluation(scenario: str) -> dict:
	require_scenario_access(scenario)
	if not _has_active_golden(scenario):
		frappe.throw(
			"Crea almeno un golden run attivo per lanciare la valutazione."
		)
	eval_id = _create_evaluation(scenario, "deep")
	frappe.enqueue(
		"os_lms.os_lms.ai.simulations.eval.jobs.run_authoring_evaluation",
		queue="long",
		timeout=1800,
		eval_id=eval_id,
	)
	return {"eval_id": eval_id}


@frappe.whitelist()
def run_production_evaluation(session_id: str) -> dict:
	require_session_access(session_id)
	scenario = frappe.db.get_value(
		"LMSA Simulation Session", session_id, "scenario"
	)
	if not scenario:
		frappe.throw(f"Session {session_id} has no scenario.")
	doc = frappe.get_doc({
		"doctype": "LMSA Quality Evaluation",
		"scenario": scenario,
		"run_mode": "production",
		"status": "queued",
		"triggered_by": frappe.session.user,
		"triggered_at": frappe.utils.now_datetime(),
		"traces": [{
			"trace_kind": "production_session",
			"source_session": session_id,
		}],
	})
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
		traces_out.append({
			"trace_kind": trace.trace_kind,
			"student_profile": trace.student_profile,
			"source_session": trace.source_session,
			"source_golden": trace.source_golden,
			"trace_status": trace.trace_status,
			"trace_error": trace.trace_error,
			"transcript": json.loads(trace.transcript_json or "[]"),
			"dimension_scores": json.loads(trace.dimension_scores_json or "[]"),
			"judge_versions": json.loads(trace.judge_versions_json or "{}"),
		})
	return {
		"eval_id": evaluation.name,
		"scenario": evaluation.scenario,
		"run_mode": evaluation.run_mode,
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
			"name as eval_id", "triggered_at", "run_mode", "status",
			"aggregate_persona_score", "aggregate_coverage_score",
			"aggregate_debrief_score", "aggregate_difficulty_score",
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
			"name as eval_id", "triggered_at", "status",
			"aggregate_persona_score", "aggregate_coverage_score",
			"aggregate_debrief_score", "aggregate_difficulty_score",
		],
		order_by="triggered_at desc",
		limit=50,
	)


@frappe.whitelist()
def list_goldens(scenario: str) -> list[dict]:
	require_scenario_access(scenario)
	rows = frappe.get_all(
		"LMSA Scenario Golden Run",
		filters={"scenario": scenario},
		fields=["name", "name_label", "active", "turns"],
		order_by="creation asc",
	)
	for r in rows:
		try:
			r["turn_count"] = len(json.loads(r.pop("turns") or "[]"))
		except (json.JSONDecodeError, TypeError):
			r["turn_count"] = 0
	return rows


@frappe.whitelist()
def save_golden(payload: dict) -> dict:
	if isinstance(payload, str):
		payload = json.loads(payload)
	scenario = payload.get("scenario")
	if not scenario:
		frappe.throw("scenario is required")
	require_scenario_access(scenario)
	name = payload.get("name")
	if name and frappe.db.exists("LMSA Scenario Golden Run", name):
		doc = frappe.get_doc("LMSA Scenario Golden Run", name)
	else:
		doc = frappe.new_doc("LMSA Scenario Golden Run")
		doc.scenario = scenario
	doc.name_label = payload.get("name_label", "")
	doc.active = 1 if payload.get("active", True) else 0
	doc.expected_outcomes = payload.get("expected_outcomes", "")
	doc.turns = json.dumps(payload.get("turns") or [], ensure_ascii=False)
	doc.save(ignore_permissions=True)
	return {"name": doc.name}


@frappe.whitelist()
def delete_golden(golden_name: str) -> dict:
	doc = frappe.get_doc("LMSA Scenario Golden Run", golden_name)
	require_scenario_access(doc.scenario)
	frappe.delete_doc(
		"LMSA Scenario Golden Run", golden_name, ignore_permissions=True
	)
	return {"ok": True}
