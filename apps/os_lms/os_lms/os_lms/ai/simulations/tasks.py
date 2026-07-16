"""Background jobs for the simulations feature.

Currently exposes a single RQ task: `generate_debrief(session_id)`.
Enqueued by SessionOrchestrator.end_session and addressable from anywhere
via the dotted module path (see hooks.py / enqueue calls).
"""

from __future__ import annotations

import json
import logging
import time

import frappe
from frappe import _

from os_lms.os_lms.ai.utils.llm import (
	ChatMessage,
	JsonSchema,
	LLMError,
	chat_with_fallback,
)

from .prompts import (
	DEBRIEF_SCHEMA,
	DEBRIEF_VERSION,
	DebriefResult,
	build_debrief_messages,
	parse_debrief_output,
)

EVENT_DEBRIEF_READY = "simulation:debrief_ready"
EVENT_DEBRIEF_FAILED = "simulation:debrief_failed"


def generate_debrief(session_id: str) -> str:
	"""Run the debrief Prompt 3 for `session_id` and persist the result.

	Returns the Debrief docname. Designed to run inside an RQ worker but also
	safe to call inline (in tests). Idempotent: if a debrief already exists
	for the session, it is updated rather than duplicated.
	"""
	logger = frappe.logger("os_lmsa", allow_site=True)
	session = frappe.get_doc("LMSA Simulation Session", session_id)

	debrief = _get_or_create_debrief(session)
	debrief.status = "Pending"
	debrief.save(ignore_permissions=True)
	frappe.db.commit()

	try:
		result, raw_text, provider_used, model_used = _ask_llm(session, logger)
	except LLMError as e:
		debrief.status = "Failed"
		debrief.raw_llm_response = f"{type(e).__name__}: {e}"
		debrief.save(ignore_permissions=True)
		frappe.db.commit()
		_publish(session, EVENT_DEBRIEF_FAILED, {"debrief": debrief.name, "reason": str(e)})
		logger.error("debrief failed: session=%s err=%s", session_id, e)
		raise

	if result is None:
		# Parser failed twice — keep raw output for review.
		debrief.status = "Needs Review"
		debrief.raw_llm_response = raw_text
		debrief.debrief_provider_used = provider_used
		debrief.debrief_model_used = model_used
		debrief.prompt_version = DEBRIEF_VERSION
		debrief.save(ignore_permissions=True)
		frappe.db.commit()
		_publish(session, EVENT_DEBRIEF_FAILED, {"debrief": debrief.name, "reason": "parse failure"})
		logger.warning("debrief parsing failed twice: session=%s", session_id)
		return debrief.name

	# Success: write the structured fields, then back-fill recommendations
	# with RAG (best-effort: never blocks publication).
	_populate_debrief(debrief, result)
	debrief.raw_llm_response = raw_text
	debrief.debrief_provider_used = provider_used
	debrief.debrief_model_used = model_used
	debrief.prompt_version = DEBRIEF_VERSION
	debrief.status = "Ready"
	debrief.save(ignore_permissions=True)
	frappe.db.commit()

	try:
		_enrich_recommendations_with_rag(debrief, session)
	except Exception as e:
		# RAG is optional enrichment; never fail the debrief over it.
		logger.warning("debrief rag enrichment skipped: %s", e)

	_publish(session, EVENT_DEBRIEF_READY, {"debrief": debrief.name})
	logger.info(
		"debrief ready: session=%s score=%s provider=%s",
		session_id,
		result.overall_score,
		provider_used,
	)
	return debrief.name


# ----- helpers -----


def _get_or_create_debrief(session) -> frappe.model.document.Document:
	name = frappe.db.get_value("LMSA Simulation Debrief", {"session": session.name}, "name")
	if name:
		return frappe.get_doc("LMSA Simulation Debrief", name)
	doc = frappe.new_doc("LMSA Simulation Debrief")
	doc.session = session.name
	doc.status = "Pending"
	doc.insert(ignore_permissions=True)
	return doc


