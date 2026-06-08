import logging

import frappe
from frappe.utils import now_datetime

from os_lms.os_lms.ai.utils.lesson_parser import LessonContentParser
from os_lms.os_lms.ai.utils.llm import load_settings
from os_lms.os_lms.ai.utils.llm.chatbot import Chatbot
from os_lms.os_lms.ai.utils.llm.gpt_chatbot import GptChatbot
from os_lms.os_lms.ai.utils.oslms_settings import OsLmsSettings
from os_lms.os_lms.ai.utils.rag_db import RagDB


class IngestionService:
	def __init__(self, settings: OsLmsSettings | None = None):
		self._settings: OsLmsSettings | None = settings
		self._rag_db: RagDB | None = None
		self._chatbot: Chatbot | None = None
		self._logger: logging.Logger | None = None

	@property
	def settings(self) -> OsLmsSettings:
		if self._settings is None:
			self._settings = load_settings()
		return self._settings

	@property
	def logger(self) -> logging.Logger:
		if self._logger is None:
			self._logger = frappe.logger("os_lmsa", allow_site=True)
		return self._logger

	@property
	def chatbot(self) -> Chatbot:
		if self._chatbot is None:
			chatbot = GptChatbot()
			chatbot.set_settings(self.settings)
			self._chatbot = chatbot
		return self._chatbot

	@property
	def rag_db(self) -> RagDB:
		if self._rag_db is None:
			self._rag_db = RagDB(self.settings)
		return self._rag_db

	def add_lesson_to_ingest_queue(self, lesson):
		if not self.settings.enabled:
			frappe.throw("LMSA is not enabled")
		if lesson.index_status == "processing":
			return
		lesson.index_status = "pending"
		lesson.save()

	def reindex_lesson_content(self):
		"""Re-index all lessons with pending or null index_status."""
		if not self.settings.enabled:
			self.logger.info("LMSA is not enabled, skipping reindex")
			return

		lessons = frappe.get_all(
			"Course Lesson",
			filters=[["index_status", "in", ["pending", None, ""]]],
			pluck="name",
		)

		self.logger.info("Found %d lessons to reindex", len(lessons))

		for lesson_name in lessons:
			try:
				lesson = frappe.get_doc("Course Lesson", lesson_name)
				self.ingest_lesson(lesson)
			except Exception as e:
				self.logger.error("Reindex failed for lesson %s: %s", lesson_name, e)

	def ingest_lesson(self, lesson):
		"""Main ingestion function for a lesson."""
		if not self.settings.enabled:
			frappe.throw("LMSA is not enabled")

		if lesson.index_status == "processing":
			self.logger.info("Lesson %s already processing, skipping", lesson.name)
			return

		self.logger.info("Starting ingestion for lesson %s", lesson.name)
		lesson.index_status = "processing"
		lesson.save()
		frappe.db.commit()

		try:
			parser = LessonContentParser(lesson)
			text = parser.extract_text()

			if not text:
				frappe.throw("No content found in lesson")

			self.rag_db.ingest_data(lesson.course, lesson.name, text)

			lesson.index_status = "indexed"
			lesson.indexed_at = now_datetime()
			self.logger.info("Lesson %s indexed successfully", lesson.name)
		except Exception as e:
			lesson.index_status = "failed"
			self.logger.error("Ingestion failed for lesson %s: %s", lesson.name, e)
			raise
		finally:
			lesson.save()
			frappe.db.commit()

	def search_chunks_by_course(self, course: str, question: str) -> list[dict]:
		"""Retrieve relevant chunks across all lessons of a course."""
		return self.rag_db.search(course, [], question)

	def search_chunks_by_lessons(self, course: str, lessons: list[str], question: str) -> list[dict]:
		"""Retrieve relevant chunks restricted to the given lessons."""
		if not self.settings.enabled:
			frappe.throw("LMSA is not enabled")
		if not lessons:
			return []
		return self.rag_db.search(course, lessons, question)

	def _build_course_context(self, lesson) -> dict:
		"""Build the student's progress map and the lessons the tutor may use.

		Allowed lessons = the current lesson plus every lesson the student has
		already completed in this course. Lessons not yet completed are
		intentionally excluded so the tutor cannot reveal their content.

		Returns:
		    dict with:
		        - allowed: set of lesson names the tutor may retrieve from.
		        - title_map: {lesson_name: (number, title)} for the whole course.
		        - meta: course/lesson titles and the formatted progress outline,
		          passed to the chatbot to enrich the prompt.
		"""
		course = lesson.course
		member = frappe.session.user

		completed = set(
			frappe.get_all(
				"LMS Course Progress",
				filters={"course": course, "member": member, "status": "Complete"},
				pluck="lesson",
			)
		)
		allowed = completed | {lesson.name}

		course_title = frappe.db.get_value("LMS Course", course, "title") or course

		# Batch-load all lesson titles for the course (get_all bypasses permissions).
		title_lookup = {
			row.name: row.title
			for row in frappe.get_all("Course Lesson", filters={"course": course}, fields=["name", "title"])
		}

		chapters = frappe.get_all(
			"Chapter Reference",
			filters={"parent": course},
			fields=["idx", "chapter"],
			order_by="idx",
		)

		outline_lines = []
		title_map = {}
		current_number = ""
		for chapter in chapters:
			lesson_rows = frappe.get_all(
				"Lesson Reference",
				filters={"parent": chapter.chapter},
				fields=["lesson", "idx"],
				order_by="idx",
			)
			for row in lesson_rows:
				number = f"{chapter.idx}-{row.idx}"
				title = title_lookup.get(row.lesson, row.lesson)
				title_map[row.lesson] = (number, title)

				if row.lesson == lesson.name:
					marker = "▶"
					current_number = number
				elif row.lesson in completed:
					marker = "✓"
				else:
					marker = "○"
				outline_lines.append(f"{marker} {number} {title}")

		meta = {
			"course_title": course_title,
			"lesson_title": lesson.title,
			"lesson_number": current_number,
			"outline_text": "\n".join(outline_lines),
		}
		return {"allowed": allowed, "title_map": title_map, "meta": meta}

	def _label_chunks(self, chunks: list[dict], title_map: dict) -> list[str]:
		"""Prefix each retrieved chunk with its source lesson, so the model can
		attribute and connect content across lessons. Kept internal (not shown
		in the UI)."""
		labeled = []
		for chunk in chunks:
			number, title = title_map.get(chunk.get("lesson"), ("", ""))
			if title:
				labeled.append(f'[Lezione {number} — "{title}"]\n{chunk["content"]}')
			else:
				labeled.append(chunk["content"])
		return labeled

	def ask(self, lesson, question: str) -> str:
		"""Ask a question about a lesson using RAG context and LLM chatbot.

		Retrieves relevant chunks from the current lesson and any lesson the
		student has already completed, enriches the prompt with the course title,
		lesson title and the student's progress, sends them to the chatbot, and
		logs the interaction in LMSA Query Log.

		Args:
		    lesson: The Course Lesson document.
		    question: The student's question.

		Returns:
		    The chatbot's answer as a string.

		Raises:
		    frappe.ValidationError: If LMSA is not enabled or no context is found.
		"""
		if not self.settings.enabled:
			frappe.throw("LMSA is not enabled")

		context_chunks = []
		answer = ""
		status = "Failed"

		try:
			# Build the course/progress context and the set of allowed lessons
			ctx = self._build_course_context(lesson)

			# Search relevant chunks across the current + completed lessons
			raw_chunks = self.rag_db.search(lesson.course, list(ctx["allowed"]), question)
			if not raw_chunks:
				frappe.throw("Lesson context not found")

			# Label each chunk with its source lesson for cross-lesson integration
			context_chunks = self._label_chunks(raw_chunks, ctx["title_map"])

			# Generate answer using the LLM chatbot
			answer = self.chatbot.ask(question, context_chunks, lesson_context=ctx["meta"])
			status = "Answered"
		except Exception as e:
			self.logger.error("Ask failed for lesson %s: %s", lesson.name, e)
			raise
		finally:
			# Always log the query, regardless of success or failure
			try:
				log = frappe.new_doc("LMSA Query Log")
				log.course = lesson.course
				log.lesson = lesson.name
				log.member = frappe.session.user
				log.question = question
				log.answer = answer
				log.context = "\n\n---\n\n".join(context_chunks) if context_chunks else ""
				log.status = status
				log.save(ignore_permissions=True)
				frappe.db.commit()
			except Exception as e:
				self.logger.error("Failed to save query log: %s", e)

		return answer
