"""Authoring (``simulation_test``) evaluation runner.

Owns the lifecycle of an ``LMSA Quality Evaluation`` in ``simulation_test``
mode: status transitions, generation of N LLM-student conversations, judging
and aggregate computation. The job entry point ``run_authoring_evaluation``
in :mod:`jobs` is just a thin wrapper around :class:`AuthoringEvaluationRunner`.
"""
from __future__ import annotations

import frappe

from os_lms.os_lms.ai.simulations.eval.jobs import (
	_build_trace,
	_compute_aggregates,
	_get_eval_model,
	_get_provider,
	_persist_trace_scores,
	_publish,
	_scenario_ref,
)
from os_lms.os_lms.ai.simulations.eval.pipeline import evaluate_transcript
from os_lms.os_lms.ai.simulations.eval.runner import run_synthetic_llm_student
from os_lms.os_lms.ai.simulations.eval.types import ScenarioRef


class AuthoringEvaluationRunner:
	"""Drive the authoring (simulation_test) evaluation lifecycle.

	Owns the LMSA Quality Evaluation doc, status transitions, save+commit
	and realtime publish. Generates N LLM-student conversations using the
	chosen student profile and runs the 4 judges on each. No golden runs.

	Service Pattern: lazy properties for provider/model/scenario_ref so
	tests that patch ``_get_provider`` (or any other helper) keep working —
	the patch is consulted on first property access, not at construction.
	"""

	def __init__(self, eval_id: str):
		self.evaluation = frappe.get_doc("LMSA Quality Evaluation", eval_id)
		self._provider = None
		self._model: str | None = None
		self._scenario: ScenarioRef | None = None
		self._lesson_context: str | None = None

	# ---- lazy dependencies ----

	@property
	def provider(self):
		if self._provider is None:
			raw = _get_provider()
			from os_lms.os_lms.ai.utils.llm import logger as _logger

			if _logger.ENABLED:
				self._provider = _logger.LoggingProvider(
					raw, _logger.llm_log_path(self.evaluation.name),
				)
			else:
				self._provider = raw
		return self._provider

	@property
	def model(self) -> str | None:
		if self._model is None:
			self._model = _get_eval_model()
		return self._model

	@property
	def scenario(self) -> ScenarioRef:
		if self._scenario is None:
			self._scenario = _scenario_ref(self.evaluation.scenario)
		return self._scenario

	@property
	def lesson_context(self) -> str:
		"""RAG-retrieved excerpt of the lesson/course material the simulated
		student is supposed to have studied. Cached: 1 RAG call per run."""
		if self._lesson_context is None:
			self._lesson_context = self._build_lesson_context()
		return self._lesson_context

	# ---- public entry point ----

	def run(self) -> None:
		"""Execute the full job: mark running → run variants → aggregate
		→ mark complete/failed → save + publish in `finally`."""
		try:
			self._mark_running()
			profile_name, num_variants = self._read_params()
			for _ in range(num_variants):
				self._run_one_variant(profile_name)
			_compute_aggregates(self.evaluation)
			self.evaluation.status = "complete"
		except Exception as e:  # noqa: BLE001
			self.evaluation.status = "failed"
			self.evaluation.error_message = str(e)
			frappe.log_error(message=str(e), title="run_authoring_evaluation")
		finally:
			self.evaluation.save(ignore_permissions=True)
			frappe.db.commit()
			_publish(self.evaluation)

	# ---- internals ----

	def _mark_running(self) -> None:
		self.evaluation.status = "running"
		self.evaluation.save(ignore_permissions=True)
		frappe.db.commit()

	def _read_params(self) -> tuple[str, int]:
		profile_name = self.evaluation.get("student_profile")
		if not profile_name:
			raise ValueError("student_profile non impostato sulla valutazione.")
		num_variants = int(self.evaluation.get("num_variants") or 1)
		if num_variants < 1:
			num_variants = 1
		return profile_name, num_variants

	def _run_one_variant(self, profile_name: str) -> None:
		scenario_brief = self.evaluation.get("student_scenario_brief") or ""
		transcript = run_synthetic_llm_student(
			scenario=self.scenario,
			profile_name=profile_name,
			provider=self.provider,
			model=self.model,
			lesson_context=self.lesson_context,
			scenario_brief=scenario_brief,
		)
		trace = _build_trace(
			self.evaluation,
			trace_kind="llm_student",
			student_profile=profile_name,
			transcript=transcript,
		)
		scores = evaluate_transcript(
			transcript=transcript,
			scenario=self.scenario,
			trace_kind="llm_student",
			provider=self.provider,
			debrief_payload=None,
			model=self.model,
		)
		_persist_trace_scores(trace, scores)

	def _build_lesson_context(self) -> str:
		"""Pull lesson excerpts from the RAG index, scoped to the scenario's
		course_lesson when set, otherwise to the whole course.

		Best-effort: returns empty string on any failure (RAG disabled,
		ingestion service throw, empty index) so the evaluation never
		breaks because of a missing context enhancement.
		"""
		course = self.scenario.course
		if not course:
			return ""

		query_parts = [self.scenario.scenario_name, *self.scenario.learning_objectives]
		query = " ".join(p for p in query_parts if p).strip()
		if not query:
			return ""

		try:
			from os_lms.os_lms.ai.ingestion import IngestionService

			service = IngestionService()
			if self.scenario.course_lesson:
				chunks = service.search_chunks_by_lessons(
					course, [self.scenario.course_lesson], query,
				)
			else:
				chunks = service.search_chunks_by_course(course, query)
		except Exception:
			return ""

		parts = [(c.get("content") or "").strip() for c in chunks or []]
		parts = [p for p in parts if p]
		return "\n\n---\n\n".join(parts)