def _ask_llm(session, logger: logging.Logger) -> tuple[DebriefResult | None, str, str, str]:
	"""Return (result, raw_text, provider, model). result=None on parse failure."""
	scenario = frappe.get_doc("LMSA Simulation Scenario", session.scenario)
	schema = frappe.get_doc("LMSA Evaluation Schema", scenario.evaluation_schema)

	schema_criteria = [
		{
			"name": row.criterion_name,
			"weight": float(row.weight or 0.0),
			"description": row.description or "",
			"observable_behaviors": row.observable_behaviors or "",
		}
		for row in schema.criteria
	]
	objectives = [
		(row.objective_text or "").strip()
		for row in (scenario.learning_objectives or [])
		if (row.objective_text or "").strip()
	]
	transcript = frappe.db.get_all(
		"LMSA Simulation Turn",
		filters={"session": session.name},
		fields=["role", "text_content"],
		order_by="turn_index asc",
	)
	transcript_dicts = [{"role": t["role"], "text": t["text_content"]} for t in transcript]

	system, messages = build_debrief_messages(
		scenario_name=scenario.scenario_name,
		difficulty=scenario.difficulty,
		learning_objectives=objectives,
		schema_criteria=schema_criteria,
		transcript=transcript_dicts,
	)
	chat_messages = [ChatMessage(role=m["role"], content=m["content"]) for m in messages]

	t0 = time.monotonic()
	response = chat_with_fallback(
		"debrief",
		chat_messages,
		system=system,
		temperature=0.2,
		max_tokens=2000,
		response_format=JsonSchema(name="debrief", schema=DEBRIEF_SCHEMA),
	)
	logger.info(
		"debrief llm call: session=%s provider=%s latency_ms=%d",
		session.name,
		response.provider,
		int((time.monotonic() - t0) * 1000),
	)

	try:
		return parse_debrief_output(response.text), response.text, response.provider, response.model
	except ValueError as first_err:
		logger.warning("debrief parse failed once, retrying at temperature=0: %s", first_err)

	# Corrective retry at temperature 0
	retry = chat_with_fallback(
		"debrief",
		chat_messages
		+ [
			ChatMessage(role="assistant", content=response.text),
			ChatMessage(
				role="user",
				content=(
					"L'output non era JSON valido secondo lo schema. Riprova "
					"rispondendo ESCLUSIVAMENTE con un oggetto JSON valido, "
					"senza testo prima o dopo."
				),
			),
		],
		system=system,
		temperature=0,
		max_tokens=2000,
		response_format=JsonSchema(name="debrief", schema=DEBRIEF_SCHEMA),
	)
	try:
		return parse_debrief_output(retry.text), retry.text, retry.provider, retry.model
	except ValueError as second_err:
		logger.warning("debrief parse failed twice: %s", second_err)
		return None, retry.text, retry.provider, retry.model


def _populate_debrief(debrief, result: DebriefResult) -> None:
	"""Write the parsed DebriefResult into the doc and its child tables."""
	debrief.overall_score = result.overall_score
	debrief.behavioral_analysis = result.behavioral_analysis

	debrief.set("criterion_scores", [])
	for c in result.criterion_scores:
		debrief.append(
			"criterion_scores",
			{
				"criterion_name": c.criterion,
				"score": c.score,
				"max_score": c.max_score,
				"evidence_quote": c.evidence_quote,
				"note": c.note,
			},
		)

	debrief.set("strengths", [])
	for s in result.strengths:
		debrief.append("strengths", {"title": s.title, "detail": s.detail, "quote": s.quote})

	debrief.set("improvements", [])
	for i in result.improvements:
		debrief.append(
			"improvements",
			{
				"title": i.title,
				"detail": i.detail,
				"quote": i.quote,
				"suggestion": i.suggestion,
			},
		)

	debrief.set("recommended_content", [])
	for r in result.recommended_content:
		row = {"title": r.title, "why": r.why}
		# If the LLM proposed a lesson id, verify it actually exists and is
		# in the session's course. Otherwise, leave the field empty for RAG
		# enrichment to fill.
		if r.lesson and frappe.db.exists("Course Lesson", r.lesson):
			row["lesson"] = r.lesson
		debrief.append("recommended_content", row)


