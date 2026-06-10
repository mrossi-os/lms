from __future__ import annotations

import frappe
from frappe import _

from lms.lms.utils import get_course_details, has_moderator_role, is_instructor
from os_lms.os_lms.ai.ingestion import IngestionService
from os_lms.os_lms.ai.utils.course_context import format_course_context
from os_lms.os_lms.ai.utils.llm import ChatMessage, load_settings, resolve_provider
from os_lms.os_lms.ai.utils.oslms_settings import OsLmsSettings
from os_lms.os_lms.ai.utils.template_loader import (
	PURPOSE_TUTOR,
	load_prompt_template,
	render_template,
)


class TutorAi:
	"""AI tutor scoped to a learner inside a course and (optionally) a lesson.

	Builds the conversation context (system prompt + history) and dispatches
	questions to the configured LLM provider via ``resolve_provider("chat")``.
	"""

	def __init__(self, course: str, lesson: str | None, user: str):
		if not course:
			frappe.throw(_("Course is required"))
		self.course = course
		self.lesson = lesson
		self.user = user
		self._course_details: dict | None = None
		self._settings: OsLmsSettings | None = None

	@property
	def course_details(self) -> dict:
		if self._course_details is None:
			details = get_course_details(self.course)
			if not details:
				frappe.throw(_("Course not found or inaccessible"))
			self._course_details = details

		return self._course_details

	@property
	def settings(self) -> OsLmsSettings:
		if self._settings is None:
			self._settings = load_settings()
		return self._settings

	def ask(self, question: str, history: list[dict] | None = None) -> str:
		if not question or not question.strip():
			frappe.throw(_("Question is required"))

		question = question.strip()
		messages = self._build_messages(question, history or [])

		answer = ""
		context = ""
		status = "Failed"
		try:
			system_prompt, context = self._system_prompt(question)
			provider = resolve_provider("chat")
			response = provider.chat(messages=messages, system=system_prompt)
			answer = response.text
			status = "Answered"
			return answer
		finally:
			self._log_query(question=question, answer=answer, context=context, status=status)

	def _system_prompt(self, question: str) -> tuple[str, str]:
		"""Build the system prompt and return it together with the labeled
		chunks string used as context — so `ask` can log both."""
		course = self.course_details
		service = IngestionService(settings=self.settings)

		chunks = []
		if is_instructor(self.course) or has_moderator_role(self.user):
			chunks = service.search_chunks_by_course(self.course, question)
		else:
			completed = set(
				frappe.get_all(
					"LMS Course Progress",
					filters={"course": course, "member": self.user, "status": "Complete"},
					pluck="lesson",
				)
			)
			chunks = service.search_chunks_by_lessons(self.course, list(completed), question)

		labeled_chunks = self._label_chunks(chunks)
		lessons_content = "\n\n---\n\n".join(labeled_chunks)
		current_lesson_content = "\n\n---\n\n".join(
			c.get("content", "") for c in chunks if c.get("lesson") == self.lesson
		)
		course_context = format_course_context(self.course_details, include_title=True)
		template = load_prompt_template(PURPOSE_TUTOR)["system_template"]
		prompt = render_template(
			template,
			{
				"course_details": course_context,
				"lessons_content": lessons_content,
				"current_lesson_content": current_lesson_content,
			},
		)
		return prompt, lessons_content

	def _log_query(self, *, question: str, answer: str, context: str, status: str) -> None:
		"""Persist the Q&A interaction to LMSA Query Log (best-effort).

		``lesson`` is optional in the doctype: course-level questions are
		logged with an empty lesson link. Failures never propagate — audit
		must never break the user-facing flow.
		"""
		try:
			log = frappe.new_doc("LMSA Query Log")
			log.course = self.course
			log.lesson = self.lesson or ""
			log.member = self.user
			log.question = question
			log.answer = answer
			log.context = context
			log.status = status
			log.save(ignore_permissions=True)
			frappe.db.commit()
		except Exception:
			frappe.log_error(title="LMSA Query Log write failed")

	def _label_chunks(self, chunks: list[dict]) -> list[str]:
		"""Prefix each retrieved chunk with its source lesson, so the model can
		attribute and connect content across lessons. Kept internal (not shown
		in the UI)."""
		title_map = {
			row.name: row.title
			for row in frappe.get_all(
				"Course Lesson", filters={"course": self.course}, fields=["name", "title"]
			)
		}
		labeled = []
		for chunk in chunks:
			title = title_map.get(chunk.get("lesson")) or ""
			if title:
				labeled.append(f'[Lezione: "{title}"]\n{chunk["content"]}')
			else:
				labeled.append(chunk["content"])
		return labeled

	def _build_messages(self, question: str, history: list[dict]) -> list[ChatMessage]:
		messages = [
			ChatMessage(
				role="user" if turn.get("from") == "user" else "assistant",
				content=turn.get("message", ""),
			)
			for turn in history
		]
		messages.append(ChatMessage(role="user", content=question))
		return messages
