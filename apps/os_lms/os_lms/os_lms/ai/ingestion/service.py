import logging

import frappe
from frappe import _
from frappe.utils import now_datetime

from os_lms.os_lms.ai.utils.lesson_parser import LessonContentParser
from os_lms.os_lms.ai.utils.llm import load_settings
from os_lms.os_lms.ai.utils.oslms_settings import OsLmsSettings
from os_lms.os_lms.ai.utils.rag_db import RagDB


class IngestionService:
	def __init__(self, settings: OsLmsSettings | None = None):
		self._settings: OsLmsSettings | None = settings
		self._rag_db: RagDB | None = None
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
	def rag_db(self) -> RagDB:
		if self._rag_db is None:
			self._rag_db = RagDB(self.settings)
		return self._rag_db

	def add_lesson_to_ingest_queue(self, lesson):
		if not self.settings.enabled:
			frappe.throw(_("LMSA is not enabled"))
		if lesson.index_status == "processing":
			return
		# db_set skips check_if_latest so a concurrent edit of the lesson
		# (e.g. the form open in another tab) cannot raise TimestampMismatchError.
		lesson.db_set("index_status", "pending", update_modified=False)

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
			frappe.throw(_("LMSA is not enabled"))

		if lesson.index_status == "processing":
			self.logger.info("Lesson %s already processing, skipping", lesson.name)
			return

		self.logger.info("Starting ingestion for lesson %s", lesson.name)
		# Bookkeeping fields (index_status / indexed_at) are written via db_set
		# with update_modified=False so the long embedding call between the
		# two writes cannot race against a concurrent save of the lesson
		# (which would otherwise raise TimestampMismatchError on the final
		# save and leave index_status stuck on "processing"). Same pattern as
		# the enrollment race fix in course_lesson.save_progress.
		lesson.db_set("index_status", "processing", update_modified=False)
		frappe.db.commit()

		try:
			text = self._normalize_lesson_text(lesson)

			if not text:
				frappe.throw(_("No content found in lesson"))

			self.rag_db.ingest_data(lesson.course, lesson.name, text)

			lesson.db_set(
				{"index_status": "indexed", "indexed_at": now_datetime()},
				update_modified=False,
			)
			self.logger.info("Lesson %s indexed successfully", lesson.name)
		except Exception as e:
			lesson.db_set("index_status", "failed", update_modified=False)
			self.logger.error("Ingestion failed for lesson %s: %s", lesson.name, e)
			raise
		finally:
			frappe.db.commit()

	def remove_lesson(self, course: str, lesson: str) -> None:
		"""Delete a lesson's vectors from the RAG index.

		Best-effort and never raises: it runs from the Course Lesson on_trash
		hook, so a missing Redis config or an index error must not block the
		lesson deletion.
		"""
		if not lesson or not frappe.conf.get("redis_vector_store"):
			return
		try:
			self.rag_db.delete_lesson(course, lesson)
		except Exception as e:
			self.logger.error("RAG cleanup failed for lesson %s: %s", lesson, e)

	def search_chunks_by_course(self, course: str, question: str) -> list[dict]:
		"""Retrieve relevant chunks across all lessons of a course."""
		return self.rag_db.search(course, [], question)

	def search_chunks_by_lessons(self, course: str, lessons: list[str], question: str) -> list[dict]:
		"""Retrieve relevant chunks restricted to the given lessons."""
		if not self.settings.enabled:
			frappe.throw(_("LMSA is not enabled"))
		if not lessons:
			return []
		return self.rag_db.search(course, lessons, question)

	def _normalize_lesson_text(self, lesson) -> str:
		"""Extract plain text from a lesson via LessonContentParser."""
		return LessonContentParser(lesson).extract_text()