def _enrich_recommendations_with_rag(debrief, session) -> None:
	"""Back-fill `lesson` and add up to 3 RAG-suggested lessons.

	Uses the existing RagDB facade (RAG tutor pipeline) to find lessons of the
	same course relevant to the improvement areas. Best-effort: any failure is
	caught by the caller, so RAG outages never block the debrief.
	"""
	from os_lms.os_lms.ai.utils.llm import _load_settings
	from os_lms.os_lms.ai.utils.rag_db import RagDB

	settings = _load_settings()
	if not settings.enabled or not session.course:
		return

	rag = RagDB(settings)

	# Build the search query from the improvements (titles + suggestions).
	query_parts: list[str] = []
	for imp in debrief.improvements:
		if imp.title:
			query_parts.append(imp.title)
		if imp.suggestion:
			query_parts.append(imp.suggestion)
	if debrief.behavioral_analysis:
		query_parts.append(debrief.behavioral_analysis[:200])
	query = " ".join(query_parts).strip()
	if not query:
		return

	try:
		hits = rag.search(query=query, course=session.course, top_k=5)
	except Exception:
		return

	# Map lesson -> (best_score, title). hits is a list of dict-like records;
	# we look for the `lesson` and `score`/similarity keys defensively.
	by_lesson: dict[str, dict] = {}
	for h in hits or []:
		lesson_id = h.get("lesson") if isinstance(h, dict) else None
		if not lesson_id or not frappe.db.exists("Course Lesson", lesson_id):
			continue
		score = float(h.get("score") or h.get("similarity") or 0)
		if lesson_id not in by_lesson or score > by_lesson[lesson_id]["score"]:
			by_lesson[lesson_id] = {
				"score": score,
				"title": frappe.db.get_value("Course Lesson", lesson_id, "title") or lesson_id,
			}

	if not by_lesson:
		return

	# 1) Back-fill empty `lesson` slots on existing rows (LLM titles → RAG ids).
	existing_lesson_ids = {row.lesson for row in debrief.recommended_content if row.lesson}
	available = [(lid, info) for lid, info in by_lesson.items() if lid not in existing_lesson_ids]
	available.sort(key=lambda kv: -kv[1]["score"])

	for row in debrief.recommended_content:
		if row.lesson:
			continue
		if not available:
			break
		lid, info = available.pop(0)
		row.lesson = lid
		row.relevance_score = info["score"]
		existing_lesson_ids.add(lid)

	# 2) Append up to 2 extra RAG-suggested lessons if we still have budget.
	while available and len(debrief.recommended_content) < 5:
		lid, info = available.pop(0)
		debrief.append(
			"recommended_content",
			{
				"lesson": lid,
				"title": info["title"],
				"why": _("Lezione del corso ad alta rilevanza con l'area di miglioramento."),
				"relevance_score": info["score"],
			},
		)
		existing_lesson_ids.add(lid)

	debrief.save(ignore_permissions=True)
	frappe.db.commit()


def _publish(session, event: str, payload: dict) -> None:
	try:
		frappe.publish_realtime(
			event=event,
			message={"session": session.name, **payload},
			user=session.student,
		)
	except Exception:
		# Best-effort delivery; caller logs.
		pass


# A session with no activity for this many minutes is treated as left behind by
# the scheduled reaper (the student never pressed "Termina", closed the tab, or
# dropped the connection).
STALE_SESSION_IDLE_MINUTES = 30


def reap_stale_sessions() -> dict:
	"""Close simulation sessions the student never ended (scheduled, cron).

	Finds ``In Progress`` / ``Ready`` sessions idle for at least
	``STALE_SESSION_IDLE_MINUTES`` and ends them through the orchestrator, which
	decides the outcome server-side: Completed when the chat time cap was
	reached during the conversation, otherwise Abandoned. A debrief is generated
	only for the Completed ones — abandoned sessions produce nothing.

	This is the reliable backstop for every case the browser can't report (tab
	closed abruptly, crash, dropped voice connection): the frontend closes the
	common cases immediately, this sweeps whatever is left.
	"""
	from os_lms.os_lms.ai.simulations import SessionOrchestrator
	from os_lms.os_lms.doctype.lmsa_simulation_session.lmsa_simulation_session import (
		STATUS_IN_PROGRESS,
		STATUS_READY,
	)

	logger = frappe.logger("os_lmsa", allow_site=True)
	cutoff = frappe.utils.add_to_date(
		frappe.utils.now_datetime(), minutes=-STALE_SESSION_IDLE_MINUTES
	)

	candidates = frappe.get_all(
		"LMSA Simulation Session",
		filters={"status": ["in", [STATUS_IN_PROGRESS, STATUS_READY]]},
		fields=["name", "modified", "started_at"],
		order_by="modified asc",
		limit=200,
	)

	orchestrator = SessionOrchestrator()
	reaped = 0
	for s in candidates:
		last = _last_activity(s.name) or s.modified or s.started_at
		if not last or frappe.utils.get_datetime(last) > cutoff:
			# Still active (recent turn) or missing timestamp: leave it be.
			continue
		try:
			orchestrator.end_session(session_id=s.name, reason="abandoned")
			reaped += 1
		except Exception as e:
			logger.warning("reap_stale_sessions: failed to close %s: %s", s.name, e)

	if reaped:
		logger.info("reap_stale_sessions: closed %s stale session(s)", reaped)
	return {"reaped": reaped, "scanned": len(candidates)}


def _last_activity(session_name: str):
	"""Creation time of the session's most recent turn, or None if it has none."""
	rows = frappe.db.get_all(
		"LMSA Simulation Turn",
		filters={"session": session_name},
		fields=["creation"],
		order_by="creation desc",
		limit=1,
	)
	return rows[0].creation if rows else None
