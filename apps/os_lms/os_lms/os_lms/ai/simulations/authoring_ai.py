"""AI-assisted authoring helpers.

Generate a pre-filled payload for ``LMSA Simulation Scenario`` or
``LMSA Evaluation Schema`` by combining:

- a configurable prompt template (``LMSA Prompt Template`` doctype, with
  hardcoded fallback in :mod:`prompts.template_loader`)
- an optional RAG context retrieved from the course / lesson the
  instructor selected (same path used by ``AuthoringEvaluationRunner``)
- a free-text instructor hint

The result is a plain dict ready to feed into the existing ``save_*``
endpoints — these helpers never write to the DB themselves: the form
populates, the instructor reviews, the user saves.
"""

from __future__ import annotations

import json

import frappe
from frappe import _

from os_lms.os_lms.ai.simulations.prompts.template_loader import (
	PURPOSE_EVALUATION_SCHEMA_GENERATOR_AI,
	PURPOSE_SCENARIO_GENERATOR_AI,
	load_prompt_template,
	render_template,
)
from os_lms.os_lms.ai.utils.llm.provider import ChatMessage, JsonSchema

# ---------- response_format schemas (OpenAI strict-mode compatible) ----------

SCENARIO_OUTPUT_SCHEMA: dict = {
	"type": "object",
	"additionalProperties": False,
	"required": [
		"scenario_name",
		"difficulty",
		"modality",
		"roleplay_persona",
		"situation_template",
		"max_turns",
		"time_limit_minutes",
		"learning_objectives",
		"seed_variations",
	],
	"properties": {
		"scenario_name": {"type": "string"},
		"difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
		"modality": {"type": "string", "enum": ["chat", "voice", "both"]},
		"roleplay_persona": {"type": "string"},
		"situation_template": {"type": "string"},
		"max_turns": {"type": "integer"},
		"time_limit_minutes": {"type": "integer"},
		"learning_objectives": {
			"type": "array",
			"items": {
				"type": "object",
				"additionalProperties": False,
				"required": ["objective_text", "weight"],
				"properties": {
					"objective_text": {"type": "string"},
					"weight": {"type": "number"},
				},
			},
		},
		"seed_variations": {
			"type": "array",
			"items": {
				"type": "object",
				"additionalProperties": False,
				"required": ["variable_name", "possible_values"],
				"properties": {
					"variable_name": {"type": "string"},
					# Newline-separated string, matching the doctype's storage format.
					"possible_values": {"type": "string"},
				},
			},
		},
	},
}

EVAL_SCHEMA_OUTPUT_SCHEMA: dict = {
	"type": "object",
	"additionalProperties": False,
	"required": [
		"schema_name",
		"description",
		"scoring_scale",
		"passing_threshold",
		"criteria",
	],
	"properties": {
		"schema_name": {"type": "string"},
		"description": {"type": "string"},
		"scoring_scale": {"type": "string", "enum": ["0-3", "0-5", "0-10"]},
		"passing_threshold": {"type": "number"},
		"criteria": {
			"type": "array",
			"items": {
				"type": "object",
				"additionalProperties": False,
				"required": [
					"criterion_name",
					"weight",
					"description",
					"observable_behaviors",
				],
				"properties": {
					"criterion_name": {"type": "string"},
					"weight": {"type": "number"},
					"description": {"type": "string"},
					"observable_behaviors": {"type": "string"},
				},
			},
		},
	},
}

# Cap the RAG snippet we inject into the prompt to keep token count bounded.
_MAX_CONTEXT_CHARS = 6000


# ---------- public API ----------


