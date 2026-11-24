"""The AI tutor must not learn a lesson's instructor-only notes.

Regression: LessonContentParser indexed ``instructor_content`` next to the
lesson body, and the tutor answers learners from that single per-course RAG
index (no role filter on the chunks), so it could repeat the instructor notes
to students.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.events import lesson as lesson_events
from os_lms.os_lms.ai.ingestion.service import IngestionService
from os_lms.os_lms.ai.utils.lesson_parser import LessonContentParser
from os_lms.patches.v0_0_12 import requeue_lessons_with_instructor_content as requeue

STUDENT_TEXT = "Photosynthesis turns light into chemical energy."
INSTRUCTOR_TEXT = "SECRET-NOTE: the quiz answer is option C."


def _editorjs(*texts: str) -> str:
	return json.dumps({"blocks": [{"type": "paragraph", "data": {"text": t}} for t in texts]})


def _lesson(content=None, instructor_content=None, body=None):
	return SimpleNamespace(
		name="0001 Lesson",
		course="corso-x",
		body=body,
		content=content,
		instructor_content=instructor_content,
	)


class TestParserSkipsInstructorContent(UnitTestCase):
	def test_instructor_content_is_not_in_the_parsed_text(self):
		lesson = _lesson(content=_editorjs(STUDENT_TEXT), instructor_content=_editorjs(INSTRUCTOR_TEXT))

		text = LessonContentParser(lesson).extract_text()

		self.assertIn(STUDENT_TEXT, text)
		self.assertNotIn(INSTRUCTOR_TEXT, text)

	def test_lesson_with_only_instructor_content_yields_no_text(self):
		lesson = _lesson(content=None, instructor_content=_editorjs(INSTRUCTOR_TEXT))

		self.assertEqual(LessonContentParser(lesson).extract_text(), "")

	def test_indexed_text_sent_to_the_rag_store_has_no_instructor_notes(self):
		lesson = _lesson(content=_editorjs(STUDENT_TEXT), instructor_content=_editorjs(INSTRUCTOR_TEXT))
		lesson.index_status = "pending"
		lesson.db_set = MagicMock()
		service = IngestionService(settings=SimpleNamespace(enabled=True))
		service._rag_db = MagicMock()

		with patch.object(frappe.db, "commit"):
			service.ingest_lesson(lesson)

		service._rag_db.ingest_data.assert_called_once()
		course, lesson_name, text = service._rag_db.ingest_data.call_args.args
		self.assertEqual((course, lesson_name), ("corso-x", "0001 Lesson"))
		self.assertIn(STUDENT_TEXT, text)
		self.assertNotIn(INSTRUCTOR_TEXT, text)


class TestInstructorEditDoesNotQueueReindex(UnitTestCase):
	def _doc(self, changed: set[str]):
		doc = MagicMock()
		doc.is_new.return_value = False
		doc.has_value_changed.side_effect = lambda field: field in changed
		doc.index_status = "indexed"
		return doc

	def test_instructor_content_change_alone_keeps_the_index(self):
		doc = self._doc({"instructor_content"})
		lesson_events.reset_index_status_on_content_change(doc, "before_save")
		self.assertEqual(doc.index_status, "indexed")

	def test_content_change_still_queues_reindex(self):
		doc = self._doc({"content"})
		lesson_events.reset_index_status_on_content_change(doc, "before_save")
		self.assertEqual(doc.index_status, "pending")


class TestRequeuePatch(UnitTestCase):
	def test_has_instructor_blocks(self):
		self.assertTrue(requeue.has_instructor_blocks(_editorjs(INSTRUCTOR_TEXT)))
		self.assertFalse(requeue.has_instructor_blocks(json.dumps({"blocks": []})))
		self.assertFalse(requeue.has_instructor_blocks(None))
		self.assertFalse(requeue.has_instructor_blocks(""))
		self.assertTrue(requeue.has_instructor_blocks("legacy markdown note"))

	def test_only_lessons_with_instructor_notes_are_requeued(self):
		rows = [
			frappe._dict(name="with-notes", instructor_content=_editorjs(INSTRUCTOR_TEXT)),
			frappe._dict(name="empty-notes", instructor_content=json.dumps({"blocks": []})),
		]
		with (
			patch.object(frappe, "get_all", return_value=rows) as get_all,
			patch.object(frappe.db, "set_value") as set_value,
		):
			requeue.execute()

		filters = get_all.call_args.kwargs["filters"]
		self.assertEqual(filters["index_status"], ["in", ("indexed", "failed")])
		set_value.assert_called_once_with(
			"Course Lesson",
			{"name": ["in", ["with-notes"]]},
			"index_status",
			"pending",
			update_modified=False,
		)

	def test_nothing_to_requeue_writes_nothing(self):
		with (
			patch.object(frappe, "get_all", return_value=[]),
			patch.object(frappe.db, "set_value") as set_value,
		):
			requeue.execute()
		set_value.assert_not_called()
