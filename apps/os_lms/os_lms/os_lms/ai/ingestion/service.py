import hashlib
import logging

import frappe
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
			text = self._normalize_lesson_text(lesson)

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

		"""Return the ingestion status for a lesson.

		Reads the LMSA Material record (if any) and compares the stored
		source_hash with the hash of the lesson's current text content,
		so the caller can tell whether a re-ingestion is needed.
		"""
		material = frappe.db.get_value(
			"LMSA Material",
			{"lesson": lesson.name},
			["name", "status", "chunk_count", "last_ingested_on", "source_hash"],
			as_dict=True,
		)

		if not material:
			return {
				"status": "not_ingested",
				"chunk_count": 0,
				"last_ingested_on": None,
				"needs_update": True,
			}

		current_text = self._normalize_lesson_text(lesson)
		current_hash = self._material_hash(current_text) if current_text else ""
		needs_update = material.source_hash != current_hash
		if material.status and material.status.lower() == "failed":
			needs_update = True

		return {
			"status": material.status.lower(),
			"chunk_count": material.chunk_count or 0,
			"last_ingested_on": (str(material.last_ingested_on) if material.last_ingested_on else None),
			"needs_update": needs_update,
			"material": material.name,
		}

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

	def _normalize_lesson_text(self, lesson) -> str:
		"""Extract plain text from a lesson via LessonContentParser."""
		return LessonContentParser(lesson).extract_text()

	@staticmethod
	def _material_hash(text: str) -> str:
		"""SHA256 hash of text content (used to detect content changes)."""
		return hashlib.sha256(text.encode("utf-8")).hexdigest()