def generate_scenario_payload(
	*,
	course: str,
	lesson: str | None = None,
	hint: str = "",
) -> dict:
	"""Return a dict shaped like the ``save_scenario`` payload.

	The returned dict does NOT include ``lms_course``/``course_lesson``/
	``evaluation_schema`` — those are set by the editor before submit.
	"""
	if not course:
		frappe.throw(_("course is required to generate a scenario."))

	course_name = frappe.db.get_value("LMS Course", course, "title") or course
	lesson_title = (
		frappe.db.get_value("Course Lesson", lesson, "title") if lesson else ""
	) or ""

	rag_query = " ".join(p for p in [lesson_title, course_name, hint] if p).strip()
	lesson_context = _fetch_rag_context(course=course, lesson=lesson, query=rag_query)
	lesson_context_block = (
		f"Estratti del materiale (RAG):\n{lesson_context}\n\n" if lesson_context else ""
	)

	config = load_prompt_template(PURPOSE_SCENARIO_GENERATOR_AI)
	ctx = {
		"course_name": course_name,
		"lesson_title": lesson_title or "(tutto il corso)",
		"lesson_context_block": lesson_context_block,
		"hint": hint or "(nessuno)",
	}
	return _call_llm_for_payload(
		system=render_template(config["system_template"], ctx),
		user=render_template(config["user_template"], ctx),
		temperature=config["temperature"],
		max_tokens=config["max_tokens"],
		schema_name="scenario_payload",
		schema=SCENARIO_OUTPUT_SCHEMA,
	)


def generate_evaluation_schema_payload(
	*,
	hint: str = "",
	course: str | None = None,
	lesson: str | None = None,
) -> dict:
	"""Return a dict shaped like the ``save_evaluation_schema`` payload."""
	course_name = (
		frappe.db.get_value("LMS Course", course, "title") if course else ""
	) or ""
	lesson_title = (
		frappe.db.get_value("Course Lesson", lesson, "title") if lesson else ""
	) or ""

	lesson_context = ""
	if course:
		rag_query = " ".join(
			p for p in [lesson_title, course_name, hint] if p
		).strip()
		lesson_context = _fetch_rag_context(
			course=course, lesson=lesson, query=rag_query
		)

	course_block_parts: list[str] = []
	if course_name:
		course_block_parts.append(f"Corso: {course_name}")
	if lesson_title:
		course_block_parts.append(f"Lezione: {lesson_title}")
	if lesson_context:
		course_block_parts.append(f"Estratti del materiale:\n{lesson_context}")
	course_block = (
		"\n".join(course_block_parts) + "\n\n" if course_block_parts else ""
	)

	config = load_prompt_template(PURPOSE_EVALUATION_SCHEMA_GENERATOR_AI)
	ctx = {
		"course_block": course_block,
		"hint": hint or "(nessuno)",
	}
	return _call_llm_for_payload(
		system=render_template(config["system_template"], ctx),
		user=render_template(config["user_template"], ctx),
		temperature=config["temperature"],
		max_tokens=config["max_tokens"],
		schema_name="evaluation_schema_payload",
		schema=EVAL_SCHEMA_OUTPUT_SCHEMA,
	)


# ---------- internals ----------


def _call_llm_for_payload(
	*,
	system: str,
	user: str,
	temperature: float,
	max_tokens: int,
	schema_name: str,
	schema: dict,
) -> dict:
	provider = _get_provider()
	response = provider.chat(
		[ChatMessage(role="user", content=user)],
		system=system,
		model=_get_model(),
		temperature=temperature,
		max_tokens=max_tokens,
		response_format=JsonSchema(name=schema_name, schema=schema),
	)
	try:
		return json.loads(response.text or "")
	except json.JSONDecodeError as e:
		raise frappe.ValidationError(
			_("LLM returned non-JSON content for {0}: {1}").format(schema_name, e)
		) from e


def _fetch_rag_context(*, course: str, lesson: str | None, query: str) -> str:
	"""Pull lesson excerpts from the RAG index, scoped to `lesson` when set.

	Best-effort: returns an empty string on any failure (RAG disabled, empty
	index, ingestion service error) so the authoring helper still works on
	courses that haven't been indexed.
	"""
	if not course or not query.strip():
		return ""
	try:
		from os_lms.os_lms.ai.ingestion import IngestionService

		service = IngestionService()
		if lesson:
			chunks = service.search_chunks_by_lessons(course, [lesson], query)
		else:
			chunks = service.search_chunks_by_course(course, query)
	except Exception:
		return ""

	parts = [(c.get("content") or "").strip() for c in chunks or []]
	parts = [p for p in parts if p]
	text = "\n\n---\n\n".join(parts)
	return text[:_MAX_CONTEXT_CHARS]


def _get_provider():
	from os_lms.os_lms.ai.utils.llm import resolve_provider

	return resolve_provider("debrief")


def _get_model() -> str | None:
	try:
		settings = frappe.get_single("LMSA Settings")
		return settings.get("simulation_debrief_model") or None
	except Exception:
		return None
