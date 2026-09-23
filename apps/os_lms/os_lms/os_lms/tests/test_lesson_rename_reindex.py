"""Unit tests for the Course Lesson after_rename hook.

The regression these cover: upstream v2.61.0 renames settled "NNNN Untitled
lesson" docnames every night, but the AI tutor's Redis vectors stay tagged with
the old name, so the tutor stops finding the lesson and the old chunks leak.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import UnitTestCase

from os_lms.events import lesson as lesson_events


def _lesson(name="0012 Intro", status="indexed"):
	return SimpleNamespace(name=name, course="corso-x", index_status=status)


class TestReindexAfterRename(UnitTestCase):
	def _run(self, doc, old):
		service = MagicMock()
		with (
			patch("os_lms.os_lms.ai.ingestion.service.IngestionService", return_value=service),
			patch.object(frappe.db, "set_value") as set_value,
		):
			lesson_events.reindex_after_rename(doc, "after_rename", old, doc.name, False)
		return service, set_value

	def test_drops_old_vectors_and_queues_reindex(self):
		service, set_value = self._run(_lesson(), "0012 Untitled lesson")

		service.remove_lesson.assert_called_once_with("corso-x", "0012 Untitled lesson")
		set_value.assert_called_once_with(
			"Course Lesson", "0012 Intro", "index_status", "pending", update_modified=False
		)

	def test_lesson_being_indexed_is_not_requeued(self):
		service, set_value = self._run(_lesson(status="processing"), "0012 Untitled lesson")

		service.remove_lesson.assert_called_once()
		set_value.assert_not_called()

	def test_same_name_is_a_no_op(self):
		service, set_value = self._run(_lesson(), "0012 Intro")

		service.remove_lesson.assert_not_called()
		set_value.assert_not_called()

	def test_rag_failure_does_not_block_the_rename(self):
		service = MagicMock()
		service.remove_lesson.side_effect = RuntimeError("redis down")
		with (
			patch("os_lms.os_lms.ai.ingestion.service.IngestionService", return_value=service),
			patch.object(frappe.db, "set_value") as set_value,
			patch.object(frappe, "log_error") as log_error,
		):
			lesson_events.reindex_after_rename(_lesson(), "after_rename", "0012 Untitled lesson", "0012 Intro")

		log_error.assert_called_once()
		set_value.assert_called_once()
